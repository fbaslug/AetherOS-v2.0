"""Jerarquía de excepciones personalizadas para AetherOS v2.0.

Cada subsistema del kernel tiene su rama de excepciones, permitiendo
captura granular en las capas superiores. Todas heredan de ``AetherOSError``
para facilitar capturas genéricas cuando sea necesario.

Jerarquía::

    AetherOSError
    ├── ProcesoError
    │   ├── ProcesoNoEncontrado
    │   └── LimiteProcesosAlcanzado
    ├── MemoriaError
    │   ├── MemoriaInsuficiente
    │   └── BloqueNoEncontrado
    ├── DispositivoError
    │   ├── DispositivoNoDisponible
    │   └── OperacionESFallida
    ├── ArchivoError
    │   ├── RutaInvalida
    │   ├── PermisoInsuficiente
    │   └── ElementoNoEncontrado
    └── TerminalError
        ├── ShellNoDisponible
        └── ComandoFallido
"""

from __future__ import annotations


class AetherOSError(Exception):
    """Excepción base para todos los errores de AetherOS.

    Attributes:
        mensaje: Descripción legible del error.
        codigo: Código numérico de error para consumo programático.
    """

    def __init__(self, mensaje: str = "Error interno de AetherOS", codigo: int = 1) -> None:
        self.mensaje: str = mensaje
        self.codigo: int = codigo
        super().__init__(self.mensaje)

    def to_dict(self) -> dict[str, object]:
        """Serializa la excepción a diccionario para logging/API."""
        return {
            "tipo": self.__class__.__name__,
            "mensaje": self.mensaje,
            "codigo": self.codigo,
        }


# ---------------------------------------------------------------------------
# Excepciones de Gestión de Procesos
# ---------------------------------------------------------------------------

class ProcesoError(AetherOSError):
    """Error base del subsistema de procesos."""

    def __init__(self, mensaje: str = "Error en gestión de procesos", codigo: int = 100) -> None:
        super().__init__(mensaje, codigo)


class ProcesoNoEncontrado(ProcesoError):
    """El PID solicitado no existe en la tabla de procesos.

    Attributes:
        pid: PID que no fue encontrado.
    """

    def __init__(self, pid: int) -> None:
        self.pid: int = pid
        super().__init__(f"Proceso con PID {pid} no encontrado", codigo=101)


class LimiteProcesosAlcanzado(ProcesoError):
    """Se alcanzó el número máximo de procesos concurrentes.

    Attributes:
        limite: Límite configurado de procesos.
    """

    def __init__(self, limite: int) -> None:
        self.limite: int = limite
        super().__init__(
            f"Límite de procesos alcanzado: {limite} procesos máximo",
            codigo=102,
        )


# ---------------------------------------------------------------------------
# Excepciones de Administración de Memoria
# ---------------------------------------------------------------------------

class MemoriaError(AetherOSError):
    """Error base del subsistema de memoria."""

    def __init__(self, mensaje: str = "Error en administración de memoria", codigo: int = 200) -> None:
        super().__init__(mensaje, codigo)


class MemoriaInsuficiente(MemoriaError):
    """No hay suficientes marcos libres para satisfacer la solicitud.

    Attributes:
        solicitado: Unidades de memoria solicitadas.
        disponible: Unidades de memoria disponibles.
    """

    def __init__(self, solicitado: int, disponible: int) -> None:
        self.solicitado: int = solicitado
        self.disponible: int = disponible
        super().__init__(
            f"Memoria insuficiente: solicitado={solicitado}, disponible={disponible}",
            codigo=201,
        )


class BloqueNoEncontrado(MemoriaError):
    """El bloque o asignación de memoria referenciado no existe.

    Attributes:
        identificador: ID del bloque o PID consultado.
    """

    def __init__(self, identificador: int) -> None:
        self.identificador: int = identificador
        super().__init__(
            f"Bloque de memoria no encontrado para identificador {identificador}",
            codigo=202,
        )


# ---------------------------------------------------------------------------
# Excepciones de Controladores de Dispositivo
# ---------------------------------------------------------------------------

class DispositivoError(AetherOSError):
    """Error base del subsistema de dispositivos."""

    def __init__(self, mensaje: str = "Error en controlador de dispositivo", codigo: int = 300) -> None:
        super().__init__(mensaje, codigo)


class DispositivoNoDisponible(DispositivoError):
    """El dispositivo solicitado no está registrado o está fuera de servicio.

    Attributes:
        id_dispositivo: ID del dispositivo no disponible.
    """

    def __init__(self, id_dispositivo: int) -> None:
        self.id_dispositivo: int = id_dispositivo
        super().__init__(
            f"Dispositivo {id_dispositivo} no disponible",
            codigo=301,
        )


class OperacionESFallida(DispositivoError):
    """Una operación de entrada/salida no se completó correctamente.

    Attributes:
        id_dispositivo: ID del dispositivo.
        operacion: Tipo de operación que falló.
    """

    def __init__(self, id_dispositivo: int, operacion: str) -> None:
        self.id_dispositivo: int = id_dispositivo
        self.operacion: str = operacion
        super().__init__(
            f"Operación '{operacion}' fallida en dispositivo {id_dispositivo}",
            codigo=302,
        )


# ---------------------------------------------------------------------------
# Excepciones de Gestión de Archivos
# ---------------------------------------------------------------------------

class ArchivoError(AetherOSError):
    """Error base del subsistema de archivos."""

    def __init__(self, mensaje: str = "Error en gestión de archivos", codigo: int = 400) -> None:
        super().__init__(mensaje, codigo)


class RutaInvalida(ArchivoError):
    """La ruta proporcionada es insegura o está fuera del sandbox.

    Attributes:
        ruta: Ruta que fue rechazada.
    """

    def __init__(self, ruta: str) -> None:
        self.ruta: str = ruta
        super().__init__(f"Ruta inválida o fuera del sandbox: {ruta}", codigo=401)


class PermisoInsuficiente(ArchivoError):
    """El proceso no tiene permisos para la operación solicitada.

    Attributes:
        ruta: Ruta donde se denegó el acceso.
        operacion: Operación que fue denegada.
    """

    def __init__(self, ruta: str, operacion: str = "acceso") -> None:
        self.ruta: str = ruta
        self.operacion: str = operacion
        super().__init__(
            f"Permiso insuficiente para '{operacion}' en: {ruta}",
            codigo=402,
        )


class ElementoNoEncontrado(ArchivoError):
    """El archivo o directorio referenciado no existe.

    Attributes:
        ruta: Ruta que no fue encontrada.
    """

    def __init__(self, ruta: str) -> None:
        self.ruta: str = ruta
        super().__init__(f"Elemento no encontrado: {ruta}", codigo=403)


# ---------------------------------------------------------------------------
# Excepciones de Terminal Integrada
# ---------------------------------------------------------------------------

class TerminalError(AetherOSError):
    """Error base del subsistema de terminal."""

    def __init__(self, mensaje: str = "Error en terminal integrada", codigo: int = 500) -> None:
        super().__init__(mensaje, codigo)


class ShellNoDisponible(TerminalError):
    """El shell o emulador de terminal no está disponible en la plataforma.

    Attributes:
        plataforma: Sistema operativo detectado.
    """

    def __init__(self, plataforma: str) -> None:
        self.plataforma: str = plataforma
        super().__init__(
            f"Shell PTY no disponible en plataforma '{plataforma}'. "
            "Esta funcionalidad requiere un sistema Linux con soporte para "
            "pseudo-terminales (pty) y el emulador xterm instalado.",
            codigo=501,
        )


class ComandoFallido(TerminalError):
    """La ejecución de un comando en la terminal falló.

    Attributes:
        comando: Comando que falló.
        codigo_salida: Código de salida del proceso.
    """

    def __init__(self, comando: str, codigo_salida: int = -1) -> None:
        self.comando: str = comando
        self.codigo_salida: int = codigo_salida
        super().__init__(
            f"Comando fallido (exit={codigo_salida}): {comando}",
            codigo=502,
        )
