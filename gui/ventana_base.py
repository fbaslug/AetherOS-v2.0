"""Clase base para las ventanas internas (aplicaciones) de AetherOS.

Provee una ventana sin bordes nativos (overrideredirect) con una
barra de título personalizada que permite moverla, minimizarla
y cerrarla.
"""

import tkinter as tk
from typing import Callable, Optional

from gui import tema


class VentanaInterna(tk.Toplevel):
    """Ventana de aplicación simulada en el escritorio.

    Reemplaza la decoración del manejador de ventanas del SO anfitrión
    con una barra de título propia que coincide con el tema de AetherOS.
    """

    def __init__(
        self,
        parent: tk.Widget,
        titulo: str,
        ancho: int = 600,
        alto: int = 400,
        icono: str = "⬛",
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.titulo = titulo
        self.icono = icono
        self._on_close_callback = on_close

        # Eliminar bordes nativos del SO
        self.overrideredirect(True)
        self.configure(bg=tema.ACENTO) # Borde muy fino cyan

        # Posicionar centrada
        screen_w = parent.winfo_screenwidth()
        screen_h = parent.winfo_screenheight()
        x = (screen_w // 2) - (ancho // 2)
        y = (screen_h // 2) - (alto // 2)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")

        # Contenedor principal que deja un borde de 1px
        self.contenedor = tk.Frame(self, bg=tema.FONDO_VENTANA)
        self.contenedor.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Barra de Título
        self.barra_titulo = tk.Frame(self.contenedor, bg=tema.FONDO_SECUNDARIO, height=30)
        self.barra_titulo.pack(fill=tk.X, side=tk.TOP)
        self.barra_titulo.pack_propagate(False)

        # Eventos para arrastrar ventana
        self.barra_titulo.bind("<ButtonPress-1>", self._iniciar_arrastre)
        self.barra_titulo.bind("<B1-Motion>", self._arrastrar)

        # Elementos de la barra
        lbl_icono = tk.Label(
            self.barra_titulo,
            text=self.icono,
            bg=tema.FONDO_SECUNDARIO,
            fg=tema.ACENTO,
            font=tema.FUENTE_PRINCIPAL,
        )
        lbl_icono.pack(side=tk.LEFT, padx=5)

        lbl_titulo = tk.Label(
            self.barra_titulo,
            text=self.titulo,
            bg=tema.FONDO_SECUNDARIO,
            fg=tema.TEXTO,
            font=tema.FUENTE_PRINCIPAL,
        )
        lbl_titulo.pack(side=tk.LEFT)
        lbl_titulo.bind("<ButtonPress-1>", self._iniciar_arrastre)
        lbl_titulo.bind("<B1-Motion>", self._arrastrar)

        # Botón Cerrar
        btn_cerrar = tk.Button(
            self.barra_titulo,
            text="✕",
            bg=tema.FONDO_SECUNDARIO,
            fg=tema.TEXTO_SECUNDARIO,
            activebackground=tema.ERROR,
            activeforeground=tema.TEXTO,
            bd=0,
            relief=tk.FLAT,
            font=("Segoe UI", 10),
            command=self.cerrar,
        )
        btn_cerrar.pack(side=tk.RIGHT, padx=2)

        # Botón Minimizar (Oculta la ventana)
        btn_minimizar = tk.Button(
            self.barra_titulo,
            text="—",
            bg=tema.FONDO_SECUNDARIO,
            fg=tema.TEXTO_SECUNDARIO,
            activebackground=tema.FONDO_ALT,
            activeforeground=tema.TEXTO,
            bd=0,
            relief=tk.FLAT,
            font=("Segoe UI", 10, "bold"),
            command=self.minimizar,
        )
        btn_minimizar.pack(side=tk.RIGHT, padx=2)

        # Área de contenido (donde las subclases agregarán sus widgets)
        self.area_contenido = tk.Frame(self.contenedor, bg=tema.FONDO_VENTANA)
        self.area_contenido.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Variables para arrastre
        self._x_offset = 0
        self._y_offset = 0

        # Forzar el foco
        self.focus_force()

    def _iniciar_arrastre(self, event) -> None:
        """Guarda la posición inicial del clic."""
        self._x_offset = event.x
        self._y_offset = event.y

    def _arrastrar(self, event) -> None:
        """Mueve la ventana según el desplazamiento del ratón."""
        x = self.winfo_x() + event.x - self._x_offset
        y = self.winfo_y() + event.y - self._y_offset
        self.geometry(f"+{x}+{y}")

    def cerrar(self) -> None:
        """Cierra y destruye la ventana, ejecutando callback si existe."""
        if self._on_close_callback:
            self._on_close_callback()
        self.destroy()

    def minimizar(self) -> None:
        """Oculta la ventana (simula minimizar)."""
        self.withdraw()

    def restaurar(self) -> None:
        """Muestra la ventana previamente minimizada."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def agregar_widget(self, widget: tk.Widget) -> None:
        """Método auxiliar para que las subclases agreguen widgets más fácil."""
        widget.pack(fill=tk.BOTH, expand=True)
