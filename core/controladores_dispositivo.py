"""Módulo de controladores de dispositivo para AetherOS v2.0.

Implementa una capa de abstracción de hardware (HAL) simulada que
gestiona el registro, estado y operaciones de E/S de dispositivos
virtuales. Cada dispositivo tiene buffers internos de entrada/salida
y un historial de operaciones para auditoría.

Dispositivos pre-registrados al inicializar:
    - Teclado (ID=1)
    - Pantalla (ID=2)
    - Disco (ID=3)
    - Red (ID=4)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict
from typing import Any, Optional

from excepciones.errores import (
    DispositivoNoDisponible,
    OperacionESFallida,
)
from modelos.tipos import (
    DispositivoInfo,
    EstadoDispositivo,
    OperacionES,
    ResultadoOperacion,
    TipoDispositivo,
    TipoOperacionES,
)

logger = logging.getLogger("AetherOS.Dispositivos")


class ControladorDispositivos:
    """Capa de abstracción de hardware para dispositivos simulados.

    Gestiona el registro, desregistro y operaciones de E/S de
    dispositivos virtuales. Cada dispositivo mantiene buffers
    internos y un log de operaciones.

    Attributes:
        max_buffer: Tamaño máximo de los buffers de E/S por dispositivo.
    """

    def __init__(self, max_buffer: int = 1024) -> None:
        """Inicializa el controlador y registra dispositivos por defecto.

        Args:
            max_buffer: Capacidad máxima de los buffers de E/S.
        """
        self.max_buffer: int = max_buffer

        self._dispositivos: dict[int, DispositivoInfo] = {}
        self._log_operaciones: dict[int, list[dict[str, object]]] = {}
        self._siguiente_id: int = 1
        self._lock: threading.Lock = threading.Lock()

        # Registrar dispositivos por defecto
        self._registrar_defaults()

        logger.info(
            "ControladorDispositivos inicializado con %d dispositivo(s)",
            len(self._dispositivos),
        )

    # ------------------------------------------------------------------
    # API Pública
    # ------------------------------------------------------------------

    def registrar_dispositivo(
        self,
        nombre: str,
        tipo: TipoDispositivo,
    ) -> ResultadoOperacion:
        """Registra un nuevo dispositivo en el sistema.

        Args:
            nombre: Nombre legible del dispositivo.
            tipo: Categoría de hardware del dispositivo.

        Returns:
            ResultadoOperacion con los datos del dispositivo registrado.
        """
        with self._lock:
            id_dispositivo = self._siguiente_id
            self._siguiente_id += 1

            dispositivo = DispositivoInfo(
                id_dispositivo=id_dispositivo,
                nombre=nombre,
                tipo=tipo,
                estado=EstadoDispositivo.ACTIVO,
            )

            self._dispositivos[id_dispositivo] = dispositivo
            self._log_operaciones[id_dispositivo] = []

            logger.info(
                "Dispositivo registrado: ID=%d, nombre='%s', tipo=%s",
                id_dispositivo,
                nombre,
                tipo.value,
            )

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Dispositivo '{nombre}' registrado con ID {id_dispositivo}",
                datos=self._serializar_dispositivo(dispositivo),
                codigo_error=0,
            )

    def desregistrar_dispositivo(self, id_dispositivo: int) -> ResultadoOperacion:
        """Elimina un dispositivo del sistema.

        Args:
            id_dispositivo: ID del dispositivo a eliminar.

        Returns:
            ResultadoOperacion confirmando la eliminación.

        Raises:
            DispositivoNoDisponible: Si el ID no existe.
        """
        with self._lock:
            dispositivo = self._obtener_dispositivo_o_error(id_dispositivo)
            nombre = dispositivo.nombre

            del self._dispositivos[id_dispositivo]
            self._log_operaciones.pop(id_dispositivo, None)

            logger.info(
                "Dispositivo desregistrado: ID=%d, nombre='%s'",
                id_dispositivo,
                nombre,
            )

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Dispositivo '{nombre}' (ID={id_dispositivo}) eliminado",
                datos={"id_dispositivo": id_dispositivo, "nombre": nombre},
                codigo_error=0,
            )

    def listar_dispositivos(self) -> ResultadoOperacion:
        """Lista todos los dispositivos registrados en el sistema.

        Returns:
            ResultadoOperacion con la lista de dispositivos.
        """
        with self._lock:
            dispositivos = [
                self._serializar_dispositivo(d)
                for d in self._dispositivos.values()
            ]

            return ResultadoOperacion(
                exito=True,
                mensaje=f"{len(dispositivos)} dispositivo(s) registrado(s)",
                datos=dispositivos,
                codigo_error=0,
            )

    def enviar_operacion(
        self,
        id_dispositivo: int,
        tipo_operacion: TipoOperacionES,
        datos: Any = None,
    ) -> ResultadoOperacion:
        """Envía una operación de E/S a un dispositivo.

        Simula la operación según el tipo de dispositivo y registra
        el resultado en el log de operaciones.

        Args:
            id_dispositivo: ID del dispositivo destino.
            tipo_operacion: Tipo de operación (lectura/escritura/control).
            datos: Payload de la operación (opcional).

        Returns:
            ResultadoOperacion con el resultado de la operación.

        Raises:
            DispositivoNoDisponible: Si el dispositivo no existe.
            OperacionESFallida: Si el dispositivo está en estado de error.
        """
        with self._lock:
            dispositivo = self._obtener_dispositivo_o_error(id_dispositivo)

            if dispositivo.estado == EstadoDispositivo.ERROR:
                raise OperacionESFallida(
                    id_dispositivo,
                    tipo_operacion.value,
                )

            if dispositivo.estado == EstadoDispositivo.INACTIVO:
                return ResultadoOperacion(
                    exito=False,
                    mensaje=(
                        f"Dispositivo '{dispositivo.nombre}' está inactivo"
                    ),
                    datos=None,
                    codigo_error=303,
                )

            # Simular operación según tipo
            resultado_datos = self._ejecutar_operacion_simulada(
                dispositivo, tipo_operacion, datos
            )

            # Registrar operación
            operacion = OperacionES(
                dispositivo_id=id_dispositivo,
                tipo_operacion=tipo_operacion,
                datos=datos,
                exitosa=True,
            )
            dispositivo.total_operaciones += 1

            registro_log = {
                "tipo": tipo_operacion.value,
                "datos_entrada": str(datos) if datos is not None else None,
                "datos_salida": resultado_datos,
                "timestamp": operacion.timestamp,
                "exitosa": True,
            }
            self._log_operaciones[id_dispositivo].append(registro_log)

            logger.debug(
                "Operación %s en dispositivo %d: exitosa",
                tipo_operacion.value,
                id_dispositivo,
            )

            return ResultadoOperacion(
                exito=True,
                mensaje=(
                    f"Operación '{tipo_operacion.value}' completada en "
                    f"'{dispositivo.nombre}'"
                ),
                datos=resultado_datos,
                codigo_error=0,
            )

    def obtener_estado(self, id_dispositivo: int) -> ResultadoOperacion:
        """Consulta el estado actual de un dispositivo.

        Args:
            id_dispositivo: ID del dispositivo.

        Returns:
            ResultadoOperacion con el estado completo del dispositivo.

        Raises:
            DispositivoNoDisponible: Si el dispositivo no existe.
        """
        with self._lock:
            dispositivo = self._obtener_dispositivo_o_error(id_dispositivo)

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Estado del dispositivo '{dispositivo.nombre}'",
                datos=self._serializar_dispositivo(dispositivo),
                codigo_error=0,
            )

    def cambiar_estado_dispositivo(
        self,
        id_dispositivo: int,
        nuevo_estado: EstadoDispositivo,
    ) -> ResultadoOperacion:
        """Cambia el estado operativo de un dispositivo.

        Args:
            id_dispositivo: ID del dispositivo.
            nuevo_estado: Nuevo estado a asignar.

        Returns:
            ResultadoOperacion con el estado actualizado.

        Raises:
            DispositivoNoDisponible: Si el dispositivo no existe.
        """
        with self._lock:
            dispositivo = self._obtener_dispositivo_o_error(id_dispositivo)
            estado_anterior = dispositivo.estado
            dispositivo.estado = nuevo_estado

            logger.info(
                "Dispositivo %d: %s -> %s",
                id_dispositivo,
                estado_anterior.value,
                nuevo_estado.value,
            )

            return ResultadoOperacion(
                exito=True,
                mensaje=(
                    f"Dispositivo '{dispositivo.nombre}': "
                    f"{estado_anterior.value} -> {nuevo_estado.value}"
                ),
                datos=self._serializar_dispositivo(dispositivo),
                codigo_error=0,
            )

    def obtener_log_operaciones(
        self,
        id_dispositivo: int,
        limite: int = 50,
    ) -> ResultadoOperacion:
        """Retorna el historial de operaciones de un dispositivo.

        Args:
            id_dispositivo: ID del dispositivo.
            limite: Número máximo de entradas a retornar.

        Returns:
            ResultadoOperacion con la lista de operaciones.

        Raises:
            DispositivoNoDisponible: Si el dispositivo no existe.
        """
        with self._lock:
            self._obtener_dispositivo_o_error(id_dispositivo)
            operaciones = self._log_operaciones.get(id_dispositivo, [])
            ultimas = operaciones[-limite:]

            return ResultadoOperacion(
                exito=True,
                mensaje=(
                    f"{len(ultimas)} operación(es) del dispositivo "
                    f"{id_dispositivo}"
                ),
                datos=ultimas,
                codigo_error=0,
            )

    def obtener_estadisticas(self) -> ResultadoOperacion:
        """Retorna estadísticas globales de todos los dispositivos.

        Returns:
            ResultadoOperacion con métricas agregadas.
        """
        with self._lock:
            conteo_estados: dict[str, int] = {}
            for estado in EstadoDispositivo:
                conteo_estados[estado.value] = sum(
                    1
                    for d in self._dispositivos.values()
                    if d.estado == estado
                )

            total_ops = sum(
                d.total_operaciones for d in self._dispositivos.values()
            )

            return ResultadoOperacion(
                exito=True,
                mensaje="Estadísticas de dispositivos",
                datos={
                    "total_dispositivos": len(self._dispositivos),
                    "conteo_por_estado": conteo_estados,
                    "total_operaciones": total_ops,
                    "dispositivos": [
                        {
                            "id": d.id_dispositivo,
                            "nombre": d.nombre,
                            "tipo": d.tipo.value,
                            "estado": d.estado.value,
                            "operaciones": d.total_operaciones,
                        }
                        for d in self._dispositivos.values()
                    ],
                },
                codigo_error=0,
            )

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------

    def _registrar_defaults(self) -> None:
        """Registra los dispositivos del sistema por defecto.

        Se ejecuta durante la inicialización. Los dispositivos
        predeterminados representan el hardware básico simulado.
        """
        defaults = [
            ("Teclado del Sistema", TipoDispositivo.TECLADO),
            ("Pantalla Principal", TipoDispositivo.PANTALLA),
            ("Disco Primario", TipoDispositivo.DISCO),
            ("Interfaz de Red", TipoDispositivo.RED),
        ]
        for nombre, tipo in defaults:
            id_dev = self._siguiente_id
            self._siguiente_id += 1
            dispositivo = DispositivoInfo(
                id_dispositivo=id_dev,
                nombre=nombre,
                tipo=tipo,
                estado=EstadoDispositivo.ACTIVO,
            )
            self._dispositivos[id_dev] = dispositivo
            self._log_operaciones[id_dev] = []

    def _obtener_dispositivo_o_error(self, id_dispositivo: int) -> DispositivoInfo:
        """Busca un dispositivo por ID o lanza excepción.

        Args:
            id_dispositivo: ID del dispositivo.

        Returns:
            DispositivoInfo del dispositivo encontrado.

        Raises:
            DispositivoNoDisponible: Si el ID no existe.
        """
        dispositivo = self._dispositivos.get(id_dispositivo)
        if dispositivo is None:
            raise DispositivoNoDisponible(id_dispositivo)
        return dispositivo

    def _ejecutar_operacion_simulada(
        self,
        dispositivo: DispositivoInfo,
        tipo_operacion: TipoOperacionES,
        datos: Any,
    ) -> dict[str, object]:
        """Simula la ejecución de una operación de E/S según el tipo de dispositivo.

        Args:
            dispositivo: Dispositivo destino.
            tipo_operacion: Tipo de operación.
            datos: Payload de entrada.

        Returns:
            Diccionario con los resultados de la operación simulada.
        """
        resultado: dict[str, object] = {
            "dispositivo": dispositivo.nombre,
            "operacion": tipo_operacion.value,
            "timestamp": time.time(),
        }

        if tipo_operacion == TipoOperacionES.LECTURA:
            # Simular lectura: retornar datos del buffer de salida
            if dispositivo.buffer_salida:
                resultado["datos_leidos"] = dispositivo.buffer_salida.pop(0)
            else:
                resultado["datos_leidos"] = None
                resultado["nota"] = "Buffer de salida vacío"

        elif tipo_operacion == TipoOperacionES.ESCRITURA:
            # Simular escritura: agregar datos al buffer de entrada
            if datos is not None:
                if len(dispositivo.buffer_entrada) < self.max_buffer:
                    dispositivo.buffer_entrada.append(datos)
                    resultado["bytes_escritos"] = len(str(datos))
                else:
                    resultado["bytes_escritos"] = 0
                    resultado["nota"] = "Buffer de entrada lleno"
            else:
                resultado["bytes_escritos"] = 0
                resultado["nota"] = "Sin datos para escribir"

        elif tipo_operacion == TipoOperacionES.CONTROL:
            # Simular operación de control
            resultado["comando"] = str(datos) if datos else "status"
            resultado["respuesta"] = {
                "estado": dispositivo.estado.value,
                "buffer_entrada_size": len(dispositivo.buffer_entrada),
                "buffer_salida_size": len(dispositivo.buffer_salida),
                "total_operaciones": dispositivo.total_operaciones,
            }

        return resultado

    @staticmethod
    def _serializar_dispositivo(dispositivo: DispositivoInfo) -> dict[str, object]:
        """Convierte un DispositivoInfo a diccionario serializable.

        Args:
            dispositivo: Dispositivo a serializar.

        Returns:
            Diccionario con los datos del dispositivo.
        """
        return {
            "id_dispositivo": dispositivo.id_dispositivo,
            "nombre": dispositivo.nombre,
            "tipo": dispositivo.tipo.value,
            "estado": dispositivo.estado.value,
            "total_operaciones": dispositivo.total_operaciones,
            "buffer_entrada_size": len(dispositivo.buffer_entrada),
            "buffer_salida_size": len(dispositivo.buffer_salida),
        }
