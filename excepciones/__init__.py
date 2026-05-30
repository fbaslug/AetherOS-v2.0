"""Paquete de excepciones personalizadas para AetherOS v2.0.

Provee una jerarquía de excepciones tipadas que permite a cada capa
del sistema manejar errores de forma granular y predecible.
"""

from excepciones.errores import (
    AetherOSError,
    ProcesoError,
    ProcesoNoEncontrado,
    LimiteProcesosAlcanzado,
    MemoriaError,
    MemoriaInsuficiente,
    BloqueNoEncontrado,
    DispositivoError,
    DispositivoNoDisponible,
    OperacionESFallida,
    ArchivoError,
    RutaInvalida,
    PermisoInsuficiente,
    ElementoNoEncontrado,
    TerminalError,
    ShellNoDisponible,
    ComandoFallido,
)

__all__ = [
    "AetherOSError",
    "ProcesoError",
    "ProcesoNoEncontrado",
    "LimiteProcesosAlcanzado",
    "MemoriaError",
    "MemoriaInsuficiente",
    "BloqueNoEncontrado",
    "DispositivoError",
    "DispositivoNoDisponible",
    "OperacionESFallida",
    "ArchivoError",
    "RutaInvalida",
    "PermisoInsuficiente",
    "ElementoNoEncontrado",
    "TerminalError",
    "ShellNoDisponible",
    "ComandoFallido",
]
