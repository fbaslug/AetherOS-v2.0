"""Interfaz gráfica para la Terminal Integrada.

Emula una ventana de consola interactiva con prompt, entrada de
comandos, historial de navegación, y soporte para códigos ANSI
básicos. Funciona tanto en modo PTY (Linux) como en modo simulado.
"""

import re
import tkinter as tk
from tkinter import messagebox
from typing import Optional

from servicios.terminal_module import TerminalIntegrada
from gui import tema
from gui.ventana_base import VentanaInterna


# Mapeo de códigos ANSI a tags de Tkinter
_ANSI_COLORES: dict[str, dict[str, str]] = {
    "30": {"foreground": "#1c2128"},      # Negro
    "31": {"foreground": "#f85149"},      # Rojo
    "32": {"foreground": "#3fb950"},      # Verde
    "33": {"foreground": "#d29922"},      # Amarillo
    "34": {"foreground": "#58a6ff"},      # Azul
    "35": {"foreground": "#bc8cff"},      # Magenta
    "36": {"foreground": "#00d4ff"},      # Cyan
    "37": {"foreground": "#e6edf3"},      # Blanco
    "0": {"foreground": "#00ff00"},       # Reset (verde terminal)
    "1": {"font": ("Consolas", 11, "bold")},  # Bold
}

_PATRON_ANSI = re.compile(r'\033\[([0-9;]*)m')


class TerminalApp(VentanaInterna):
    """Aplicación de Emulador de Terminal interactiva."""

    def __init__(self, parent: tk.Widget, terminal: TerminalIntegrada) -> None:
        super().__init__(
            parent,
            titulo="Terminal",
            ancho=750,
            alto=480,
            icono="⌨️"
        )
        self.terminal = terminal

        # --- Área de Texto ---
        frame_texto = tk.Frame(self.area_contenido, bg="#000000")
        frame_texto.pack(fill=tk.BOTH, expand=True)

        self.txt = tk.Text(
            frame_texto,
            bg="#0d1117",
            fg="#00ff00",
            font=("Consolas", 11),
            insertbackground="#00ff00",
            selectbackground="#264f78",
            selectforeground="#e6edf3",
            relief=tk.FLAT,
            borderwidth=8,
            wrap=tk.WORD,
            undo=False,
        )
        self.txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(
            frame_texto,
            command=self.txt.yview,
            bg="#161b22",
            troughcolor="#0d1117",
        )
        self.txt.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configurar tags de color ANSI
        self._configurar_tags_ansi()

        # --- Marcador de inicio de entrada ---
        # Todo el texto antes de este mark es "solo lectura"
        self.txt.mark_set("input_start", "end-1c")
        self.txt.mark_gravity("input_start", "left")

        # --- Estado ---
        self._historial: list[str] = []
        self._historial_idx: int = 0
        self._prompt_mostrado: bool = False
        self._comando_temporal: str = ""

        # --- Bindings ---
        self.txt.bind("<Return>", self._on_enter)
        self.txt.bind("<BackSpace>", self._on_backspace)
        self.txt.bind("<Delete>", self._on_delete)
        self.txt.bind("<Key>", self._on_key)
        self.txt.bind("<Up>", self._on_arrow_up)
        self.txt.bind("<Down>", self._on_arrow_down)
        self.txt.bind("<Home>", self._on_home)
        self.txt.bind("<Control-c>", self._on_ctrl_c)
        self.txt.bind("<Control-l>", self._on_ctrl_l)
        # Prevenir pegado antes del prompt
        self.txt.bind("<<Paste>>", self._on_paste)
        # Prevenir seleccionar y borrar zona protegida
        self.txt.bind("<Control-a>", self._on_select_all)

        # --- Iniciar backend ---
        res = self.terminal.iniciar()
        if not res["exito"]:
            self._insertar_texto(f"ERROR: {res['mensaje']}\n", "error")
            self.txt.configure(state=tk.DISABLED)
        else:
            # Iniciar loop de lectura
            self._iniciar_loop_lectura()

        # Foco en el Text widget
        self.txt.focus_set()

    # ------------------------------------------------------------------
    # Tags ANSI
    # ------------------------------------------------------------------

    def _configurar_tags_ansi(self) -> None:
        """Configura los tags de color para secuencias ANSI."""
        for codigo, config in _ANSI_COLORES.items():
            self.txt.tag_configure(f"ansi_{codigo}", **config)

        # Tag especial para errores
        self.txt.tag_configure(
            "error",
            foreground="#f85149",
            font=("Consolas", 11, "bold"),
        )

        # Tag para prompt
        self.txt.tag_configure(
            "prompt_user",
            foreground="#3fb950",
            font=("Consolas", 11, "bold"),
        )
        self.txt.tag_configure(
            "prompt_path",
            foreground="#58a6ff",
            font=("Consolas", 11, "bold"),
        )
        self.txt.tag_configure(
            "prompt_symbol",
            foreground="#e6edf3",
        )

    # ------------------------------------------------------------------
    # Inserción de texto con soporte ANSI
    # ------------------------------------------------------------------

    def _insertar_texto(self, texto: str, tag: Optional[str] = None) -> None:
        """Inserta texto procesando secuencias ANSI básicas."""
        if not texto:
            return

        # Buscar marcador de limpiar pantalla
        if "\x1b[CLEAR]" in texto:
            self.txt.delete("1.0", tk.END)
            texto = texto.replace("\x1b[CLEAR]", "")
            if not texto:
                return

        # Procesar secuencias ANSI
        ultimo_fin = 0
        tag_activo: Optional[str] = tag
        bold_activo = False

        for match in _PATRON_ANSI.finditer(texto):
            # Insertar texto antes de la secuencia
            antes = texto[ultimo_fin:match.start()]
            if antes:
                self.txt.insert(tk.END, antes, tag_activo or ())

            # Procesar código ANSI
            codigos = match.group(1).split(";")
            for codigo in codigos:
                if codigo == "0":
                    tag_activo = None
                    bold_activo = False
                elif codigo == "1":
                    bold_activo = True
                elif codigo in _ANSI_COLORES:
                    if bold_activo:
                        tag_activo = f"ansi_{codigo}"
                    else:
                        tag_activo = f"ansi_{codigo}"

            ultimo_fin = match.end()

        # Insertar texto restante después de la última secuencia
        restante = texto[ultimo_fin:]
        if restante:
            self.txt.insert(tk.END, restante, tag_activo or ())

        self.txt.see(tk.END)

    def _insertar_prompt(self) -> None:
        """Inserta el prompt del shell y posiciona el marcador de entrada."""
        prompt_raw = self.terminal.get_prompt()
        # Procesar prompt con ANSI
        self._insertar_texto(prompt_raw)
        # Posicionar marcador DESPUÉS del prompt
        self.txt.mark_set("input_start", "end-1c")
        self.txt.mark_gravity("input_start", "left")
        self.txt.see(tk.END)
        self._prompt_mostrado = True

    # ------------------------------------------------------------------
    # Loop de lectura de salida
    # ------------------------------------------------------------------

    def _iniciar_loop_lectura(self) -> None:
        """Lee periódicamente la salida del backend."""
        if not self.winfo_exists():
            return

        try:
            res = self.terminal.leer_salida()
            if res["exito"]:
                datos = res.get("datos", "")
                # datos puede ser string o dict
                if isinstance(datos, dict):
                    texto = datos.get("salida", "")
                else:
                    texto = str(datos) if datos else ""

                if texto:
                    self._insertar_texto(texto)
                    self._prompt_mostrado = False

            # Si no está procesando y no hemos mostrado prompt, mostrarlo
            if not self.terminal.esta_procesando() and not self._prompt_mostrado:
                self._insertar_prompt()

        except Exception:
            pass

        self.after(60, self._iniciar_loop_lectura)

    # ------------------------------------------------------------------
    # Manejo de entrada de teclado
    # ------------------------------------------------------------------

    def _on_enter(self, event) -> str:
        """Procesa Enter: extrae comando y lo envía al backend."""
        # Obtener texto escrito por el usuario (después del prompt)
        try:
            cmd = self.txt.get("input_start", "end-1c")
        except tk.TclError:
            cmd = ""

        # Insertar newline
        self.txt.insert(tk.END, "\n")
        self.txt.see(tk.END)

        cmd = cmd.strip()
        if cmd:
            self._historial.append(cmd)
            self._historial_idx = len(self._historial)
            self._prompt_mostrado = False
            self.terminal.enviar_comando(cmd)
        else:
            # Comando vacío, solo mostrar nuevo prompt
            self._prompt_mostrado = False

        return "break"

    def _on_backspace(self, event) -> str:
        """Previene borrar más allá del prompt."""
        try:
            if self.txt.compare("insert", "<=", "input_start"):
                return "break"
        except tk.TclError:
            pass
        return ""

    def _on_delete(self, event) -> str:
        """Previene Delete en zona protegida."""
        try:
            if self.txt.compare("insert", "<", "input_start"):
                return "break"
        except tk.TclError:
            pass
        return ""

    def _on_key(self, event) -> Optional[str]:
        """Maneja pulsaciones de teclado generales."""
        # Ignorar teclas especiales (flechas, funciones, etc.)
        if event.keysym in (
            "Shift_L", "Shift_R", "Control_L", "Control_R",
            "Alt_L", "Alt_R", "Caps_Lock", "Escape",
            "F1", "F2", "F3", "F4", "F5", "F6",
            "F7", "F8", "F9", "F10", "F11", "F12",
            "Up", "Down", "Left", "Right", "Home", "End",
            "Prior", "Next", "Insert",
        ):
            return None

        # Si el cursor está antes del input_start, moverlo al final
        try:
            if self.txt.compare("insert", "<", "input_start"):
                self.txt.mark_set("insert", "end-1c")
        except tk.TclError:
            pass

        return None

    def _on_arrow_up(self, event) -> str:
        """Navega hacia atrás en el historial."""
        if self._historial and self._historial_idx > 0:
            # Guardar comando actual si estamos al final
            if self._historial_idx == len(self._historial):
                try:
                    self._comando_temporal = self.txt.get(
                        "input_start", "end-1c"
                    )
                except tk.TclError:
                    self._comando_temporal = ""

            self._historial_idx -= 1
            self._reemplazar_input(self._historial[self._historial_idx])

        return "break"

    def _on_arrow_down(self, event) -> str:
        """Navega hacia adelante en el historial."""
        if self._historial_idx < len(self._historial):
            self._historial_idx += 1

            if self._historial_idx == len(self._historial):
                self._reemplazar_input(self._comando_temporal)
            else:
                self._reemplazar_input(self._historial[self._historial_idx])

        return "break"

    def _on_home(self, event) -> str:
        """Lleva el cursor al inicio de la zona editable."""
        self.txt.mark_set("insert", "input_start")
        return "break"

    def _on_ctrl_c(self, event) -> str:
        """Simula Ctrl+C: cancela la línea actual."""
        self.txt.insert(tk.END, "^C\n")
        self._prompt_mostrado = False
        return "break"

    def _on_ctrl_l(self, event) -> str:
        """Simula Ctrl+L: limpia la pantalla."""
        self.txt.delete("1.0", tk.END)
        self._prompt_mostrado = False
        return "break"

    def _on_paste(self, event) -> Optional[str]:
        """Maneja pegado en la zona correcta."""
        try:
            if self.txt.compare("insert", "<", "input_start"):
                self.txt.mark_set("insert", "end-1c")
        except tk.TclError:
            pass
        return None

    def _on_select_all(self, event) -> str:
        """Selecciona solo la zona editable."""
        try:
            self.txt.tag_add("sel", "input_start", "end-1c")
        except tk.TclError:
            pass
        return "break"

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _reemplazar_input(self, texto: str) -> None:
        """Reemplaza el texto en la zona editable del prompt."""
        try:
            self.txt.delete("input_start", "end-1c")
            self.txt.insert("input_start", texto)
            self.txt.mark_set("insert", "end-1c")
        except tk.TclError:
            pass

    def cerrar(self) -> None:
        """Cierra la terminal liberando el backend."""
        try:
            self.terminal.detener()
        except Exception:
            pass
        super().cerrar()
