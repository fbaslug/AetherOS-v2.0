"""Barra de tareas inferior del escritorio.

Contiene el botón de menú principal, los botones de acceso a
ventanas minimizadas o activas, y un monitor del sistema (reloj,
indicador de memoria y procesos).
"""

import time
import tkinter as tk
from typing import Callable, Optional

from core.sistema import SistemaAetherOS
from gui import tema


class BarraTareas(tk.Frame):
    """Barra de tareas inferior del escritorio."""

    def __init__(
        self,
        parent: tk.Widget,
        sistema: SistemaAetherOS,
        on_menu_click: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent, bg=tema.FONDO_SECUNDARIO, height=40)
        self.pack_propagate(False)
        self.sistema = sistema

        # Botón Inicio
        self.btn_inicio = tk.Button(
            self,
            text="⧉ AetherOS",
            bg=tema.FONDO_PRINCIPAL,
            fg=tema.ACENTO,
            activebackground=tema.ACENTO_HOVER,
            activeforeground=tema.FONDO_PRINCIPAL,
            bd=0,
            relief=tk.FLAT,
            font=("Segoe UI", 11, "bold"),
            padx=15,
            command=on_menu_click,
        )
        self.btn_inicio.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=4)

        # Contenedor de apps abiertas
        self.contenedor_apps = tk.Frame(self, bg=tema.FONDO_SECUNDARIO)
        self.contenedor_apps.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        # Monitor del sistema (Lado derecho)
        self.panel_monitor = tk.Frame(self, bg=tema.FONDO_SECUNDARIO)
        self.panel_monitor.pack(side=tk.RIGHT, fill=tk.Y, padx=10)

        self.lbl_metricas = tk.Label(
            self.panel_monitor,
            text="Procesos: 0 | Mem: 0%",
            bg=tema.FONDO_SECUNDARIO,
            fg=tema.TEXTO_SECUNDARIO,
            font=("Segoe UI", 9),
        )
        self.lbl_metricas.pack(side=tk.LEFT, padx=10)

        self.lbl_reloj = tk.Label(
            self.panel_monitor,
            text="00:00:00",
            bg=tema.FONDO_SECUNDARIO,
            fg=tema.TEXTO,
            font=("Segoe UI", 10, "bold"),
        )
        self.lbl_reloj.pack(side=tk.LEFT)

        # Diccionario para mantener referencias a los botones de ventanas
        self._botones_ventanas: dict[str, tk.Button] = {}

    def actualizar_monitor(self) -> None:
        """Actualiza el reloj y las métricas del sistema."""
        hora_actual = time.strftime("%H:%M:%S")
        self.lbl_reloj.configure(text=hora_actual)

        # Obtener estado de forma segura sin bloquear UI
        if self.sistema.esta_activo():
            try:
                res_proc = self.sistema.procesos.obtener_estadisticas()
                res_mem = self.sistema.memoria.obtener_uso_memoria()
                
                procs = res_proc.get("datos", {}).get("procesos_activos", 0)
                mem = res_mem.get("datos", {}).get("porcentaje_uso", 0)
                
                self.lbl_metricas.configure(text=f"Procesos: {procs} | Mem: {mem}%")
            except Exception:
                pass

    def registrar_ventana(self, id_ventana: str, titulo: str, icono: str, on_click: Callable) -> None:
        """Añade un botón a la barra de tareas para una ventana."""
        if id_ventana in self._botones_ventanas:
            return

        btn = tk.Button(
            self.contenedor_apps,
            text=f"{icono} {titulo}",
            bg=tema.FONDO_ALT,
            fg=tema.TEXTO,
            activebackground=tema.ACENTO,
            activeforeground=tema.FONDO_PRINCIPAL,
            bd=0,
            relief=tk.FLAT,
            font=tema.FUENTE_PRINCIPAL,
            padx=10,
            command=on_click,
        )
        btn.pack(side=tk.LEFT, fill=tk.Y, padx=2, pady=5)
        self._botones_ventanas[id_ventana] = btn

    def quitar_ventana(self, id_ventana: str) -> None:
        """Elimina el botón de la ventana de la barra de tareas."""
        if id_ventana in self._botones_ventanas:
            self._botones_ventanas[id_ventana].destroy()
            del self._botones_ventanas[id_ventana]
