"""Definiciones de tipos y estructuras de datos para AetherOS v2.0.

Este módulo centraliza todas las dataclasses, enumeraciones y TypedDicts
que conforman el modelo de dominio del sistema operativo simulado.
Todos los módulos del kernel y servicios consumen estas estructuras
para garantizar consistencia en la comunicación entre capas.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional, TypedDict


# ---------------------------------------------------------------------------
# Enumeraciones
# ---------------------------------------------------------------------------

class EstadoProceso(Enum):
    """Estados posibles en el ciclo de vida de un proceso.

    Transiciones válidas:
        NUEVO -> LISTO
        LISTO -> EJECUTANDO
        EJECUTANDO -> LISTO (preemption / quantum expirado)
        EJECUTANDO -> BLOQUEADO (espera de E/S)
        EJECUTANDO -> TERMINADO
        BLOQUEADO -> LISTO (E/S completada)
    """

    NUEVO = auto()
    LISTO = auto()
    EJECUTANDO = auto()
    BLOQUEADO = auto()
    TERMINADO = auto()


class TipoDispositivo(Enum):
    """Categorías de dispositivos de hardware simulado."""

    TECLADO = "teclado"
    PANTALLA = "pantalla"
    DISCO = "disco"
    RED = "red"
    IMPRESORA = "impresora"
    USB = "usb"


class EstadoDispositivo(Enum):
    """Estados operativos de un dispositivo."""

    ACTIVO = "activo"
    INACTIVO = "inactivo"
    ERROR = "error"
    OCUPADO = "ocupado"


class TipoOperacionES(Enum):
    """Tipos de operación de entrada/salida."""

    LECTURA = "lectura"
    ESCRITURA = "escritura"
    CONTROL = "control"


# ---------------------------------------------------------------------------
# Dataclasses — Núcleo del sistema
# ---------------------------------------------------------------------------

@dataclass
class Proceso:
    """Representación de un proceso del sistema.

    Attributes:
        pid: Identificador único del proceso.
        nombre: Nombre legible del proceso.
        estado: Estado actual en el ciclo de vida.
        prioridad: Prioridad de planificación (0 = máxima).
        memoria_asignada: Total de unidades de memoria asignadas.
        tiempo_cpu: Unidades de tiempo de CPU consumidas.
        quantum_restante: Unidades de quantum restantes en el ciclo actual.
        timestamp_creacion: Marca de tiempo UNIX de creación.
    """

    pid: int
    nombre: str
    estado: EstadoProceso = EstadoProceso.NUEVO
    prioridad: int = 5
    memoria_asignada: int = 0
    tiempo_cpu: int = 0
    quantum_restante: int = 4
    timestamp_creacion: float = field(default_factory=time.time)


@dataclass
class Pagina:
    """Página de memoria virtual asignada a un proceso.

    Attributes:
        numero_pagina: Índice de la página dentro del espacio del proceso.
        marco: Número del marco físico asignado (-1 si no está cargada).
        en_memoria: Indica si la página reside actualmente en RAM.
        pid: PID del proceso propietario.
    """

    numero_pagina: int
    marco: int = -1
    en_memoria: bool = False
    pid: int = -1


@dataclass
class MarcoMemoria:
    """Marco (frame) de memoria física.

    Attributes:
        numero_marco: Índice del marco en la memoria física.
        ocupado: Indica si el marco está asignado.
        pid_propietario: PID del proceso que ocupa el marco (-1 si libre).
        pagina_asignada: Número de página mapeada a este marco (-1 si libre).
    """

    numero_marco: int
    ocupado: bool = False
    pid_propietario: int = -1
    pagina_asignada: int = -1


@dataclass
class BloqueMemoria:
    """Bloque lógico de memoria asignado a un proceso.

    Agrupa la información de asignación para consultas de alto nivel.

    Attributes:
        id_bloque: Identificador único del bloque.
        tamaño: Tamaño en unidades de memoria.
        ocupado: Si el bloque está en uso.
        pid_propietario: PID del proceso dueño.
        direccion_inicio: Dirección base del bloque (marco * tamaño_pagina).
        paginas: Lista de números de página que componen el bloque.
    """

    id_bloque: int
    tamaño: int
    ocupado: bool = True
    pid_propietario: int = -1
    direccion_inicio: int = 0
    paginas: list[int] = field(default_factory=list)


@dataclass
class DispositivoInfo:
    """Información de registro de un dispositivo de hardware simulado.

    Attributes:
        id_dispositivo: Identificador único del dispositivo.
        nombre: Nombre legible del dispositivo.
        tipo: Categoría de hardware.
        estado: Estado operativo actual.
        buffer_entrada: Buffer interno de datos de entrada.
        buffer_salida: Buffer interno de datos de salida.
        total_operaciones: Contador de operaciones realizadas.
    """

    id_dispositivo: int
    nombre: str
    tipo: TipoDispositivo
    estado: EstadoDispositivo = EstadoDispositivo.ACTIVO
    buffer_entrada: list[Any] = field(default_factory=list)
    buffer_salida: list[Any] = field(default_factory=list)
    total_operaciones: int = 0


@dataclass
class OperacionES:
    """Registro de una operación de entrada/salida.

    Attributes:
        dispositivo_id: ID del dispositivo involucrado.
        tipo_operacion: Lectura, escritura o control.
        datos: Payload de la operación.
        timestamp: Marca de tiempo UNIX de la operación.
        exitosa: Resultado de la operación.
    """

    dispositivo_id: int
    tipo_operacion: TipoOperacionES
    datos: Any = None
    timestamp: float = field(default_factory=time.time)
    exitosa: bool = True


# ---------------------------------------------------------------------------
# TypedDicts — Contratos de retorno
# ---------------------------------------------------------------------------

class EntradaArchivo(TypedDict):
    """Estructura de retorno para elementos del sistema de archivos.

    Attributes:
        nombre: Nombre del archivo o directorio.
        ruta: Ruta absoluta completa.
        tipo: Literal 'archivo' o 'directorio'.
        tamaño: Tamaño en bytes (0 para directorios).
        permisos: Cadena octal de permisos (ej. '0o755').
    """

    nombre: str
    ruta: str
    tipo: str
    tamaño: int
    permisos: str


class ResultadoOperacion(TypedDict, total=False):
    """Estructura de retorno uniforme para todas las operaciones del sistema.

    Se usa como contrato de respuesta en todos los métodos públicos
    de los módulos del kernel y servicios.

    Attributes:
        exito: Indica si la operación fue exitosa.
        mensaje: Descripción legible del resultado.
        datos: Payload opcional con datos de retorno.
        codigo_error: Código numérico de error (0 = sin error).
    """

    exito: bool
    mensaje: str
    datos: Any
    codigo_error: int
