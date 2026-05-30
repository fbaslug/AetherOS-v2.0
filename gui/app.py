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

# Importaciones retrasadas de aplicaciones
# from gui.explorador_archivos import ExploradorArchivos
# from gui.admin_procesos import AdminProcesos
# from gui.monitor_memoria import MonitorMemoria
# from gui.gestor_dispositivos import GestorDispositivos
# from gui.terminal_gui import TerminalApp


class AetherOSApp(tk.Tk):
    """Ventana principal y controlador del escritorio."""

    def __init__(self, sistema: SistemaAetherOS) -> None:
        super().__init__()
        self.sistema = sistema
        self.gestor_archivos = GestorArchivos()
        self.terminal_backend = TerminalIntegrada()

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

        # Agregar iconos
        self.escritorio.agregar_icono("📁", "Archivos", self.abrir_explorador)
        self.escritorio.agregar_icono("📊", "Procesos", self.abrir_procesos)
        self.escritorio.agregar_icono("💾", "Memoria", self.abrir_memoria)
        self.escritorio.agregar_icono("🖧", "Dispositivos", self.abrir_dispositivos)
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
            self._registrar_app("dispositivos", "Dispositivos", "🖧", v)
        else:
            self.ventanas_abiertas["dispositivos"].restaurar()

    def abrir_terminal(self) -> None:
        from gui.terminal_gui import TerminalApp
        if "terminal" not in self.ventanas_abiertas:
            v = TerminalApp(self, self.terminal_backend)
            self._registrar_app("terminal", "Terminal", "⌨️", v)
        else:
            self.ventanas_abiertas["terminal"].restaurar()


def lanzar_gui(sistema: SistemaAetherOS) -> None:
    """Entry point para la interfaz gráfica."""
    app = AetherOSApp(sistema)
    app.mainloop()
