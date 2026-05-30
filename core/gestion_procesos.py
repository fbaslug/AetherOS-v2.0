"""Módulo de gestión de procesos para AetherOS v2.0.

Implementa la simulación completa del ciclo de vida de procesos,
incluyendo planificación Round-Robin con prioridades y control de
estados con máquina de transiciones validadas.

El módulo es thread-safe: todas las operaciones sobre la tabla de
procesos están protegidas con ``threading.Lock``.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import asdict
from typing import Optional

from excepciones.errores import (
    LimiteProcesosAlcanzado,
    ProcesoNoEncontrado,
)
from modelos.tipos import EstadoProceso, Proceso, ResultadoOperacion

logger = logging.getLogger("AetherOS.Procesos")

# Transiciones de estado válidas: estado_actual -> {estados_destino}
_TRANSICIONES_VALIDAS: dict[EstadoProceso, set[EstadoProceso]] = {
    EstadoProceso.NUEVO: {EstadoProceso.LISTO},
    EstadoProceso.LISTO: {EstadoProceso.EJECUTANDO},
    EstadoProceso.EJECUTANDO: {
        EstadoProceso.LISTO,
        EstadoProceso.BLOQUEADO,
        EstadoProceso.TERMINADO,
    },
    EstadoProceso.BLOQUEADO: {EstadoProceso.LISTO},
    EstadoProceso.TERMINADO: set(),
}


class GestorProcesos:
    """Gestor del ciclo de vida y planificación de procesos.

    Provee una API completa para crear, consultar, transicionar y
    planificar procesos bajo un esquema Round-Robin con soporte
    de prioridades.

    Attributes:
        quantum: Unidades de tiempo asignadas a cada proceso por ciclo.
        max_procesos: Límite máximo de procesos concurrentes.
    """

    def __init__(
        self,
        quantum: int = 4,
        max_procesos: int = 256,
    ) -> None:
        """Inicializa el gestor de procesos.

        Args:
            quantum: Unidades de CPU por ciclo de planificación.
            max_procesos: Número máximo de procesos permitidos.
        """
        self.quantum: int = quantum
        self.max_procesos: int = max_procesos

        self._tabla_procesos: dict[int, Proceso] = {}
        self._cola_listos: deque[int] = deque()
        self._pid_actual: Optional[int] = None
        self._siguiente_pid: int = 1
        self._lock: threading.Lock = threading.Lock()

        # Contadores de estadísticas
        self._total_creados: int = 0
        self._total_terminados: int = 0
        self._cambios_contexto: int = 0

        logger.info(
            "GestorProcesos inicializado (quantum=%d, max=%d)",
            quantum,
            max_procesos,
        )

    # ------------------------------------------------------------------
    # API Pública
    # ------------------------------------------------------------------

    def crear_proceso(
        self,
        nombre: str,
        prioridad: int = 5,
    ) -> ResultadoOperacion:
        """Crea un nuevo proceso y lo transiciona a estado LISTO.

        Args:
            nombre: Nombre legible del proceso.
            prioridad: Prioridad de planificación (0 = máxima, 10 = mínima).

        Returns:
            ResultadoOperacion con los datos del proceso creado.

        Raises:
            LimiteProcesosAlcanzado: Si se alcanzó el máximo de procesos.
        """
        with self._lock:
            procesos_activos = sum(
                1
                for p in self._tabla_procesos.values()
                if p.estado != EstadoProceso.TERMINADO
            )
            if procesos_activos >= self.max_procesos:
                raise LimiteProcesosAlcanzado(self.max_procesos)

            pid = self._siguiente_pid
            self._siguiente_pid += 1

            proceso = Proceso(
                pid=pid,
                nombre=nombre,
                prioridad=max(0, min(10, prioridad)),
                quantum_restante=self.quantum,
            )

            self._tabla_procesos[pid] = proceso
            self._total_creados += 1

            # Transición automática NUEVO -> LISTO
            proceso.estado = EstadoProceso.LISTO
            self._insertar_en_cola(pid)

            logger.info("Proceso creado: PID=%d, nombre='%s'", pid, nombre)

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Proceso '{nombre}' creado con PID {pid}",
                datos=self._serializar_proceso(proceso),
                codigo_error=0,
            )

    def terminar_proceso(self, pid: int) -> ResultadoOperacion:
        """Termina un proceso y libera sus recursos.

        Args:
            pid: Identificador del proceso a terminar.

        Returns:
            ResultadoOperacion con el estado final del proceso.

        Raises:
            ProcesoNoEncontrado: Si el PID no existe.
        """
        with self._lock:
            proceso = self._obtener_proceso_o_error(pid)

            if proceso.estado == EstadoProceso.TERMINADO:
                return ResultadoOperacion(
                    exito=False,
                    mensaje=f"Proceso PID {pid} ya está terminado",
                    datos=self._serializar_proceso(proceso),
                    codigo_error=103,
                )

            estado_anterior = proceso.estado
            proceso.estado = EstadoProceso.TERMINADO

            # Limpiar de la cola de listos si estaba ahí
            if pid in self._cola_listos:
                self._cola_listos.remove(pid)

            if self._pid_actual == pid:
                self._pid_actual = None

            self._total_terminados += 1

            logger.info(
                "Proceso terminado: PID=%d (%s -> TERMINADO)",
                pid,
                estado_anterior.name,
            )

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Proceso PID {pid} terminado correctamente",
                datos=self._serializar_proceso(proceso),
                codigo_error=0,
            )

    def obtener_proceso(self, pid: int) -> ResultadoOperacion:
        """Consulta el estado actual de un proceso.

        Args:
            pid: Identificador del proceso.

        Returns:
            ResultadoOperacion con los datos del proceso.

        Raises:
            ProcesoNoEncontrado: Si el PID no existe.
        """
        with self._lock:
            proceso = self._obtener_proceso_o_error(pid)
            return ResultadoOperacion(
                exito=True,
                mensaje=f"Proceso PID {pid} encontrado",
                datos=self._serializar_proceso(proceso),
                codigo_error=0,
            )

    def listar_procesos(self, incluir_terminados: bool = False) -> ResultadoOperacion:
        """Lista todos los procesos del sistema.

        Args:
            incluir_terminados: Si True, incluye procesos en estado TERMINADO.

        Returns:
            ResultadoOperacion con lista de diccionarios de procesos.
        """
        with self._lock:
            procesos = [
                self._serializar_proceso(p)
                for p in self._tabla_procesos.values()
                if incluir_terminados or p.estado != EstadoProceso.TERMINADO
            ]
            return ResultadoOperacion(
                exito=True,
                mensaje=f"{len(procesos)} proceso(s) listado(s)",
                datos=procesos,
                codigo_error=0,
            )

    def cambiar_estado(
        self,
        pid: int,
        nuevo_estado: EstadoProceso,
    ) -> ResultadoOperacion:
        """Realiza una transición de estado validada para un proceso.

        Solo se permiten transiciones definidas en la máquina de estados.

        Args:
            pid: Identificador del proceso.
            nuevo_estado: Estado destino deseado.

        Returns:
            ResultadoOperacion indicando el resultado de la transición.

        Raises:
            ProcesoNoEncontrado: Si el PID no existe.
        """
        with self._lock:
            proceso = self._obtener_proceso_o_error(pid)
            estado_actual = proceso.estado

            if nuevo_estado not in _TRANSICIONES_VALIDAS.get(estado_actual, set()):
                msg = (
                    f"Transición inválida: {estado_actual.name} -> "
                    f"{nuevo_estado.name} para PID {pid}"
                )
                logger.warning(msg)
                return ResultadoOperacion(
                    exito=False,
                    mensaje=msg,
                    datos=self._serializar_proceso(proceso),
                    codigo_error=104,
                )

            proceso.estado = nuevo_estado

            # Gestionar colas según el nuevo estado
            if nuevo_estado == EstadoProceso.LISTO:
                proceso.quantum_restante = self.quantum
                self._insertar_en_cola(pid)
            elif nuevo_estado == EstadoProceso.EJECUTANDO:
                self._pid_actual = pid
                if pid in self._cola_listos:
                    self._cola_listos.remove(pid)
            elif nuevo_estado == EstadoProceso.TERMINADO:
                if pid in self._cola_listos:
                    self._cola_listos.remove(pid)
                if self._pid_actual == pid:
                    self._pid_actual = None
                self._total_terminados += 1
            elif nuevo_estado == EstadoProceso.BLOQUEADO:
                if pid in self._cola_listos:
                    self._cola_listos.remove(pid)
                if self._pid_actual == pid:
                    self._pid_actual = None

            logger.info(
                "Transición PID=%d: %s -> %s",
                pid,
                estado_actual.name,
                nuevo_estado.name,
            )

            return ResultadoOperacion(
                exito=True,
                mensaje=(
                    f"PID {pid}: {estado_actual.name} -> {nuevo_estado.name}"
                ),
                datos=self._serializar_proceso(proceso),
                codigo_error=0,
            )

    def planificar(self) -> ResultadoOperacion:
        """Ejecuta un ciclo de planificación Round-Robin con prioridades.

        Selecciona el siguiente proceso de la cola de listos. Si el
        proceso actual agotó su quantum, es devuelto a la cola. Los
        procesos con mayor prioridad (número menor) tienen preferencia.

        Returns:
            ResultadoOperacion con el proceso seleccionado o None si
            la cola está vacía.
        """
        with self._lock:
            # Devolver proceso actual a la cola si agotó quantum
            if self._pid_actual is not None:
                proceso_actual = self._tabla_procesos.get(self._pid_actual)
                if proceso_actual and proceso_actual.estado == EstadoProceso.EJECUTANDO:
                    proceso_actual.tiempo_cpu += (
                        self.quantum - proceso_actual.quantum_restante
                    )
                    proceso_actual.estado = EstadoProceso.LISTO
                    proceso_actual.quantum_restante = self.quantum
                    self._insertar_en_cola(self._pid_actual)
                self._pid_actual = None

            if not self._cola_listos:
                return ResultadoOperacion(
                    exito=True,
                    mensaje="Cola de procesos listos vacía",
                    datos=None,
                    codigo_error=0,
                )

            # Seleccionar proceso con mayor prioridad (menor número)
            mejor_pid = self._cola_listos[0]
            mejor_prioridad = self._tabla_procesos[mejor_pid].prioridad

            for pid_candidato in self._cola_listos:
                prioridad_candidato = self._tabla_procesos[pid_candidato].prioridad
                if prioridad_candidato < mejor_prioridad:
                    mejor_prioridad = prioridad_candidato
                    mejor_pid = pid_candidato

            self._cola_listos.remove(mejor_pid)
            proceso_seleccionado = self._tabla_procesos[mejor_pid]
            proceso_seleccionado.estado = EstadoProceso.EJECUTANDO
            proceso_seleccionado.quantum_restante = self.quantum
            self._pid_actual = mejor_pid
            self._cambios_contexto += 1

            logger.debug(
                "Planificado: PID=%d, prioridad=%d",
                mejor_pid,
                mejor_prioridad,
            )

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Proceso PID {mejor_pid} seleccionado para ejecución",
                datos=self._serializar_proceso(proceso_seleccionado),
                codigo_error=0,
            )

    def consumir_quantum(self, pid: int, unidades: int = 1) -> ResultadoOperacion:
        """Consume unidades de quantum del proceso en ejecución.

        Simula el consumo de tiempo de CPU. Si el quantum se agota,
        el proceso se marca para re-planificación.

        Args:
            pid: PID del proceso en ejecución.
            unidades: Unidades de quantum a consumir.

        Returns:
            ResultadoOperacion indicando si el quantum se agotó.

        Raises:
            ProcesoNoEncontrado: Si el PID no existe.
        """
        with self._lock:
            proceso = self._obtener_proceso_o_error(pid)

            if proceso.estado != EstadoProceso.EJECUTANDO:
                return ResultadoOperacion(
                    exito=False,
                    mensaje=f"PID {pid} no está en ejecución",
                    datos=self._serializar_proceso(proceso),
                    codigo_error=105,
                )

            proceso.quantum_restante = max(0, proceso.quantum_restante - unidades)
            proceso.tiempo_cpu += unidades
            quantum_agotado = proceso.quantum_restante <= 0

            return ResultadoOperacion(
                exito=True,
                mensaje=(
                    f"PID {pid}: quantum {'agotado' if quantum_agotado else 'restante='}"
                    f"{'planificar siguiente' if quantum_agotado else str(proceso.quantum_restante)}"
                ),
                datos={
                    **self._serializar_proceso(proceso),
                    "quantum_agotado": quantum_agotado,
                },
                codigo_error=0,
            )

    def obtener_estadisticas(self) -> ResultadoOperacion:
        """Retorna estadísticas globales del gestor de procesos.

        Returns:
            ResultadoOperacion con métricas agregadas.
        """
        with self._lock:
            conteo_estados: dict[str, int] = {}
            for estado in EstadoProceso:
                conteo_estados[estado.name] = sum(
                    1
                    for p in self._tabla_procesos.values()
                    if p.estado == estado
                )

            return ResultadoOperacion(
                exito=True,
                mensaje="Estadísticas del gestor de procesos",
                datos={
                    "total_creados": self._total_creados,
                    "total_terminados": self._total_terminados,
                    "procesos_activos": sum(
                        1
                        for p in self._tabla_procesos.values()
                        if p.estado != EstadoProceso.TERMINADO
                    ),
                    "en_cola_listos": len(self._cola_listos),
                    "pid_ejecutando": self._pid_actual,
                    "cambios_contexto": self._cambios_contexto,
                    "quantum": self.quantum,
                    "max_procesos": self.max_procesos,
                    "conteo_por_estado": conteo_estados,
                },
                codigo_error=0,
            )

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------

    def _obtener_proceso_o_error(self, pid: int) -> Proceso:
        """Busca un proceso por PID o lanza excepción.

        Args:
            pid: Identificador del proceso.

        Returns:
            Instancia del Proceso encontrado.

        Raises:
            ProcesoNoEncontrado: Si el PID no existe.
        """
        proceso = self._tabla_procesos.get(pid)
        if proceso is None:
            raise ProcesoNoEncontrado(pid)
        return proceso

    def _insertar_en_cola(self, pid: int) -> None:
        """Inserta un PID en la cola de listos si no está ya presente.

        Args:
            pid: Identificador del proceso a insertar.
        """
        if pid not in self._cola_listos:
            self._cola_listos.append(pid)

    @staticmethod
    def _serializar_proceso(proceso: Proceso) -> dict[str, object]:
        """Convierte un Proceso a diccionario serializable a JSON.

        Args:
            proceso: Instancia del proceso a serializar.

        Returns:
            Diccionario con todos los campos del proceso.
        """
        datos = asdict(proceso)
        datos["estado"] = proceso.estado.name
        return datos
