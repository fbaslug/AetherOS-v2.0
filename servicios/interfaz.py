"""Módulo de gestión de archivos para AetherOS v2.0.

Provee una capa de abstracción segura sobre las operaciones del
sistema de archivos del host, confinando todas las operaciones
dentro de un directorio sandbox configurable.

Características de seguridad:
    - Path traversal prevention via ``os.path.realpath()``
    - Sandbox enforced: todas las rutas se resuelven dentro del directorio raíz
    - Sanitización de nombres de archivo
    - Captura exhaustiva de OSError, FileNotFoundError, PermissionError
"""

from __future__ import annotations

import logging
import os
import re
import stat
import time
from pathlib import Path
from typing import Optional

from excepciones.errores import (
    ElementoNoEncontrado,
    PermisoInsuficiente,
    RutaInvalida,
)
from modelos.tipos import EntradaArchivo, ResultadoOperacion

logger = logging.getLogger("AetherOS.Archivos")

# Caracteres prohibidos en nombres de archivo
_CARACTERES_PELIGROSOS = re.compile(r'[<>:"|?*\x00-\x1f]')


class GestorArchivos:
    """Gestor seguro de operaciones sobre el sistema de archivos.

    Todas las operaciones se confinan dentro de un directorio raíz
    (sandbox). Las rutas relativas se resuelven contra este directorio
    y las rutas absolutas se validan para garantizar que no escapan
    del sandbox.

    Attributes:
        raiz: Ruta absoluta del directorio sandbox.
    """

    def __init__(self, raiz: Optional[str] = None) -> None:
        """Inicializa el gestor de archivos con un directorio raíz.

        Si el directorio raíz no existe, se crea automáticamente.

        Args:
            raiz: Ruta del directorio sandbox. Por defecto usa
                  ``~/AetherOS_Root/``.

        Raises:
            RutaInvalida: Si la ruta raíz no puede ser creada.
        """
        if raiz is None:
            raiz = os.path.join(os.path.expanduser("~"), "AetherOS_Root")

        self.raiz: str = os.path.realpath(raiz)

        try:
            os.makedirs(self.raiz, exist_ok=True)
        except OSError as e:
            raise RutaInvalida(
                f"No se pudo crear directorio raíz '{self.raiz}': {e}"
            ) from e

        logger.info("GestorArchivos inicializado: raíz='%s'", self.raiz)

    # ------------------------------------------------------------------
    # API Pública
    # ------------------------------------------------------------------

    def listar_directorio(self, ruta: str = ".") -> ResultadoOperacion:
        """Lista el contenido de un directorio diferenciando archivos y carpetas.

        Utiliza ``os.listdir()`` y clasifica cada entrada según su tipo.

        Args:
            ruta: Ruta relativa al sandbox o absoluta dentro del sandbox.

        Returns:
            ResultadoOperacion con lista de EntradaArchivo.

        Raises:
            RutaInvalida: Si la ruta está fuera del sandbox.
            ElementoNoEncontrado: Si el directorio no existe.
            PermisoInsuficiente: Si no hay permisos de lectura.
        """
        ruta_absoluta = self._resolver_ruta(ruta)
        self._validar_sandbox(ruta_absoluta)

        try:
            if not os.path.exists(ruta_absoluta):
                raise ElementoNoEncontrado(ruta_absoluta)

            if not os.path.isdir(ruta_absoluta):
                return ResultadoOperacion(
                    exito=False,
                    mensaje=f"'{ruta}' no es un directorio",
                    datos=None,
                    codigo_error=404,
                )

            entradas: list[EntradaArchivo] = []
            for nombre in os.listdir(ruta_absoluta):
                ruta_completa = os.path.join(ruta_absoluta, nombre)
                try:
                    info_stat = os.stat(ruta_completa)
                    es_directorio = os.path.isdir(ruta_completa)

                    entrada: EntradaArchivo = {
                        "nombre": nombre,
                        "ruta": ruta_completa,
                        "tipo": "directorio" if es_directorio else "archivo",
                        "tamaño": 0 if es_directorio else info_stat.st_size,
                        "permisos": oct(stat.S_IMODE(info_stat.st_mode)),
                    }
                    entradas.append(entrada)
                except OSError:
                    # Omitir entradas inaccesibles sin interrumpir el listado
                    logger.warning("No se pudo acceder a: %s", ruta_completa)

            # Ordenar: directorios primero, luego archivos, alfabético
            entradas.sort(
                key=lambda e: (0 if e["tipo"] == "directorio" else 1, e["nombre"].lower())
            )

            return ResultadoOperacion(
                exito=True,
                mensaje=f"{len(entradas)} elemento(s) en '{ruta}'",
                datos=entradas,
                codigo_error=0,
            )

        except (ElementoNoEncontrado, RutaInvalida, PermisoInsuficiente):
            raise
        except PermissionError as e:
            raise PermisoInsuficiente(ruta_absoluta, "listar") from e
        except FileNotFoundError as e:
            raise ElementoNoEncontrado(ruta_absoluta) from e
        except OSError as e:
            logger.error("Error al listar directorio '%s': %s", ruta, e)
            return ResultadoOperacion(
                exito=False,
                mensaje=f"Error del sistema de archivos: {e}",
                datos=None,
                codigo_error=405,
            )

    def crear_directorio(self, ruta: str) -> ResultadoOperacion:
        """Crea un directorio de forma recursiva.

        Utiliza ``os.makedirs()`` para crear la ruta completa
        incluyendo directorios intermedios.

        Args:
            ruta: Ruta del directorio a crear.

        Returns:
            ResultadoOperacion indicando el resultado.

        Raises:
            RutaInvalida: Si la ruta está fuera del sandbox o tiene
                         caracteres peligrosos.
            PermisoInsuficiente: Si no hay permisos de escritura.
        """
        ruta_absoluta = self._resolver_ruta(ruta)
        self._validar_sandbox(ruta_absoluta)

        # Validar nombre del directorio final
        nombre_final = os.path.basename(ruta_absoluta)
        self._validar_nombre(nombre_final)

        try:
            if os.path.exists(ruta_absoluta):
                return ResultadoOperacion(
                    exito=False,
                    mensaje=f"El directorio ya existe: '{ruta}'",
                    datos={"ruta": ruta_absoluta},
                    codigo_error=406,
                )

            os.makedirs(ruta_absoluta, exist_ok=False)

            logger.info("Directorio creado: '%s'", ruta_absoluta)

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Directorio creado: '{ruta}'",
                datos={"ruta": ruta_absoluta},
                codigo_error=0,
            )

        except PermissionError as e:
            raise PermisoInsuficiente(ruta_absoluta, "crear directorio") from e
        except FileNotFoundError as e:
            raise ElementoNoEncontrado(
                os.path.dirname(ruta_absoluta)
            ) from e
        except OSError as e:
            logger.error("Error al crear directorio '%s': %s", ruta, e)
            return ResultadoOperacion(
                exito=False,
                mensaje=f"Error del sistema de archivos: {e}",
                datos=None,
                codigo_error=407,
            )

    def eliminar_directorio(self, ruta: str) -> ResultadoOperacion:
        """Elimina un directorio vacío con validación previa.

        Utiliza ``os.rmdir()`` que solo elimina directorios vacíos,
        previniendo eliminaciones accidentales de contenido.

        Args:
            ruta: Ruta del directorio a eliminar.

        Returns:
            ResultadoOperacion indicando el resultado.

        Raises:
            RutaInvalida: Si la ruta está fuera del sandbox.
            ElementoNoEncontrado: Si el directorio no existe.
            PermisoInsuficiente: Si no hay permisos de escritura.
        """
        ruta_absoluta = self._resolver_ruta(ruta)
        self._validar_sandbox(ruta_absoluta)

        # Protección: no permitir eliminar el directorio raíz
        if os.path.realpath(ruta_absoluta) == self.raiz:
            return ResultadoOperacion(
                exito=False,
                mensaje="No se puede eliminar el directorio raíz del sandbox",
                datos=None,
                codigo_error=408,
            )

        try:
            if not os.path.exists(ruta_absoluta):
                raise ElementoNoEncontrado(ruta_absoluta)

            if not os.path.isdir(ruta_absoluta):
                return ResultadoOperacion(
                    exito=False,
                    mensaje=f"'{ruta}' no es un directorio",
                    datos=None,
                    codigo_error=409,
                )

            # Verificar si está vacío
            contenido = os.listdir(ruta_absoluta)
            if contenido:
                return ResultadoOperacion(
                    exito=False,
                    mensaje=(
                        f"El directorio no está vacío ({len(contenido)} elemento(s)). "
                        "Solo se pueden eliminar directorios vacíos."
                    ),
                    datos={"elementos": len(contenido)},
                    codigo_error=410,
                )

            os.rmdir(ruta_absoluta)

            logger.info("Directorio eliminado: '%s'", ruta_absoluta)

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Directorio eliminado: '{ruta}'",
                datos={"ruta": ruta_absoluta},
                codigo_error=0,
            )

        except (ElementoNoEncontrado, RutaInvalida, PermisoInsuficiente):
            raise
        except PermissionError as e:
            raise PermisoInsuficiente(ruta_absoluta, "eliminar directorio") from e
        except FileNotFoundError as e:
            raise ElementoNoEncontrado(ruta_absoluta) from e
        except OSError as e:
            logger.error("Error al eliminar directorio '%s': %s", ruta, e)
            return ResultadoOperacion(
                exito=False,
                mensaje=f"Error del sistema de archivos: {e}",
                datos=None,
                codigo_error=411,
            )

    def renombrar(self, ruta_origen: str, ruta_destino: str) -> ResultadoOperacion:
        """Renombra o reubica un archivo o directorio.

        Utiliza ``os.rename()`` para mover/renombrar el elemento.
        Tanto el origen como el destino deben estar dentro del sandbox.

        Args:
            ruta_origen: Ruta actual del elemento.
            ruta_destino: Nueva ruta o nombre del elemento.

        Returns:
            ResultadoOperacion indicando el resultado.

        Raises:
            RutaInvalida: Si alguna ruta está fuera del sandbox.
            ElementoNoEncontrado: Si el origen no existe.
            PermisoInsuficiente: Si no hay permisos.
        """
        abs_origen = self._resolver_ruta(ruta_origen)
        abs_destino = self._resolver_ruta(ruta_destino)
        self._validar_sandbox(abs_origen)
        self._validar_sandbox(abs_destino)

        # Validar nombre del destino
        nombre_destino = os.path.basename(abs_destino)
        self._validar_nombre(nombre_destino)

        try:
            if not os.path.exists(abs_origen):
                raise ElementoNoEncontrado(abs_origen)

            if os.path.exists(abs_destino):
                return ResultadoOperacion(
                    exito=False,
                    mensaje=f"Ya existe un elemento en la ruta destino: '{ruta_destino}'",
                    datos=None,
                    codigo_error=412,
                )

            # Asegurar que el directorio padre del destino existe
            dir_padre_destino = os.path.dirname(abs_destino)
            if not os.path.exists(dir_padre_destino):
                return ResultadoOperacion(
                    exito=False,
                    mensaje=f"El directorio padre del destino no existe: '{dir_padre_destino}'",
                    datos=None,
                    codigo_error=413,
                )

            os.rename(abs_origen, abs_destino)

            logger.info(
                "Renombrado: '%s' -> '%s'",
                abs_origen,
                abs_destino,
            )

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Renombrado: '{ruta_origen}' -> '{ruta_destino}'",
                datos={
                    "ruta_anterior": abs_origen,
                    "ruta_nueva": abs_destino,
                },
                codigo_error=0,
            )

        except (ElementoNoEncontrado, RutaInvalida, PermisoInsuficiente):
            raise
        except PermissionError as e:
            raise PermisoInsuficiente(abs_origen, "renombrar") from e
        except FileNotFoundError as e:
            raise ElementoNoEncontrado(abs_origen) from e
        except OSError as e:
            logger.error(
                "Error al renombrar '%s' -> '%s': %s",
                ruta_origen,
                ruta_destino,
                e,
            )
            return ResultadoOperacion(
                exito=False,
                mensaje=f"Error del sistema de archivos: {e}",
                datos=None,
                codigo_error=414,
            )

    def obtener_info(self, ruta: str) -> ResultadoOperacion:
        """Obtiene metadatos de un archivo o directorio.

        Args:
            ruta: Ruta del elemento a consultar.

        Returns:
            ResultadoOperacion con metadatos del elemento.

        Raises:
            RutaInvalida: Si la ruta está fuera del sandbox.
            ElementoNoEncontrado: Si el elemento no existe.
        """
        ruta_absoluta = self._resolver_ruta(ruta)
        self._validar_sandbox(ruta_absoluta)

        try:
            if not os.path.exists(ruta_absoluta):
                raise ElementoNoEncontrado(ruta_absoluta)

            info_stat = os.stat(ruta_absoluta)
            es_directorio = os.path.isdir(ruta_absoluta)

            datos: dict[str, object] = {
                "nombre": os.path.basename(ruta_absoluta),
                "ruta": ruta_absoluta,
                "tipo": "directorio" if es_directorio else "archivo",
                "tamaño": 0 if es_directorio else info_stat.st_size,
                "permisos": oct(stat.S_IMODE(info_stat.st_mode)),
                "modificado": info_stat.st_mtime,
                "creado": info_stat.st_ctime,
                "accedido": info_stat.st_atime,
            }

            if es_directorio:
                try:
                    datos["elementos"] = len(os.listdir(ruta_absoluta))
                except OSError:
                    datos["elementos"] = -1

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Información de '{ruta}'",
                datos=datos,
                codigo_error=0,
            )

        except (ElementoNoEncontrado, RutaInvalida):
            raise
        except PermissionError as e:
            raise PermisoInsuficiente(ruta_absoluta, "obtener info") from e
        except FileNotFoundError as e:
            raise ElementoNoEncontrado(ruta_absoluta) from e
        except OSError as e:
            logger.error("Error al obtener info de '%s': %s", ruta, e)
            return ResultadoOperacion(
                exito=False,
                mensaje=f"Error del sistema de archivos: {e}",
                datos=None,
                codigo_error=415,
            )

    def existe(self, ruta: str) -> ResultadoOperacion:
        """Verifica si un archivo o directorio existe.

        Args:
            ruta: Ruta a verificar.

        Returns:
            ResultadoOperacion con el resultado de la verificación.
        """
        try:
            ruta_absoluta = self._resolver_ruta(ruta)
            self._validar_sandbox(ruta_absoluta)
            resultado = os.path.exists(ruta_absoluta)

            return ResultadoOperacion(
                exito=True,
                mensaje=f"'{ruta}' {'existe' if resultado else 'no existe'}",
                datos={"existe": resultado, "ruta": ruta_absoluta},
                codigo_error=0,
            )
        except (RutaInvalida, PermisoInsuficiente):
            raise
        except OSError as e:
            return ResultadoOperacion(
                exito=False,
                mensaje=f"Error al verificar existencia: {e}",
                datos={"existe": False},
                codigo_error=416,
            )

    # ------------------------------------------------------------------
    # Métodos de seguridad internos
    # ------------------------------------------------------------------

    def _resolver_ruta(self, ruta: str) -> str:
        """Resuelve una ruta relativa o absoluta contra el directorio raíz.

        Las rutas relativas se interpretan como relativas al sandbox.
        Las rutas absolutas se validan en ``_validar_sandbox``.

        Args:
            ruta: Ruta a resolver.

        Returns:
            Ruta absoluta resuelta.
        """
        if os.path.isabs(ruta):
            return os.path.realpath(ruta)
        return os.path.realpath(os.path.join(self.raiz, ruta))

    def _validar_sandbox(self, ruta_absoluta: str) -> None:
        """Valida que una ruta resuelta esté dentro del directorio sandbox.

        Previene ataques de path traversal verificando que la ruta
        resuelta comience con el prefijo del directorio raíz.

        Args:
            ruta_absoluta: Ruta ya resuelta con ``os.path.realpath()``.

        Raises:
            RutaInvalida: Si la ruta está fuera del sandbox.
        """
        # Normalizar ambas rutas para comparación segura
        ruta_normalizada = os.path.normcase(os.path.realpath(ruta_absoluta))
        raiz_normalizada = os.path.normcase(self.raiz)

        if not ruta_normalizada.startswith(raiz_normalizada + os.sep) and \
           ruta_normalizada != raiz_normalizada:
            raise RutaInvalida(ruta_absoluta)

    @staticmethod
    def _validar_nombre(nombre: str) -> None:
        """Valida que un nombre de archivo no contenga caracteres peligrosos.

        Args:
            nombre: Nombre del archivo o directorio.

        Raises:
            RutaInvalida: Si el nombre contiene caracteres prohibidos.
        """
        if not nombre or nombre.strip() == "":
            raise RutaInvalida("El nombre no puede estar vacío")

        if _CARACTERES_PELIGROSOS.search(nombre):
            raise RutaInvalida(
                f"Nombre contiene caracteres no permitidos: '{nombre}'"
            )

        # Prevenir nombres reservados en Windows
        nombres_reservados = {
            "CON", "PRN", "AUX", "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }
        if nombre.upper().split(".")[0] in nombres_reservados:
            raise RutaInvalida(
                f"Nombre reservado del sistema: '{nombre}'"
            )
