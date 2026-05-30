"""Orquestador principal (kernel) de AetherOS v2.0.

Implementa el patrón Fachada para exponer una interfaz unificada
a los subsistemas del kernel: gestión de procesos, administración
de memoria, controladores de dispositivo y servicios de archivos/terminal.

Centraliza el logging del sistema y provee métodos para el ciclo
de vida del kernel (iniciar/apagar) y la consulta del estado global.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from core.admin_memoria import AdministradorMemoria
from core.controladores_dispositivo import ControladorDispositivos
from core.gestion_procesos import GestorProcesos
from excepciones.errores import AetherOSError
from modelos.tipos import ResultadoOperacion


def _configurar_logging(nivel: int = logging.INFO) -> logging.Logger:
    """Configura el logging centralizado para todo el sistema.

    Crea un logger raíz para AetherOS con formato estandarizado
    y handler de consola. Si ya existe, retorna el logger existente
    sin duplicar handlers.

    Args:
        nivel: Nivel de logging (default: INFO).

    Returns:
        Logger configurado.
    """
    logger = logging.getLogger("AetherOS")

    if not logger.handlers:
        logger.setLevel(nivel)
        handler = logging.StreamHandler()
        handler.setLevel(nivel)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


class SistemaAetherOS:
    """Fachada principal del sistema operativo AetherOS v2.0.

    Orquesta la inicialización, ciclo de vida y comunicación entre
    todos los subsistemas del kernel. Provee un punto de acceso
    unificado para capas superiores (GUI, CLI).

    Attributes:
        version: Versión del sistema.
        procesos: Subsistema de gestión de procesos.
        memoria: Subsistema de administración de memoria.
        dispositivos: Subsistema de controladores de dispositivo.
    """

    VERSION: str = "2.0.0"

    def __init__(
        self,
        quantum: int = 4,
        max_procesos: int = 256,
        memoria_total: int = 1024,
        tamaño_pagina: int = 64,
        nivel_log: int = logging.INFO,
    ) -> None:
        """Inicializa el sistema AetherOS con todos sus subsistemas.

        Args:
            quantum: Unidades de CPU por ciclo de planificación.
            max_procesos: Límite máximo de procesos concurrentes.
            memoria_total: Capacidad total de memoria simulada.
            tamaño_pagina: Tamaño de página/marco para paginación.
            nivel_log: Nivel del logging centralizado.
        """
        self._logger = _configurar_logging(nivel_log)
        self._activo: bool = False
        self._timestamp_inicio: Optional[float] = None

        # Inicializar subsistemas del kernel
        self.procesos: GestorProcesos = GestorProcesos(
            quantum=quantum,
            max_procesos=max_procesos,
        )
        self.memoria: AdministradorMemoria = AdministradorMemoria(
            memoria_total=memoria_total,
            tamaño_pagina=tamaño_pagina,
        )
        self.dispositivos: ControladorDispositivos = ControladorDispositivos()

        self._logger.info("SistemaAetherOS v%s instanciado", self.VERSION)

    # ------------------------------------------------------------------
    # Ciclo de vida del kernel
    # ------------------------------------------------------------------

    def iniciar(self) -> ResultadoOperacion:
        """Inicia el sistema operativo AetherOS.

        Activa todos los subsistemas y marca el kernel como operativo.

        Returns:
            ResultadoOperacion con el estado de inicio.
        """
        if self._activo:
            return ResultadoOperacion(
                exito=False,
                mensaje="El sistema ya está en ejecución",
                datos=None,
                codigo_error=10,
            )

        self._activo = True
        self._timestamp_inicio = time.time()

        self._logger.info("=" * 60)
        self._logger.info("  AetherOS v%s — Sistema Iniciado", self.VERSION)
        self._logger.info("=" * 60)

        return ResultadoOperacion(
            exito=True,
            mensaje=f"AetherOS v{self.VERSION} iniciado correctamente",
            datos={
                "version": self.VERSION,
                "timestamp_inicio": self._timestamp_inicio,
                "subsistemas": ["procesos", "memoria", "dispositivos"],
            },
            codigo_error=0,
        )

    def apagar(self) -> ResultadoOperacion:
        """Apaga el sistema operativo AetherOS de forma ordenada.

        Termina todos los procesos activos, libera memoria y
        desactiva el kernel.

        Returns:
            ResultadoOperacion con el resumen del apagado.
        """
        if not self._activo:
            return ResultadoOperacion(
                exito=False,
                mensaje="El sistema no está en ejecución",
                datos=None,
                codigo_error=11,
            )

        self._logger.info("Iniciando secuencia de apagado...")

        # Terminar procesos activos
        procesos_terminados = 0
        resultado_lista = self.procesos.listar_procesos(incluir_terminados=False)
        if resultado_lista["exito"] and resultado_lista.get("datos"):
            for proc in resultado_lista["datos"]:
                try:
                    self.procesos.terminar_proceso(proc["pid"])
                    # Liberar memoria del proceso
                    try:
                        self.memoria.liberar_memoria(proc["pid"])
                    except AetherOSError:
                        pass  # El proceso puede no tener memoria asignada
                    procesos_terminados += 1
                except AetherOSError as e:
                    self._logger.warning(
                        "Error al terminar proceso %d: %s",
                        proc["pid"],
                        e.mensaje,
                    )

        tiempo_activo = time.time() - self._timestamp_inicio if self._timestamp_inicio else 0
        self._activo = False
        self._timestamp_inicio = None

        self._logger.info("=" * 60)
        self._logger.info("  AetherOS v%s — Sistema Apagado", self.VERSION)
        self._logger.info("  Tiempo activo: %.2f segundos", tiempo_activo)
        self._logger.info("  Procesos terminados: %d", procesos_terminados)
        self._logger.info("=" * 60)

        return ResultadoOperacion(
            exito=True,
            mensaje="Sistema apagado correctamente",
            datos={
                "procesos_terminados": procesos_terminados,
                "tiempo_activo_segundos": round(tiempo_activo, 2),
            },
            codigo_error=0,
        )

    # ------------------------------------------------------------------
    # Estado del sistema
    # ------------------------------------------------------------------

    def obtener_estado_sistema(self) -> ResultadoOperacion:
        """Retorna el estado completo del sistema, serializable a JSON.

        Agrega información de todos los subsistemas en un solo
        diccionario que puede ser serializado con ``json.dumps()``.

        Returns:
            ResultadoOperacion con el estado global del sistema.
        """
        try:
            estado_procesos = self.procesos.obtener_estadisticas()
            estado_memoria = self.memoria.obtener_uso_memoria()
            estado_dispositivos = self.dispositivos.obtener_estadisticas()

            estado: dict[str, object] = {
                "sistema": {
                    "nombre": "AetherOS",
                    "version": self.VERSION,
                    "activo": self._activo,
                    "timestamp_inicio": self._timestamp_inicio,
                    "tiempo_activo_segundos": round(
                        time.time() - self._timestamp_inicio, 2
                    )
                    if self._timestamp_inicio
                    else 0,
                },
                "procesos": estado_procesos.get("datos"),
                "memoria": estado_memoria.get("datos"),
                "dispositivos": estado_dispositivos.get("datos"),
            }

            # Validar que es serializable a JSON
            json.dumps(estado, default=str)

            return ResultadoOperacion(
                exito=True,
                mensaje="Estado del sistema obtenido correctamente",
                datos=estado,
                codigo_error=0,
            )

        except Exception as e:
            self._logger.error("Error al obtener estado del sistema: %s", e)
            return ResultadoOperacion(
                exito=False,
                mensaje=f"Error al obtener estado del sistema: {e}",
                datos=None,
                codigo_error=12,
            )

    def esta_activo(self) -> bool:
        """Verifica si el sistema está en ejecución.

        Returns:
            True si el kernel está activo.
        """
        return self._activo
