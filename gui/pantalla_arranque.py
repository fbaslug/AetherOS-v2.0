"""Pantalla de arranque (Boot Screen) animada.

Se muestra al iniciar la GUI, simulando la carga de los subsistemas.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable

from core.sistema import SistemaAetherOS
from gui import tema


class PantallaArranque(tk.Frame):
    """Pantalla de carga inicial."""

    def __init__(
        self,
        parent: tk.Widget,
        sistema: SistemaAetherOS,
        on_complete: Callable[[], None]
    ) -> None:
        super().__init__(parent, bg=tema.FONDO_PRINCIPAL)
        self.sistema = sistema
        self.on_complete = on_complete

        # Logo / Título
        self.lbl_logo = tk.Label(
            self,
            text="AetherOS",
            font=("Segoe UI", 48, "bold"),
            bg=tema.FONDO_PRINCIPAL,
            fg=tema.ACENTO,
        )
        self.lbl_logo.pack(expand=True, pady=(0, 20))

        self.lbl_version = tk.Label(
            self,
            text=f"v{sistema.VERSION}",
            font=("Segoe UI", 16),
            bg=tema.FONDO_PRINCIPAL,
            fg=tema.TEXTO_SECUNDARIO,
        )
        self.lbl_version.place(relx=0.5, rely=0.55, anchor=tk.CENTER)

        # Estado de carga
        self.lbl_estado = tk.Label(
            self,
            text="Iniciando...",
            font=tema.FUENTE_PRINCIPAL,
            bg=tema.FONDO_PRINCIPAL,
            fg=tema.TEXTO,
        )
        self.lbl_estado.pack(side=tk.BOTTOM, pady=(0, 10))

        # Barra de progreso
        estilo = ttk.Style()
        estilo.configure(
            "TProgressbar",
            troughcolor=tema.FONDO_SECUNDARIO,
            background=tema.ACENTO,
            thickness=4,
        )
        
        self.progreso = ttk.Progressbar(
            self,
            orient=tk.HORIZONTAL,
            length=400,
            mode='determinate',
            style="TProgressbar",
        )
        self.progreso.pack(side=tk.BOTTOM, pady=(0, 40))

        # Secuencia de carga simulada
        self._pasos = [
            ("Inicializando Kernel...", 10),
            ("Montando Sistema de Archivos (Sandbox)...", 30),
            ("Configurando Memoria Virtual...", 50),
            ("Iniciando Planificador de Procesos...", 70),
            ("Detectando Dispositivos de E/S...", 90),
            ("Levantando Entorno de Escritorio...", 100),
        ]
        self._paso_actual = 0

    def iniciar_animacion(self) -> None:
        """Inicia el proceso de arranque simulado."""
        self._avanzar_paso()

    def _avanzar_paso(self) -> None:
        if self._paso_actual < len(self._pasos):
            mensaje, porcentaje = self._pasos[self._paso_actual]
            self.lbl_estado.configure(text=mensaje)
            self.progreso["value"] = porcentaje
            self._paso_actual += 1
            
            # Velocidad de carga (ms)
            self.after(400, self._avanzar_paso)
        else:
            # Terminado
            self.lbl_estado.configure(text="¡Listo!", fg=tema.EXITO)
            self.after(500, self._completar)

    def _completar(self) -> None:
        # Iniciar sistema subyacente si no estaba activo
        if not self.sistema.esta_activo():
            self.sistema.iniciar()
        self.on_complete()
