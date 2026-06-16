"""Área principal del escritorio que contiene los iconos de aplicaciones.

Gestiona el layout de los iconos de acceso directo y el fondo visual.
"""

import tkinter as tk
from typing import Callable, Optional

from gui import tema


class Escritorio(tk.Frame):
    """Contenedor principal del escritorio.

    Muestra el fondo y los accesos directos a las aplicaciones.
    """

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent, bg=tema.FONDO_PRINCIPAL)
        self._iconos_activos: list[tk.Frame] = []
        self._iconos_por_nombre: dict[str, tk.Frame] = {}

    def agregar_icono(self, icono: str, titulo: str, comando: Callable[[], None]) -> None:
        """Agrega un icono clickeable al escritorio.

        Organiza los iconos en una cuadrícula.
        """
        contenedor = tk.Frame(self, bg=tema.FONDO_PRINCIPAL, width=100, height=100)
        # Forzar tamaño del frame
        contenedor.pack_propagate(False)
        
        lbl_icono = tk.Label(
            contenedor,
            text=icono,
            font=("Segoe UI", 36),
            bg=tema.FONDO_PRINCIPAL,
            fg=tema.ACENTO,
            cursor="hand2",
        )
        lbl_icono.pack(pady=(10, 5))
        
        lbl_titulo = tk.Label(
            contenedor,
            text=titulo,
            font=("Segoe UI", 9),
            bg=tema.FONDO_PRINCIPAL,
            fg=tema.TEXTO,
            wraplength=90,
            justify=tk.CENTER,
            cursor="hand2",
        )
        lbl_titulo.pack()

        # Efecto hover
        def _on_enter(e) -> None:
            lbl_icono.configure(fg=tema.ACENTO_HOVER)
            lbl_titulo.configure(fg=tema.TEXTO)
            contenedor.configure(bg=tema.FONDO_ALT)
            lbl_icono.configure(bg=tema.FONDO_ALT)
            lbl_titulo.configure(bg=tema.FONDO_ALT)

        def _on_leave(e) -> None:
            lbl_icono.configure(fg=tema.ACENTO)
            lbl_titulo.configure(fg=tema.TEXTO_SECUNDARIO)
            contenedor.configure(bg=tema.FONDO_PRINCIPAL)
            lbl_icono.configure(bg=tema.FONDO_PRINCIPAL)
            lbl_titulo.configure(bg=tema.FONDO_PRINCIPAL)

        # Vincular eventos a todos los elementos
        for widget in (contenedor, lbl_icono, lbl_titulo):
            widget.bind("<Enter>", _on_enter)
            widget.bind("<Leave>", _on_leave)
            widget.bind("<Button-1>", lambda e: comando())

        # Registrar en las colecciones
        self._iconos_activos.append(contenedor)
        self._iconos_por_nombre[titulo] = contenedor

        # Actualizar posiciones
        self._recalcular_layout()

    def quitar_icono(self, titulo: str) -> None:
        """Elimina un icono del escritorio por su título."""
        if titulo in self._iconos_por_nombre:
            widget = self._iconos_por_nombre.pop(titulo)
            if widget in self._iconos_activos:
                self._iconos_activos.remove(widget)
            widget.destroy()
            self._recalcular_layout()

    def _recalcular_layout(self) -> None:
        """Recalcula y aplica las posiciones de todos los iconos."""
        # Límite de iconos por columna antes de pasar a la siguiente (5 iconos por columna)
        max_por_columna = 5
        
        for idx, widget in enumerate(self._iconos_activos):
            col = idx // max_por_columna
            row = idx % max_por_columna
            
            x_pos = 20 + (col * 110)
            y_pos = 20 + (row * 120)
            
            widget.place(x=x_pos, y=y_pos)
