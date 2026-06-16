"""Calculadora simple para AetherOS.

Se instala como paquete 'calc' a través de la terminal simulada.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from gui import tema
from gui.ventana_base import VentanaInterna

class CalcApp(VentanaInterna):
    """Aplicación de Calculadora."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(
            parent,
            titulo="Calculadora",
            ancho=300,
            alto=400,
            icono="🧮",
        )

        self.expresion = ""

        # --- Display ---
        frame_display = tk.Frame(self.area_contenido, bg="#0d1117", height=80)
        frame_display.pack(fill=tk.X, padx=10, pady=10)
        frame_display.pack_propagate(False)

        self.lbl_display = tk.Label(
            frame_display,
            text="0",
            bg="#0d1117",
            fg="#e6edf3",
            font=("Consolas", 24, "bold"),
            anchor="e",
            padx=10,
        )
        self.lbl_display.pack(fill=tk.BOTH, expand=True)

        # --- Botones ---
        frame_botones = tk.Frame(self.area_contenido, bg=tema.FONDO_PRINCIPAL)
        frame_botones.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        botones = [
            ('C', 0, 0), ('(', 0, 1), (')', 0, 2), ('/', 0, 3),
            ('7', 1, 0), ('8', 1, 1), ('9', 1, 2), ('*', 1, 3),
            ('4', 2, 0), ('5', 2, 1), ('6', 2, 2), ('-', 2, 3),
            ('1', 3, 0), ('2', 3, 1), ('3', 3, 2), ('+', 3, 3),
            ('0', 4, 0), ('.', 4, 1), ('=', 4, 2, 2)
        ]

        # Configurar grid
        for i in range(5):
            frame_botones.grid_rowconfigure(i, weight=1)
        for i in range(4):
            frame_botones.grid_columnconfigure(i, weight=1)

        for btn in botones:
            texto = btn[0]
            fila = btn[1]
            col = btn[2]
            colspan = btn[3] if len(btn) > 3 else 1

            comando = lambda t=texto: self._presionar(t)
            
            # Colores según el tipo de botón
            bg_color = "#21262d" # default
            fg_color = "#e6edf3"
            if texto in ('C', '(', ')'):
                fg_color = "#f85149"
            elif texto in ('/', '*', '-', '+', '='):
                bg_color = "#238636"
            elif texto.isdigit() or texto == '.':
                bg_color = "#161b22"

            b = tk.Button(
                frame_botones,
                text=texto,
                bg=bg_color,
                fg=fg_color,
                font=("Consolas", 14, "bold"),
                relief=tk.FLAT,
                command=comando,
                activebackground="#30363d",
                activeforeground="#ffffff",
                borderwidth=1
            )
            b.grid(row=fila, column=col, columnspan=colspan, sticky="nsew", padx=2, pady=2)

    def _presionar(self, tecla: str) -> None:
        if tecla == 'C':
            self.expresion = ""
            self.lbl_display.config(text="0")
        elif tecla == '=':
            try:
                # Evitar inyección de código básica
                for c in self.expresion:
                    if c not in "0123456789+-*/().":
                        raise ValueError
                
                if not self.expresion:
                    return
                    
                resultado = str(eval(self.expresion))
                # Limitar decimales si es float
                if '.' in resultado:
                    resultado = f"{float(resultado):.4f}".rstrip('0').rstrip('.')
                    
                self.lbl_display.config(text=resultado)
                self.expresion = resultado
            except Exception:
                self.lbl_display.config(text="Error")
                self.expresion = ""
        else:
            if self.expresion == "Error":
                self.expresion = ""
            self.expresion += tecla
            self.lbl_display.config(text=self.expresion)
