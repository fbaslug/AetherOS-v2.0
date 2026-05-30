"""Interfaz gráfica para la Terminal Integrada.

Emula una ventana de consola. En sistemas Linux con soporte PTY
interactúa con una shell real. En otros sistemas muestra un error.
"""

import tkinter as tk
from tkinter import messagebox

from servicios.terminal_module import TerminalIntegrada
from gui import tema
from gui.ventana_base import VentanaInterna


class TerminalApp(VentanaInterna):
    """Aplicación de Emulador de Terminal."""

    def __init__(self, parent: tk.Widget, terminal: TerminalIntegrada) -> None:
        super().__init__(
            parent,
            titulo="Terminal",
            ancho=700,
            alto=450,
            icono="⌨️"
        )
        self.terminal = terminal

        # Área de Texto (Scrollable)
        frame_texto = tk.Frame(self.area_contenido, bg=tema.FONDO_PRINCIPAL)
        frame_texto.pack(fill=tk.BOTH, expand=True)

        self.txt_salida = tk.Text(
            frame_texto,
            bg="#000000",          # Negro puro para terminal
            fg="#00ff00",          # Verde matrix
            font=("Consolas", 11),
            insertbackground="#00ff00",
            state=tk.NORMAL
        )
        self.txt_salida.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(frame_texto, command=self.txt_salida.yview)
        self.txt_salida.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Capturar pulsaciones de teclado directamente en el Text widget
        self.txt_salida.bind("<Return>", self._on_enter)
        self.txt_salida.bind("<Key>", self._on_key)

        # Iniciar backend
        res = self.terminal.iniciar()
        if not res["exito"]:
            self._escribir(f"ERROR: {res['mensaje']}\n")
            self.txt_salida.configure(state=tk.DISABLED)
        else:
            self._escribir("AetherOS Terminal v2.0\n")
            self._escribir("Escribe 'exit' para cerrar la terminal.\n\n")
            self._iniciar_loop_lectura()

        self._comando_actual = ""

    def _escribir(self, texto: str) -> None:
        self.txt_salida.insert(tk.END, texto)
        self.txt_salida.see(tk.END)

    def _on_enter(self, event) -> str:
        # Enviar comando cuando se presiona Enter
        cmd = self.txt_salida.get("insert linestart", "insert lineend")
        
        # Limpiar prompt si existe en la línea
        # (Esto es un hack visual básico; el PTY real maneja su propio echo)
        self.txt_salida.insert(tk.END, "\n")
        
        if cmd.strip():
            # Extraer solo lo escrito al final si es necesario (el pty maneja esto, pero enviamos todo lo modificado)
            self.terminal.enviar_comando(cmd + "\n")
            
        return "break" # Evitar salto de línea por defecto de Tkinter

    def _on_key(self, event) -> None:
        # Aquí se podría mejorar la interacción directa con PTY caracter por caracter,
        # pero para simplicidad dejamos que Tkinter bufferice la línea hasta presionar Enter.
        pass

    def _iniciar_loop_lectura(self) -> None:
        if not self.winfo_exists():
            return

        res = self.terminal.leer_salida()
        if res["exito"] and res["datos"]:
            self._escribir(res["datos"])

        self.after(100, self._iniciar_loop_lectura)

    def cerrar(self) -> None:
        # Limpiar terminal al cerrar
        self.terminal.detener()
        super().cerrar()
