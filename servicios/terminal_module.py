"""Módulo de terminal integrada para AetherOS v2.0.

Provee una interfaz para ejecutar comandos del sistema mediante
pseudo-terminales (PTY) en sistemas Linux. En Windows u otras
plataformas, utiliza un shell simulado con filesystem virtual
y comandos básicos de Linux.

Arquitectura:
    - En Linux: PTY real con ``pty.openpty()`` + bash
    - En otras plataformas: ``_ShellSimulado`` con filesystem virtual
    - API unificada: ``iniciar()``, ``enviar_comando()``, ``leer_salida()``,
      ``detener()``, ``get_prompt()``, ``esta_procesando()``
"""

from __future__ import annotations

import logging
import os
import platform
import queue
import shlex
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import Any, Callable, Optional

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


# ======================================================================
# Shell Simulado (para plataformas sin PTY)
# ======================================================================

class _ShellSimulado:
    """Mini-shell simulado con filesystem virtual.

    Implementa un subconjunto de comandos bash para demostración
    en plataformas que no soportan pseudo-terminales. Incluye
    un filesystem virtual en memoria y simulación de ``apt``.

    Attributes:
        PAQUETES_DISPONIBLES: Catálogo de paquetes simulados.
    """

    PAQUETES_DISPONIBLES: dict[str, dict[str, Any]] = {
        "nano": {
            "version": "7.2-1",
            "size_kb": 280,
            "desc": "small, friendly text editor",
            "icono": "📝",
        },
        "htop": {
            "version": "3.2.2-2",
            "size_kb": 172,
            "desc": "interactive process viewer",
            "icono": "📊",
        },
    }

    def __init__(
        self,
        on_install: Optional[Callable[[str], None]] = None,
        on_uninstall: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._user: str = "aether"
        self._hostname: str = "AetherOS"
        self._home: str = "/home/aether"
        self._cwd: str = "/home/aether"

        self._buffer: queue.Queue[str] = queue.Queue()
        self._instalados: set[str] = set()
        self._procesando: bool = False
        self._activo: bool = False

        self._on_install = on_install
        self._on_uninstall = on_uninstall

        self._historial: list[str] = []

        # Filesystem virtual (dict anidado: dict=directorio, str=archivo)
        self._fs: dict[str, Any] = self._crear_fs_inicial()

    # ------------------------------------------------------------------
    # Filesystem virtual
    # ------------------------------------------------------------------

    @staticmethod
    def _crear_fs_inicial() -> dict[str, Any]:
        """Crea el árbol de directorios inicial."""
        return {
            "home": {
                "aether": {
                    "Documentos": {
                        "readme.txt": (
                            "Bienvenido a AetherOS v2.0\n"
                            "Este es tu directorio de documentos.\n"
                        ),
                        "notas.txt": (
                            "=== Notas de AetherOS ===\n"
                            "- Sistema operativo simulado\n"
                            "- Kernel educativo en Python\n"
                        ),
                    },
                    "Descargas": {},
                    "Escritorio": {},
                    "Imagenes": {},
                    ".bashrc": (
                        "# ~/.bashrc\n"
                        "export PATH=/usr/local/bin:/usr/bin:/bin\n"
                        "export LANG=es_ES.UTF-8\n"
                    ),
                },
            },
            "etc": {
                "hostname": "AetherOS\n",
                "os-release": (
                    'NAME="AetherOS"\n'
                    'VERSION="2.0"\n'
                    "ID=aetheros\n"
                    'PRETTY_NAME="AetherOS 2.0 (Simulado)"\n'
                ),
                "passwd": (
                    "root:x:0:0:root:/root:/bin/bash\n"
                    "aether:x:1000:1000:Aether User:/home/aether:/bin/bash\n"
                ),
            },
            "usr": {
                "bin": {},
                "local": {"bin": {}},
                "share": {
                    "doc": {},
                },
            },
            "var": {
                "log": {
                    "syslog": (
                        "[INFO] AetherOS v2.0 iniciado\n"
                        "[INFO] Kernel simulado cargado\n"
                    ),
                },
                "cache": {
                    "apt": {
                        "archives": {},
                    },
                },
            },
            "tmp": {},
        }

    def _resolver_ruta_abs(self, ruta: str) -> str:
        """Normaliza una ruta a forma absoluta canónica."""
        if not ruta:
            ruta = self._cwd
        elif ruta == "~":
            ruta = self._home
        elif ruta.startswith("~/"):
            ruta = self._home + ruta[1:]
        elif not ruta.startswith("/"):
            ruta = self._cwd + "/" + ruta

        partes: list[str] = []
        for p in ruta.split("/"):
            if p == "" or p == ".":
                continue
            elif p == "..":
                if partes:
                    partes.pop()
            else:
                partes.append(p)

        return "/" + "/".join(partes) if partes else "/"

    def _obtener_nodo(self, ruta: str) -> Any:
        """Navega el filesystem virtual y retorna el nodo.

        Returns:
            El nodo (dict para directorio, str para archivo),
            o None si no existe.
        """
        ruta_abs = self._resolver_ruta_abs(ruta)
        if ruta_abs == "/":
            return self._fs

        partes = ruta_abs.strip("/").split("/")
        nodo: Any = self._fs
        for parte in partes:
            if not isinstance(nodo, dict) or parte not in nodo:
                return None
            nodo = nodo[parte]
        return nodo

    def _obtener_padre_y_nombre(self, ruta: str) -> tuple[Optional[dict], str]:
        """Retorna (directorio_padre, nombre_entrada) de una ruta."""
        ruta_abs = self._resolver_ruta_abs(ruta)
        if ruta_abs == "/":
            return None, "/"

        partes = ruta_abs.strip("/").split("/")
        nombre = partes[-1]
        padre_ruta = "/" + "/".join(partes[:-1]) if len(partes) > 1 else "/"
        padre = self._obtener_nodo(padre_ruta)

        if not isinstance(padre, dict):
            return None, nombre
        return padre, nombre

    # ------------------------------------------------------------------
    # API del Shell
    # ------------------------------------------------------------------

    def iniciar(self) -> None:
        """Inicia el shell simulado."""
        self._activo = True
        bienvenida = (
            "\033[1;36m"  # Cyan bold
            "╔══════════════════════════════════════════╗\n"
            "║      AetherOS Terminal v2.0              ║\n"
            "║      Sistema Operativo Simulado Linux    ║\n"
            "╚══════════════════════════════════════════╝\n"
            "\033[0m"
            "\nEscribe \033[1;32m'help'\033[0m para ver comandos disponibles.\n\n"
        )
        self._buffer.put(bienvenida)

    def ejecutar(self, comando: str) -> None:
        """Procesa un comando y pone la salida en el buffer."""
        comando = comando.strip()
        if not comando:
            return

        self._historial.append(comando)

        # Parsear comando (manejar pipes y redirecciones de forma básica)
        try:
            partes = shlex.split(comando)
        except ValueError:
            partes = comando.split()

        if not partes:
            return

        cmd = partes[0]
        args = partes[1:]

        # Tabla de comandos
        handlers: dict[str, Callable[[list[str]], None]] = {
            "ls": self._cmd_ls,
            "cd": self._cmd_cd,
            "pwd": self._cmd_pwd,
            "echo": self._cmd_echo,
            "cat": self._cmd_cat,
            "mkdir": self._cmd_mkdir,
            "touch": self._cmd_touch,
            "rm": self._cmd_rm,
            "rmdir": self._cmd_rmdir,
            "clear": self._cmd_clear,
            "uname": self._cmd_uname,
            "whoami": self._cmd_whoami,
            "date": self._cmd_date,
            "help": self._cmd_help,
            "exit": self._cmd_exit,
            "sudo": self._cmd_sudo,
            "apt": self._cmd_apt,
            "apt-get": self._cmd_apt,
            "neofetch": self._cmd_neofetch,
            "hostname": self._cmd_hostname,
            "id": self._cmd_id,
            "uptime": self._cmd_uptime,
            "df": self._cmd_df,
            "free": self._cmd_free,
        }

        handler = handlers.get(cmd)
        if handler:
            handler(args)
        else:
            self._buffer.put(
                f"\033[1;31mbash: {cmd}: command not found\033[0m\n"
            )

    def leer(self) -> str:
        """Lee todo el contenido disponible en el buffer."""
        salida = ""
        while not self._buffer.empty():
            try:
                salida += self._buffer.get_nowait()
            except queue.Empty:
                break
        return salida

    def get_prompt(self) -> str:
        """Retorna el prompt actual estilo bash."""
        cwd = self._cwd
        if cwd == self._home:
            cwd = "~"
        elif cwd.startswith(self._home + "/"):
            cwd = "~" + cwd[len(self._home):]

        return f"\033[1;32m{self._user}@{self._hostname}\033[0m:\033[1;34m{cwd}\033[0m$ "

    def detener(self) -> None:
        """Detiene el shell simulado."""
        self._activo = False

    # ------------------------------------------------------------------
    # Implementación de comandos
    # ------------------------------------------------------------------

    def _cmd_ls(self, args: list[str]) -> None:
        """Lista el contenido de un directorio."""
        mostrar_ocultos = "-a" in args or "-la" in args or "-al" in args
        detallado = "-l" in args or "-la" in args or "-al" in args

        # Filtrar flags de los argumentos
        rutas = [a for a in args if not a.startswith("-")]
        ruta = rutas[0] if rutas else "."

        nodo = self._obtener_nodo(ruta)
        if nodo is None:
            self._buffer.put(
                f"ls: cannot access '{ruta}': No such file or directory\n"
            )
            return

        if isinstance(nodo, str):
            # Es un archivo
            ruta_abs = self._resolver_ruta_abs(ruta)
            nombre = ruta_abs.split("/")[-1]
            if detallado:
                self._buffer.put(f"-rw-r--r-- 1 {self._user} {self._user} {len(nodo):>5d} {nombre}\n")
            else:
                self._buffer.put(f"{nombre}\n")
            return

        # Es un directorio
        entradas = sorted(nodo.keys())
        if not mostrar_ocultos:
            entradas = [e for e in entradas if not e.startswith(".")]

        if not entradas:
            return  # directorio vacío

        if detallado:
            self._buffer.put(f"total {len(entradas)}\n")
            for nombre in entradas:
                hijo = nodo[nombre]
                if isinstance(hijo, dict):
                    self._buffer.put(
                        f"\033[1;34mdrwxr-xr-x\033[0m 2 {self._user} {self._user}  4096 {nombre}/\n"
                    )
                else:
                    self._buffer.put(
                        f"-rw-r--r-- 1 {self._user} {self._user} {len(hijo):>5d} {nombre}\n"
                    )
        else:
            linea = ""
            for nombre in entradas:
                hijo = nodo[nombre]
                if isinstance(hijo, dict):
                    linea += f"\033[1;34m{nombre}/\033[0m  "
                else:
                    linea += f"{nombre}  "
            self._buffer.put(linea.rstrip() + "\n")

    def _cmd_cd(self, args: list[str]) -> None:
        """Cambia el directorio actual."""
        if not args or args[0] == "~":
            self._cwd = self._home
            return

        nueva_ruta = self._resolver_ruta_abs(args[0])
        nodo = self._obtener_nodo(nueva_ruta)

        if nodo is None:
            self._buffer.put(
                f"bash: cd: {args[0]}: No such file or directory\n"
            )
        elif not isinstance(nodo, dict):
            self._buffer.put(f"bash: cd: {args[0]}: Not a directory\n")
        else:
            self._cwd = nueva_ruta

    def _cmd_pwd(self, args: list[str]) -> None:
        """Muestra el directorio actual."""
        self._buffer.put(f"{self._cwd}\n")

    def _cmd_echo(self, args: list[str]) -> None:
        """Imprime texto."""
        texto = " ".join(args)
        # Manejar comillas simples y dobles básicamente
        texto = texto.replace("\\n", "\n").replace("\\t", "\t")
        self._buffer.put(f"{texto}\n")

    def _cmd_cat(self, args: list[str]) -> None:
        """Muestra el contenido de un archivo."""
        if not args:
            self._buffer.put("cat: missing operand\n")
            return

        for archivo in args:
            nodo = self._obtener_nodo(archivo)
            if nodo is None:
                self._buffer.put(
                    f"cat: {archivo}: No such file or directory\n"
                )
            elif isinstance(nodo, dict):
                self._buffer.put(f"cat: {archivo}: Is a directory\n")
            else:
                contenido = nodo if nodo.endswith("\n") else nodo + "\n"
                self._buffer.put(contenido)

    def _cmd_mkdir(self, args: list[str]) -> None:
        """Crea un directorio."""
        if not args:
            self._buffer.put("mkdir: missing operand\n")
            return

        crear_padres = "-p" in args
        rutas = [a for a in args if not a.startswith("-")]

        for ruta in rutas:
            padre, nombre = self._obtener_padre_y_nombre(ruta)
            if padre is None:
                if crear_padres:
                    self._crear_ruta_completa(ruta)
                else:
                    self._buffer.put(
                        f"mkdir: cannot create directory '{ruta}': "
                        "No such file or directory\n"
                    )
            elif nombre in padre:
                self._buffer.put(
                    f"mkdir: cannot create directory '{ruta}': File exists\n"
                )
            else:
                padre[nombre] = {}

    def _crear_ruta_completa(self, ruta: str) -> None:
        """Crea todos los directorios en una ruta (mkdir -p)."""
        ruta_abs = self._resolver_ruta_abs(ruta)
        partes = ruta_abs.strip("/").split("/")
        nodo = self._fs
        for parte in partes:
            if parte not in nodo:
                nodo[parte] = {}
            nodo_hijo = nodo[parte]
            if not isinstance(nodo_hijo, dict):
                return  # Conflicto con archivo existente
            nodo = nodo_hijo

    def _cmd_touch(self, args: list[str]) -> None:
        """Crea un archivo vacío o actualiza timestamp."""
        if not args:
            self._buffer.put("touch: missing file operand\n")
            return

        for archivo in args:
            padre, nombre = self._obtener_padre_y_nombre(archivo)
            if padre is None:
                self._buffer.put(
                    f"touch: cannot touch '{archivo}': "
                    "No such file or directory\n"
                )
            elif nombre not in padre:
                padre[nombre] = ""

    def _cmd_rm(self, args: list[str]) -> None:
        """Elimina archivos."""
        recursivo = "-r" in args or "-rf" in args or "-fr" in args
        rutas = [a for a in args if not a.startswith("-")]

        if not rutas:
            self._buffer.put("rm: missing operand\n")
            return

        for ruta in rutas:
            padre, nombre = self._obtener_padre_y_nombre(ruta)
            if padre is None or nombre not in padre:
                self._buffer.put(
                    f"rm: cannot remove '{ruta}': No such file or directory\n"
                )
            elif isinstance(padre[nombre], dict) and not recursivo:
                self._buffer.put(
                    f"rm: cannot remove '{ruta}': Is a directory\n"
                )
            else:
                del padre[nombre]

    def _cmd_rmdir(self, args: list[str]) -> None:
        """Elimina directorios vacíos."""
        if not args:
            self._buffer.put("rmdir: missing operand\n")
            return

        for ruta in args:
            padre, nombre = self._obtener_padre_y_nombre(ruta)
            if padre is None or nombre not in padre:
                self._buffer.put(
                    f"rmdir: failed to remove '{ruta}': "
                    "No such file or directory\n"
                )
            elif not isinstance(padre[nombre], dict):
                self._buffer.put(
                    f"rmdir: failed to remove '{ruta}': Not a directory\n"
                )
            elif padre[nombre]:
                self._buffer.put(
                    f"rmdir: failed to remove '{ruta}': "
                    "Directory not empty\n"
                )
            else:
                del padre[nombre]

    def _cmd_clear(self, args: list[str]) -> None:
        """Limpia la pantalla (marcador especial para la GUI)."""
        self._buffer.put("\x1b[CLEAR]")

    def _cmd_uname(self, args: list[str]) -> None:
        """Muestra información del sistema."""
        if "-a" in args:
            self._buffer.put(
                "Linux AetherOS 6.1.0-aether #1 SMP x86_64 GNU/Linux\n"
            )
        elif "-r" in args:
            self._buffer.put("6.1.0-aether\n")
        else:
            self._buffer.put("Linux\n")

    def _cmd_whoami(self, args: list[str]) -> None:
        """Muestra el usuario actual."""
        self._buffer.put(f"{self._user}\n")

    def _cmd_date(self, args: list[str]) -> None:
        """Muestra la fecha y hora actual."""
        ahora = datetime.now()
        self._buffer.put(ahora.strftime("%a %b %d %H:%M:%S %Z %Y") + "\n")

    def _cmd_hostname(self, args: list[str]) -> None:
        """Muestra el nombre del host."""
        self._buffer.put(f"{self._hostname}\n")

    def _cmd_id(self, args: list[str]) -> None:
        """Muestra información del usuario."""
        self._buffer.put(
            f"uid=1000({self._user}) gid=1000({self._user}) "
            f"groups=1000({self._user}),27(sudo)\n"
        )

    def _cmd_uptime(self, args: list[str]) -> None:
        """Muestra el tiempo de actividad."""
        ahora = datetime.now().strftime("%H:%M:%S")
        self._buffer.put(
            f" {ahora} up 1:23, 1 user, load average: 0.15, 0.10, 0.05\n"
        )

    def _cmd_df(self, args: list[str]) -> None:
        """Muestra uso de disco simulado."""
        self._buffer.put(
            "Filesystem     1K-blocks    Used Available Use% Mounted on\n"
            "/dev/sda1       51200000 8234560  42965440  17% /\n"
            "tmpfs            2048000       0   2048000   0% /tmp\n"
        )

    def _cmd_free(self, args: list[str]) -> None:
        """Muestra uso de memoria simulado."""
        self._buffer.put(
            "              total        used        free      shared\n"
            "Mem:        4096000     1024000     2560000      128000\n"
            "Swap:       2048000           0     2048000\n"
        )

    def _cmd_help(self, args: list[str]) -> None:
        """Muestra la ayuda con los comandos disponibles."""
        ayuda = (
            "\033[1;36m╔══════════════════════════════════════════════╗\n"
            "║          Comandos disponibles                ║\n"
            "╚══════════════════════════════════════════════╝\033[0m\n\n"
            "\033[1;33m  Navegación:\033[0m\n"
            "    ls [-la]         Listar archivos y directorios\n"
            "    cd <dir>         Cambiar de directorio\n"
            "    pwd              Mostrar directorio actual\n\n"
            "\033[1;33m  Archivos:\033[0m\n"
            "    cat <archivo>    Ver contenido de un archivo\n"
            "    touch <archivo>  Crear un archivo vacío\n"
            "    mkdir <dir>      Crear un directorio\n"
            "    rm <archivo>     Eliminar un archivo\n"
            "    rmdir <dir>      Eliminar directorio vacío\n\n"
            "\033[1;33m  Sistema:\033[0m\n"
            "    echo <texto>     Imprimir texto\n"
            "    uname [-a]       Información del sistema\n"
            "    whoami           Usuario actual\n"
            "    hostname         Nombre del equipo\n"
            "    date             Fecha y hora actual\n"
            "    uptime           Tiempo de actividad\n"
            "    df               Uso de disco\n"
            "    free             Uso de memoria\n"
            "    id               Info del usuario\n"
            "    neofetch         Info del sistema (fancy)\n"
            "    clear            Limpiar pantalla\n\n"
            "\033[1;33m  Paquetes:\033[0m\n"
            "    sudo apt install <paquete>    Instalar programa\n"
            "    sudo apt remove <paquete>     Desinstalar programa\n"
            "    apt list --installed           Ver programas instalados\n\n"
            "\033[1;33m  Paquetes disponibles:\033[0m nano, htop\n\n"
            "    exit             Cerrar terminal\n"
        )
        self._buffer.put(ayuda)

    def _cmd_exit(self, args: list[str]) -> None:
        """Marca la terminal como inactiva."""
        self._buffer.put("logout\n")
        self._activo = False

    def _cmd_neofetch(self, args: list[str]) -> None:
        """Muestra información del sistema con arte ASCII."""
        arte = (
            "\033[1;36m"
            "        ╱╲          \033[1;37m aether@AetherOS\n"
            "\033[1;36m       ╱  ╲         \033[0m ────────────────\n"
            "\033[1;36m      ╱    ╲        \033[1;33m OS:\033[0m AetherOS v2.0\n"
            "\033[1;36m     ╱  ╱╲  ╲       \033[1;33m Kernel:\033[0m 6.1.0-aether\n"
            "\033[1;36m    ╱  ╱  ╲  ╲      \033[1;33m Shell:\033[0m bash 5.2.15\n"
            "\033[1;36m   ╱  ╱    ╲  ╲     \033[1;33m Terminal:\033[0m AetherTerm\n"
            "\033[1;36m  ╱  ╱══════╲  ╲    \033[1;33m CPU:\033[0m AetherCPU (sim)\n"
            "\033[1;36m ╱            ╲   \033[1;33m Memory:\033[0m 1024M / 4096M\n"
            "\033[1;36m╱══════════════╲  \033[1;33m Packages:\033[0m "
            f"{len(self._instalados)} (apt)\n"
            "\033[0m\n"
        )
        self._buffer.put(arte)

    # ------------------------------------------------------------------
    # Gestión de paquetes (apt)
    # ------------------------------------------------------------------

    def _cmd_sudo(self, args: list[str]) -> None:
        """Procesa comandos con sudo."""
        if not args:
            self._buffer.put("usage: sudo <command>\n")
            return

        sub_cmd = args[0]
        sub_args = args[1:]

        if sub_cmd in ("apt", "apt-get"):
            self._cmd_apt(sub_args)
        else:
            # Simular ejecución con sudo
            handlers: dict[str, Callable[[list[str]], None]] = {
                "ls": self._cmd_ls,
                "cat": self._cmd_cat,
                "rm": self._cmd_rm,
                "mkdir": self._cmd_mkdir,
            }
            handler = handlers.get(sub_cmd)
            if handler:
                handler(sub_args)
            else:
                self._buffer.put(
                    f"sudo: {sub_cmd}: command not found\n"
                )

    def _cmd_apt(self, args: list[str]) -> None:
        """Gestiona paquetes con apt."""
        if not args:
            self._buffer.put(
                "usage: apt <command> [options]\n"
                "  install   Install packages\n"
                "  remove    Remove packages\n"
                "  list      List packages\n"
            )
            return

        sub = args[0]
        sub_args = args[1:]

        if sub == "install":
            self._apt_install(sub_args)
        elif sub == "remove" or sub == "purge":
            self._apt_remove(sub_args)
        elif sub == "list":
            self._apt_list(sub_args)
        elif sub == "update":
            self._apt_update()
        elif sub == "upgrade":
            self._apt_upgrade()
        else:
            self._buffer.put(
                f"E: Invalid operation {sub}\n"
            )

    def _apt_update(self) -> None:
        """Simula apt update."""
        self._procesando = True

        lineas = [
            ("Hit:1 http://archive.ubuntu.com/ubuntu jammy InRelease\n", 0.4),
            ("Hit:2 http://archive.ubuntu.com/ubuntu jammy-updates InRelease\n", 0.3),
            ("Hit:3 http://security.ubuntu.com/ubuntu jammy-security InRelease\n", 0.3),
            ("Reading package lists... ", 0.4),
            ("Done\n", 0.2),
        ]

        delay_acum = 0.0
        for texto, delay in lineas:
            delay_acum += delay
            threading.Timer(
                delay_acum,
                lambda t=texto: self._buffer.put(t),
            ).start()

        threading.Timer(delay_acum + 0.2, self._fin_procesamiento).start()

    def _apt_upgrade(self) -> None:
        """Simula apt upgrade."""
        self._buffer.put(
            "Reading package lists... Done\n"
            "Building dependency tree... Done\n"
            "0 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.\n"
        )

    def _apt_install(self, paquetes: list[str]) -> None:
        """Simula la instalación de paquetes con salida progresiva."""
        # Filtrar flags -y etc.
        paquetes_reales = [p for p in paquetes if not p.startswith("-")]

        if not paquetes_reales:
            self._buffer.put("E: No packages specified\n")
            return

        for paq in paquetes_reales:
            if paq not in self.PAQUETES_DISPONIBLES:
                self._buffer.put(
                    f"\033[1;31mE: Unable to locate package {paq}\033[0m\n"
                )
                return

            if paq in self._instalados:
                info = self.PAQUETES_DISPONIBLES[paq]
                self._buffer.put(
                    f"{paq} is already the newest version "
                    f"({info['version']}).\n"
                    "0 upgraded, 0 newly installed, 0 to remove.\n"
                )
                return

        # Animación progresiva para el primer paquete
        paq = paquetes_reales[0]
        info = self.PAQUETES_DISPONIBLES[paq]
        self._procesando = True

        lineas = [
            ("Reading package lists... ", 0.5),
            ("Done\n", 0.4),
            ("Building dependency tree... ", 0.5),
            ("Done\n", 0.3),
            ("Reading state information... ", 0.3),
            ("Done\n", 0.2),
            (
                f"The following \033[1;32mNEW\033[0m packages will be installed:\n"
                f"  {paq}\n",
                0.3,
            ),
            (
                "0 upgraded, 1 newly installed, 0 to remove "
                "and 0 not upgraded.\n",
                0.2,
            ),
            (
                f"Need to get {info['size_kb']} kB of archives.\n"
                f"After this operation, {info['size_kb'] * 3} kB of "
                "additional disk space will be used.\n",
                0.4,
            ),
            (
                f"\033[0;32mGet:1\033[0m http://archive.ubuntu.com/ubuntu "
                f"jammy/main amd64 {paq} amd64 {info['version']} "
                f"[{info['size_kb']} kB]\n",
                1.0,
            ),
            (
                f"Fetched {info['size_kb']} kB in 1s "
                f"({info['size_kb']} kB/s)\n",
                0.5,
            ),
            (
                f"Selecting previously unselected package {paq}.\n",
                0.3,
            ),
            (
                "(Reading database ... "
                "45832 files and directories currently installed.)\n",
                0.5,
            ),
            (
                f"Preparing to unpack .../{paq}_{info['version']}"
                "_amd64.deb ...\n",
                0.4,
            ),
            (
                f"Unpacking {paq} ({info['version']}) ...\n",
                0.6,
            ),
            (
                f"\033[1;32mSetting up {paq} ({info['version']}) "
                "...\033[0m\n",
                0.5,
            ),
            (
                "Processing triggers for man-db (2.10.2-1) ...\n",
                0.3,
            ),
        ]

        delay_acum = 0.0
        for texto, delay in lineas:
            delay_acum += delay
            threading.Timer(
                delay_acum,
                lambda t=texto: self._buffer.put(t),
            ).start()

        # Finalizar instalación
        def _completar_instalacion() -> None:
            self._instalados.add(paq)
            # Agregar binario al filesystem virtual
            usr_bin = self._obtener_nodo("/usr/bin")
            if isinstance(usr_bin, dict):
                usr_bin[paq] = f"#!/usr/bin/env bash\n# {paq} {info['version']}\n"

            self._procesando = False

            if self._on_install:
                self._on_install(paq)

        threading.Timer(delay_acum + 0.3, _completar_instalacion).start()

    def _apt_remove(self, paquetes: list[str]) -> None:
        """Simula la desinstalación de paquetes."""
        paquetes_reales = [p for p in paquetes if not p.startswith("-")]

        if not paquetes_reales:
            self._buffer.put("E: No packages specified\n")
            return

        for paq in paquetes_reales:
            if paq not in self._instalados:
                self._buffer.put(
                    f"E: Package '{paq}' is not installed\n"
                )
                return

        paq = paquetes_reales[0]
        info = self.PAQUETES_DISPONIBLES.get(paq, {})
        version = info.get("version", "unknown")
        self._procesando = True

        lineas = [
            ("Reading package lists... ", 0.4),
            ("Done\n", 0.3),
            ("Building dependency tree... ", 0.4),
            ("Done\n", 0.2),
            (
                f"The following packages will be \033[1;31mREMOVED\033[0m:\n"
                f"  {paq}\n",
                0.3,
            ),
            (
                "0 upgraded, 0 newly installed, 1 to remove "
                "and 0 not upgraded.\n",
                0.3,
            ),
            (
                f"\033[1;33m(Reading database ... "
                "45832 files and directories currently installed.)\033[0m\n",
                0.4,
            ),
            (
                f"Removing {paq} ({version}) ...\n",
                0.6,
            ),
            (
                "Processing triggers for man-db (2.10.2-1) ...\n",
                0.3,
            ),
        ]

        delay_acum = 0.0
        for texto, delay in lineas:
            delay_acum += delay
            threading.Timer(
                delay_acum,
                lambda t=texto: self._buffer.put(t),
            ).start()

        def _completar_desinstalacion() -> None:
            self._instalados.discard(paq)
            # Quitar del filesystem virtual
            usr_bin = self._obtener_nodo("/usr/bin")
            if isinstance(usr_bin, dict) and paq in usr_bin:
                del usr_bin[paq]

            self._procesando = False

            if self._on_uninstall:
                self._on_uninstall(paq)

        threading.Timer(delay_acum + 0.3, _completar_desinstalacion).start()

    def _apt_list(self, args: list[str]) -> None:
        """Lista paquetes instalados o disponibles."""
        if "--installed" in args:
            if not self._instalados:
                self._buffer.put("No packages installed via apt.\n")
            else:
                self._buffer.put("Listing... Done\n")
                for paq in sorted(self._instalados):
                    info = self.PAQUETES_DISPONIBLES.get(paq, {})
                    version = info.get("version", "?")
                    self._buffer.put(
                        f"{paq}/{version} [installed]\n"
                    )
        else:
            self._buffer.put("Listing... Done\n")
            for paq, info in sorted(self.PAQUETES_DISPONIBLES.items()):
                estado = (
                    "\033[1;32m[installed]\033[0m"
                    if paq in self._instalados
                    else "[available]"
                )
                self._buffer.put(
                    f"{paq}/{info['version']} {estado} - "
                    f"{info['desc']}\n"
                )

    def _fin_procesamiento(self) -> None:
        """Marca el fin de un procesamiento asíncrono."""
        self._procesando = False


# ======================================================================
# Terminal Integrada
# ======================================================================

class TerminalIntegrada:
    """Terminal integrada con soporte de pseudo-terminal (PTY).

    En Linux utiliza PTY real para una shell interactiva.
    En otras plataformas utiliza un shell simulado con
    filesystem virtual y comandos básicos de Linux.

    Attributes:
        timeout: Segundos de espera para lectura de salida.
        shell: Ruta al shell a utilizar.
    """

    def __init__(
        self,
        timeout: float = 1.0,
        shell: str = "/bin/bash",
        on_programa_instalado: Optional[Callable[[str], None]] = None,
        on_programa_desinstalado: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Inicializa la terminal integrada.

        Args:
            timeout: Timeout en segundos para operaciones de lectura.
            shell: Ruta al intérprete de shell.
            on_programa_instalado: Callback al instalar un programa.
            on_programa_desinstalado: Callback al desinstalar un programa.
        """
        self.timeout: float = timeout
        self.shell: str = shell

        self._master_fd: Optional[int] = None
        self._slave_fd: Optional[int] = None
        self._proceso: Optional[subprocess.Popen[bytes]] = None
        self._activa: bool = False

        # Modo simulado para plataformas sin PTY
        self._modo_simulado: bool = not _ES_LINUX
        self._shell_simulado: Optional[_ShellSimulado] = None

        # Callbacks
        self._on_programa_instalado = on_programa_instalado
        self._on_programa_desinstalado = on_programa_desinstalado

        logger.info(
            "TerminalIntegrada inicializada (plataforma=%s, modo=%s)",
            platform.system(),
            "simulado" if self._modo_simulado else "PTY",
        )

    # ------------------------------------------------------------------
    # API Pública — Aliases para compatibilidad con la GUI
    # ------------------------------------------------------------------

    def iniciar(self) -> ResultadoOperacion:
        """Inicia la terminal (simulada o PTY según plataforma).

        Returns:
            ResultadoOperacion indicando si se inició correctamente.
        """
        if self._modo_simulado:
            return self._iniciar_simulado()
        return self.iniciar_sesion()

    def enviar_comando(self, comando: str) -> None:
        """Envía un comando a la terminal.

        En modo simulado procesa el comando internamente.
        En modo PTY envía el texto al master fd.

        Args:
            comando: Comando a ejecutar.
        """
        if self._modo_simulado:
            if self._shell_simulado:
                self._shell_simulado.ejecutar(comando)
        else:
            try:
                self.enviar_entrada(comando + "\n")
            except Exception:
                pass

    def detener(self) -> ResultadoOperacion:
        """Detiene la terminal y libera recursos.

        Returns:
            ResultadoOperacion confirmando el cierre.
        """
        if self._modo_simulado:
            return self._detener_simulado()
        return self.cerrar_sesion()

    def esta_procesando(self) -> bool:
        """Verifica si hay un comando en proceso (async).

        Returns:
            True si un comando aún está produciendo salida.
        """
        if self._modo_simulado and self._shell_simulado:
            return self._shell_simulado._procesando
        return False

    def get_prompt(self) -> str:
        """Obtiene el prompt actual del shell.

        Returns:
            String del prompt formateado.
        """
        if self._modo_simulado and self._shell_simulado:
            return self._shell_simulado.get_prompt()
        return "$ "

    def obtener_programas_instalados(self) -> set[str]:
        """Retorna el set de programas instalados via apt.

        Returns:
            Conjunto de nombres de paquetes instalados.
        """
        if self._shell_simulado:
            return self._shell_simulado._instalados.copy()
        return set()

    # ------------------------------------------------------------------
    # Métodos del modo simulado
    # ------------------------------------------------------------------

    def _iniciar_simulado(self) -> ResultadoOperacion:
        """Inicia el shell simulado."""
        self._shell_simulado = _ShellSimulado(
            on_install=self._on_programa_instalado,
            on_uninstall=self._on_programa_desinstalado,
        )
        self._shell_simulado.iniciar()
        self._activa = True

        return ResultadoOperacion(
            exito=True,
            mensaje="Terminal simulada iniciada",
            datos={"modo": "simulado"},
            codigo_error=0,
        )

    def _detener_simulado(self) -> ResultadoOperacion:
        """Detiene el shell simulado."""
        if self._shell_simulado:
            self._shell_simulado.detener()
        self._activa = False

        return ResultadoOperacion(
            exito=True,
            mensaje="Terminal simulada cerrada",
            datos=None,
            codigo_error=0,
        )

    # ------------------------------------------------------------------
    # API Pública Original (PTY)
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

        Returns:
            ResultadoOperacion con el texto disponible.
        """
        # Modo simulado
        if self._modo_simulado:
            if self._shell_simulado:
                salida = self._shell_simulado.leer()
                return ResultadoOperacion(
                    exito=True,
                    mensaje="OK",
                    datos=salida,
                    codigo_error=0,
                )
            return ResultadoOperacion(
                exito=False,
                mensaje="Shell simulado no inicializado",
                datos="",
                codigo_error=510,
            )

        # Modo PTY
        self._verificar_plataforma()
        self._verificar_sesion_activa()

        try:
            salida = self._leer_master()
            tiene_datos = len(salida) > 0

            return ResultadoOperacion(
                exito=True,
                mensaje="Salida leída" if tiene_datos else "Sin datos disponibles",
                datos=salida,
                codigo_error=0,
            )

        except OSError as e:
            logger.error("Error al leer salida: %s", e)
            return ResultadoOperacion(
                exito=False,
                mensaje=f"Error al leer salida de la terminal: {e}",
                datos="",
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
                "modo": "simulado" if self._modo_simulado else "pty",
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
