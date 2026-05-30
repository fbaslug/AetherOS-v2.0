"""Módulo de terminal integrada para AetherOS v2.0.

Provee una interfaz para ejecutar comandos del sistema mediante
pseudo-terminales (PTY) en sistemas Linux. En Windows, las
operaciones PTY lanzan ``ShellNoDisponible`` con un mensaje
descriptivo de incompatibilidad.

Arquitectura:
    - Se crea un par master/slave con ``pty.openpty()``
    - El proceso hijo (bash) se conecta al slave como stdin/stdout/stderr
    - La lectura del master es no bloqueante via ``select.select()``
    - Los comandos se sanitizan antes de la ejecución
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
import time
from typing import Optional

from excepciones.errores import (
    ComandoFallido,
    ShellNoDisponible,
    TerminalError,
)
from modelos.tipos import ResultadoOperacion

logger = logging.getLogger("AetherOS.Terminal")

# Verificar soporte de plataforma
_ES_LINUX: bool = platform.system() == "Linux"

# Imports condicionales para módulos exclusivos de Linux
if _ES_LINUX:
    import fcntl
    import pty
    import select
    import struct
    import termios


class TerminalIntegrada:
    """Terminal integrada con soporte de pseudo-terminal (PTY).

    Permite la ejecución interactiva de comandos del shell bash
    con captura de salida en tiempo real. En plataformas no-Linux,
    todas las operaciones PTY lanzan ``ShellNoDisponible``.

    Attributes:
        timeout: Segundos de espera para lectura de salida.
        shell: Ruta al shell a utilizar.
    """

    def __init__(
        self,
        timeout: float = 1.0,
        shell: str = "/bin/bash",
    ) -> None:
        """Inicializa la terminal integrada.

        Args:
            timeout: Timeout en segundos para operaciones de lectura.
            shell: Ruta al intérprete de shell.
        """
        self.timeout: float = timeout
        self.shell: str = shell

        self._master_fd: Optional[int] = None
        self._slave_fd: Optional[int] = None
        self._proceso: Optional[subprocess.Popen[bytes]] = None
        self._activa: bool = False

        logger.info(
            "TerminalIntegrada inicializada (plataforma=%s, shell=%s)",
            platform.system(),
            shell,
        )

    # ------------------------------------------------------------------
    # API Pública
    # ------------------------------------------------------------------

    def iniciar_sesion(self) -> ResultadoOperacion:
        """Abre una sesión de shell interactiva via PTY.

        Crea un par master/slave de pseudo-terminal e instancia
        un proceso hijo con bash.

        Returns:
            ResultadoOperacion indicando si la sesión se inició.

        Raises:
            ShellNoDisponible: En plataformas sin soporte PTY.
            TerminalError: Si ya hay una sesión activa.
        """
        self._verificar_plataforma()

        if self._activa:
            return ResultadoOperacion(
                exito=False,
                mensaje="Ya existe una sesión de terminal activa",
                datos=None,
                codigo_error=503,
            )

        try:
            # Crear par master/slave PTY
            self._master_fd, self._slave_fd = pty.openpty()

            # Instanciar proceso hijo con bash
            self._proceso = subprocess.Popen(
                [self.shell],
                stdin=self._slave_fd,
                stdout=self._slave_fd,
                stderr=self._slave_fd,
                preexec_fn=os.setsid,
            )

            self._activa = True

            logger.info(
                "Sesión de terminal iniciada (PID=%d, shell=%s)",
                self._proceso.pid,
                self.shell,
            )

            # Leer el prompt inicial (no bloqueante)
            time.sleep(0.1)
            prompt_inicial = self._leer_master()

            return ResultadoOperacion(
                exito=True,
                mensaje="Sesión de terminal iniciada",
                datos={
                    "pid": self._proceso.pid,
                    "shell": self.shell,
                    "prompt": prompt_inicial,
                },
                codigo_error=0,
            )

        except FileNotFoundError:
            self._limpiar()
            raise ShellNoDisponible(
                f"Linux (shell no encontrado: {self.shell})"
            )
        except OSError as e:
            self._limpiar()
            logger.error("Error al iniciar sesión de terminal: %s", e)
            return ResultadoOperacion(
                exito=False,
                mensaje=f"Error al iniciar terminal: {e}",
                datos=None,
                codigo_error=504,
            )

    def ejecutar_comando(self, comando: str) -> ResultadoOperacion:
        """Envía un comando al shell y captura la salida.

        El comando se sanitiza antes de ser enviado. La captura
        de salida usa ``select.select()`` para lectura no bloqueante.

        Args:
            comando: Comando a ejecutar en el shell.

        Returns:
            ResultadoOperacion con la salida del comando.

        Raises:
            ShellNoDisponible: En plataformas sin soporte PTY.
            TerminalError: Si no hay sesión activa.
            ComandoFallido: Si ocurre un error durante la ejecución.
        """
        self._verificar_plataforma()
        self._verificar_sesion_activa()

        # Sanitizar comando
        comando_limpio = self._sanitizar_comando(comando)
        if comando_limpio is None:
            return ResultadoOperacion(
                exito=False,
                mensaje="Comando rechazado por contener patrones peligrosos",
                datos={"comando_original": comando},
                codigo_error=505,
            )

        try:
            # Enviar comando al master fd
            os.write(self._master_fd, (comando_limpio + "\n").encode("utf-8"))

            # Esperar brevemente para que el comando se procese
            time.sleep(0.2)

            # Leer salida completa
            salida = self._leer_master()

            logger.debug("Comando ejecutado: '%s'", comando_limpio)

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Comando ejecutado: '{comando_limpio}'",
                datos={
                    "comando": comando_limpio,
                    "salida": salida,
                    "timestamp": time.time(),
                },
                codigo_error=0,
            )

        except OSError as e:
            logger.error(
                "Error al ejecutar comando '%s': %s",
                comando_limpio,
                e,
            )
            raise ComandoFallido(comando_limpio) from e

    def leer_salida(self) -> ResultadoOperacion:
        """Lee la salida disponible del proceso activo (no bloqueante).

        Utiliza ``select.select()`` para verificar si hay datos
        disponibles antes de intentar la lectura.

        Returns:
            ResultadoOperacion con el texto disponible.

        Raises:
            ShellNoDisponible: En plataformas sin soporte PTY.
            TerminalError: Si no hay sesión activa.
        """
        self._verificar_plataforma()
        self._verificar_sesion_activa()

        try:
            salida = self._leer_master()
            tiene_datos = len(salida) > 0

            return ResultadoOperacion(
                exito=True,
                mensaje="Salida leída" if tiene_datos else "Sin datos disponibles",
                datos={
                    "salida": salida,
                    "tiene_datos": tiene_datos,
                },
                codigo_error=0,
            )

        except OSError as e:
            logger.error("Error al leer salida: %s", e)
            return ResultadoOperacion(
                exito=False,
                mensaje=f"Error al leer salida de la terminal: {e}",
                datos=None,
                codigo_error=506,
            )

    def enviar_entrada(self, texto: str) -> ResultadoOperacion:
        """Envía texto de entrada al proceso activo.

        Útil para responder a prompts interactivos o enviar
        señales como Ctrl+C (\\x03) o Ctrl+D (\\x04).

        Args:
            texto: Texto a enviar al proceso.

        Returns:
            ResultadoOperacion indicando si se envió correctamente.

        Raises:
            ShellNoDisponible: En plataformas sin soporte PTY.
            TerminalError: Si no hay sesión activa.
        """
        self._verificar_plataforma()
        self._verificar_sesion_activa()

        try:
            bytes_escritos = os.write(
                self._master_fd,
                texto.encode("utf-8"),
            )

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Enviados {bytes_escritos} byte(s) a la terminal",
                datos={
                    "bytes_enviados": bytes_escritos,
                    "texto": texto if len(texto) <= 100 else texto[:100] + "...",
                },
                codigo_error=0,
            )

        except OSError as e:
            logger.error("Error al enviar entrada: %s", e)
            return ResultadoOperacion(
                exito=False,
                mensaje=f"Error al enviar entrada a la terminal: {e}",
                datos=None,
                codigo_error=507,
            )

    def cerrar_sesion(self) -> ResultadoOperacion:
        """Cierra la sesión de terminal y libera todos los recursos.

        Envía señal de terminación al proceso hijo y cierra los
        descriptores de archivo del PTY.

        Returns:
            ResultadoOperacion confirmando el cierre.
        """
        if not self._activa:
            return ResultadoOperacion(
                exito=False,
                mensaje="No hay sesión de terminal activa",
                datos=None,
                codigo_error=508,
            )

        pid_proceso = self._proceso.pid if self._proceso else None

        try:
            if self._proceso:
                self._proceso.terminate()
                try:
                    self._proceso.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self._proceso.kill()
                    self._proceso.wait(timeout=2)

        except (OSError, subprocess.SubprocessError) as e:
            logger.warning("Error al terminar proceso de terminal: %s", e)
        finally:
            self._limpiar()

        logger.info("Sesión de terminal cerrada (PID=%s)", pid_proceso)

        return ResultadoOperacion(
            exito=True,
            mensaje="Sesión de terminal cerrada",
            datos={"pid_terminado": pid_proceso},
            codigo_error=0,
        )

    def esta_activa(self) -> ResultadoOperacion:
        """Verifica si la sesión de terminal está activa.

        Comprueba tanto el flag interno como el estado real del
        proceso hijo.

        Returns:
            ResultadoOperacion con el estado de la sesión.
        """
        activa = self._activa

        # Verificar que el proceso hijo sigue vivo
        if activa and self._proceso:
            codigo_retorno = self._proceso.poll()
            if codigo_retorno is not None:
                self._activa = False
                activa = False
                logger.info(
                    "Proceso de terminal terminó inesperadamente (exit=%d)",
                    codigo_retorno,
                )

        return ResultadoOperacion(
            exito=True,
            mensaje=f"Terminal {'activa' if activa else 'inactiva'}",
            datos={
                "activa": activa,
                "pid": self._proceso.pid if self._proceso and activa else None,
                "plataforma": platform.system(),
                "soporte_pty": _ES_LINUX,
            },
            codigo_error=0,
        )

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------

    def _verificar_plataforma(self) -> None:
        """Verifica que la plataforma soporte PTY.

        Raises:
            ShellNoDisponible: Si la plataforma no es Linux.
        """
        if not _ES_LINUX:
            raise ShellNoDisponible(platform.system())

    def _verificar_sesion_activa(self) -> None:
        """Verifica que haya una sesión activa.

        Raises:
            TerminalError: Si no hay sesión activa.
        """
        if not self._activa or self._master_fd is None:
            raise TerminalError(
                "No hay sesión de terminal activa. Use iniciar_sesion() primero.",
                codigo=509,
            )

    def _leer_master(self) -> str:
        """Lee datos disponibles del master fd usando select().

        Implementa lectura no bloqueante con timeout configurable.
        Acumula múltiples fragmentos hasta que no haya más datos.

        Returns:
            Texto leído decodificado.
        """
        salida_completa = b""
        timeout = self.timeout

        while True:
            lista_lectura, _, _ = select.select(
                [self._master_fd], [], [], timeout
            )

            if not lista_lectura:
                break

            try:
                fragmento = os.read(self._master_fd, 4096)
                if not fragmento:
                    break
                salida_completa += fragmento
                # Reducir timeout para lecturas subsecuentes
                timeout = 0.1
            except OSError:
                break

        return salida_completa.decode("utf-8", errors="replace")

    def _limpiar(self) -> None:
        """Libera los recursos del PTY y resetea el estado interno."""
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None

        if self._slave_fd is not None:
            try:
                os.close(self._slave_fd)
            except OSError:
                pass
            self._slave_fd = None

        self._proceso = None
        self._activa = False

    @staticmethod
    def _sanitizar_comando(comando: str) -> Optional[str]:
        """Sanitiza un comando para prevenir inyección básica.

        Elimina espacios extra y verifica que el comando no esté vacío.
        En modo no restringido, permite la mayoría de operadores de shell.

        Args:
            comando: Comando original.

        Returns:
            Comando sanitizado, o None si es rechazado.
        """
        if not comando or not comando.strip():
            return None

        # Eliminar caracteres de control (excepto tab y newline)
        comando_limpio = "".join(
            c for c in comando.strip()
            if c >= " " or c in ("\t",)
        )

        if not comando_limpio:
            return None

        return comando_limpio
