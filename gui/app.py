"""Controlador principal de la GUI de AetherOS.

Administra la ventana principal de Tkinter, gestiona la transición
entre la pantalla de arranque y el escritorio, y provee los métodos
para lanzar las aplicaciones integradas.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from core.sistema import SistemaAetherOS
from servicios.interfaz import GestorArchivos
from servicios.terminal_module import TerminalIntegrada

from gui import tema
from gui.barra_tareas import BarraTareas
from gui.escritorio import Escritorio
from gui.pantalla_arranque import PantallaArranque


class AetherOSApp(tk.Tk):
    """Ventana principal y controlador del escritorio."""

    # Mapeo de paquetes apt a metadatos de aplicación de escritorio
    _APP_MAP: dict[str, dict[str, str]] = {
        "nano": {
            "titulo": "nano",
            "icono": "📝",
            "id": "nano",
        },
        "calc": {
            "titulo": "Calculadora",
            "icono": "🧮",
            "id": "calc",
        },
    }

    def __init__(self, sistema: SistemaAetherOS) -> None:
        super().__init__()
        self.sistema = sistema
        self.gestor_archivos = GestorArchivos()

        # Terminal con callbacks de instalación/desinstalación
        self.terminal_backend = TerminalIntegrada(
            on_programa_instalado=self._on_programa_instalado,
            on_programa_desinstalado=self._on_programa_desinstalado,
        )

        # Configuración de ventana base
        self.title("AetherOS v2.0")
        self.geometry("1024x768")
        self.configure(bg=tema.FONDO_PRINCIPAL)
        
        # Intentar modo pantalla completa o maximizado
        try:
            self.attributes("-zoomed", True)
        except Exception:
            self.state("zoomed")
            
        # Ocultar barra de menús del sistema si es posible
        self.option_add('*tearOff', tk.FALSE)

        # Configurar estilos base
        estilo = ttk.Style(self)
        tema.configurar_estilos_ttk(estilo)

        # Contenedores principales
        self.vista_actual: Optional[tk.Frame] = None
        self.barra_tareas: Optional[BarraTareas] = None
        self.escritorio: Optional[Escritorio] = None

        # Estado de ventanas abiertas
        self.ventanas_abiertas: dict[str, tk.Toplevel] = {}

        # Iniciar con pantalla de arranque
        self.mostrar_arranque()

    def mostrar_arranque(self) -> None:
        """Muestra la pantalla de carga animada."""
        if self.vista_actual:
            self.vista_actual.destroy()

        arranque = PantallaArranque(self, self.sistema, on_complete=self.mostrar_escritorio)
        arranque.pack(fill=tk.BOTH, expand=True)
        self.vista_actual = arranque
        arranque.iniciar_animacion()

    def mostrar_escritorio(self) -> None:
        """Carga y muestra el escritorio y la barra de tareas."""
        if self.vista_actual:
            self.vista_actual.destroy()

        # Barra de tareas (inferior)
        self.barra_tareas = BarraTareas(
            self,
            self.sistema,
            on_menu_click=self.toggle_menu_inicio
        )
        self.barra_tareas.pack(side=tk.BOTTOM, fill=tk.X)

        # Escritorio (resto del espacio)
        self.escritorio = Escritorio(self)
        self.escritorio.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.vista_actual = self.escritorio

        # Agregar iconos de aplicaciones del sistema
        self.escritorio.agregar_icono("📁", "Archivos", self.abrir_explorador)
        self.escritorio.agregar_icono("📊", "Procesos", self.abrir_procesos)
        self.escritorio.agregar_icono("💾", "Memoria", self.abrir_memoria)
        self.escritorio.agregar_icono("🖥", "Dispositivos", self.abrir_dispositivos)
        self.escritorio.agregar_icono("⌨️", "Terminal", self.abrir_terminal)

        # Iniciar loop de monitorización (cada 1s)
        self._loop_monitor()

    def toggle_menu_inicio(self) -> None:
        """Muestra u oculta el menú de inicio."""
        # TODO: Implementar menú inicio desplegable
        print("Menú inicio presionado")

    def _loop_monitor(self) -> None:
        """Actualiza métricas del sistema periódicamente."""
        if self.barra_tareas:
            self.barra_tareas.actualizar_monitor()
        self.after(1000, self._loop_monitor)

    # ------------------------------------------------------------------
    # Callbacks de Instalación / Desinstalación
    # ------------------------------------------------------------------

    def _on_programa_instalado(self, nombre_paquete: str) -> None:
        """Callback invocado cuando se instala un programa via apt.

        Se ejecuta en hilo de temporizador, por lo que usamos
        ``self.after()`` para operar en el hilo principal de Tkinter.
        """
        self.after(0, lambda: self._agregar_app_escritorio(nombre_paquete))

    def _on_programa_desinstalado(self, nombre_paquete: str) -> None:
        """Callback invocado cuando se desinstala un programa via apt.

        Se ejecuta en hilo de temporizador, por lo que usamos
        ``self.after()`` para operar en el hilo principal de Tkinter.
        """
        self.after(0, lambda: self._quitar_app_escritorio(nombre_paquete))

    def _agregar_app_escritorio(self, nombre_paquete: str) -> None:
        """Agrega un icono al escritorio para un programa instalado."""
        app_info = self._APP_MAP.get(nombre_paquete)
        if not app_info or not self.escritorio:
            return

        titulo = app_info["titulo"]

        # Verificar que no exista ya
        if titulo in self.escritorio._iconos_por_nombre:
            return

        # Determinar el comando de apertura
        if nombre_paquete == "nano":
            comando = self.abrir_nano
        elif nombre_paquete == "calc":
            comando = self.abrir_calc
        else:
            return

        self.escritorio.agregar_icono(
            app_info["icono"],
            titulo,
            comando,
        )

    def _quitar_app_escritorio(self, nombre_paquete: str) -> None:
        """Quita el icono del escritorio de un programa desinstalado."""
        app_info = self._APP_MAP.get(nombre_paquete)
        if not app_info or not self.escritorio:
            return

        titulo = app_info["titulo"]
        id_app = app_info["id"]

        # Quitar icono del escritorio
        self.escritorio.quitar_icono(titulo)

        # Cerrar la ventana si está abierta
        if id_app in self.ventanas_abiertas:
            try:
                self.ventanas_abiertas[id_app].cerrar()
            except Exception:
                pass
            if id_app in self.ventanas_abiertas:
                del self.ventanas_abiertas[id_app]
            if self.barra_tareas:
                self.barra_tareas.quitar_ventana(id_app)

    # ------------------------------------------------------------------
    # Lanzadores de Aplicaciones
    # ------------------------------------------------------------------

    def _registrar_app(self, id_app: str, titulo: str, icono: str, ventana) -> None:
        """Registra la ventana en el sistema y barra de tareas."""
        self.ventanas_abiertas[id_app] = ventana
        
        # Callback cuando se cierra la ventana
        def on_close():
            if id_app in self.ventanas_abiertas:
                del self.ventanas_abiertas[id_app]
            if self.barra_tareas:
                self.barra_tareas.quitar_ventana(id_app)
                
        # Inyectar callback a la ventana_base
        ventana._on_close_callback = on_close
        
        # Registrar en barra de tareas
        if self.barra_tareas:
            self.barra_tareas.registrar_ventana(
                id_app, titulo, icono, ventana.restaurar
            )

    def abrir_explorador(self) -> None:
        from gui.explorador_archivos import ExploradorArchivos
        if "archivos" not in self.ventanas_abiertas:
            v = ExploradorArchivos(self, self.gestor_archivos)
            self._registrar_app("archivos", "Archivos", "📁", v)
        else:
            self.ventanas_abiertas["archivos"].restaurar()

    def abrir_procesos(self) -> None:
        from gui.admin_procesos import AdminProcesos
        if "procesos" not in self.ventanas_abiertas:
            v = AdminProcesos(self, self.sistema.procesos)
            self._registrar_app("procesos", "Procesos", "📊", v)
        else:
            self.ventanas_abiertas["procesos"].restaurar()

    def abrir_memoria(self) -> None:
        from gui.monitor_memoria import MonitorMemoria
        if "memoria" not in self.ventanas_abiertas:
            v = MonitorMemoria(self, self.sistema.memoria)
            self._registrar_app("memoria", "Memoria", "💾", v)
        else:
            self.ventanas_abiertas["memoria"].restaurar()

    def abrir_dispositivos(self) -> None:
        from gui.gestor_dispositivos import GestorDispositivos
        if "dispositivos" not in self.ventanas_abiertas:
            v = GestorDispositivos(self, self.sistema.dispositivos)
            self._registrar_app("dispositivos", "Dispositivos", "🖥", v)
        else:
            self.ventanas_abiertas["dispositivos"].restaurar()

    def abrir_terminal(self) -> None:
        from gui.terminal_gui import TerminalApp
        if "terminal" not in self.ventanas_abiertas:
            v = TerminalApp(self, self.terminal_backend)
            self._registrar_app("terminal", "Terminal", "⌨️", v)
        else:
            self.ventanas_abiertas["terminal"].restaurar()

    def abrir_nano(self) -> None:
        """Abre el editor de texto nano (instalado via apt)."""
        from gui.nano_app import NanoApp
        if "nano" not in self.ventanas_abiertas:
            v = NanoApp(self)
            self._registrar_app("nano", "nano", "📝", v)
        else:
            self.ventanas_abiertas["nano"].restaurar()

    def abrir_calc(self) -> None:
        """Abre la calculadora (instalada via apt)."""
        from gui.calc_app import CalcApp
        if "calc" not in self.ventanas_abiertas:
            v = CalcApp(self)
            self._registrar_app("calc", "Calculadora", "🧮", v)
        else:
            self.ventanas_abiertas["calc"].restaurar()


def lanzar_gui(sistema: SistemaAetherOS) -> None:
    """Entry point para la interfaz gráfica."""
    app = AetherOSApp(sistema)
    app.mainloop()
