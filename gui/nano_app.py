"""Editor de texto simple estilo nano para AetherOS.

Provee un editor de texto minimalista que se instala como
programa via ``sudo apt install nano`` en la terminal simulada.
"""

import tkinter as tk
from tkinter import messagebox
from typing import Optional

from gui import tema
from gui.ventana_base import VentanaInterna


class NanoApp(VentanaInterna):
    """Editor de texto nano (simulado).

    Editor simple con las funciones básicas: nuevo, abrir (dentro
    del filesystem virtual), guardar, y las combinaciones de teclado
    tradicionales de nano mostradas en la barra inferior.
    """

    def __init__(
        self,
        parent: tk.Widget,
        archivo: Optional[str] = None,
    ) -> None:
        super().__init__(
            parent,
            titulo="nano — Editor de Texto",
            ancho=700,
            alto=480,
            icono="📝",
        )

        self._archivo_actual: Optional[str] = archivo
        self._modificado: bool = False

        # --- Barra de título del editor ---
        frame_header = tk.Frame(
            self.area_contenido,
            bg="#1a1a2e",
            height=28,
        )
        frame_header.pack(fill=tk.X)
        frame_header.pack_propagate(False)

        self.lbl_archivo = tk.Label(
            frame_header,
            text=self._get_titulo_archivo(),
            bg="#1a1a2e",
            fg="#00d4ff",
            font=("Consolas", 10, "bold"),
        )
        self.lbl_archivo.pack(side=tk.LEFT, padx=10)

        self.lbl_estado = tk.Label(
            frame_header,
            text="",
            bg="#1a1a2e",
            fg="#3fb950",
            font=("Consolas", 9),
        )
        self.lbl_estado.pack(side=tk.RIGHT, padx=10)

        # --- Área de edición ---
        frame_editor = tk.Frame(
            self.area_contenido,
            bg="#0d1117",
        )
        frame_editor.pack(fill=tk.BOTH, expand=True)

        # Números de línea
        self.txt_lineas = tk.Text(
            frame_editor,
            bg="#161b22",
            fg="#8b949e",
            font=("Consolas", 11),
            width=4,
            relief=tk.FLAT,
            state=tk.DISABLED,
            takefocus=0,
            borderwidth=4,
        )
        self.txt_lineas.pack(side=tk.LEFT, fill=tk.Y)

        # Editor principal
        self.txt_editor = tk.Text(
            frame_editor,
            bg="#0d1117",
            fg="#e6edf3",
            font=("Consolas", 11),
            insertbackground="#00d4ff",
            selectbackground="#264f78",
            selectforeground="#e6edf3",
            relief=tk.FLAT,
            borderwidth=4,
            wrap=tk.NONE,
            undo=True,
            maxundo=50,
        )
        self.txt_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar_y = tk.Scrollbar(
            frame_editor,
            command=self._on_scroll_y,
            bg="#161b22",
            troughcolor="#0d1117",
        )
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_editor.configure(yscrollcommand=scrollbar_y.set)

        # --- Barra de atajos inferior (estilo nano) ---
        frame_atajos = tk.Frame(
            self.area_contenido,
            bg="#1a1a2e",
            height=48,
        )
        frame_atajos.pack(fill=tk.X, side=tk.BOTTOM)
        frame_atajos.pack_propagate(False)

        atajos = [
            ("^G", "Ayuda"),
            ("^O", "Guardar"),
            ("^X", "Salir"),
            ("^K", "Cortar"),
            ("^U", "Pegar"),
            ("^W", "Buscar"),
        ]

        frame_atajos_inner = tk.Frame(frame_atajos, bg="#1a1a2e")
        frame_atajos_inner.pack(expand=True)

        for tecla, accion in atajos:
            lbl_tecla = tk.Label(
                frame_atajos_inner,
                text=tecla,
                bg="#1a1a2e",
                fg="#00d4ff",
                font=("Consolas", 9, "bold"),
            )
            lbl_tecla.pack(side=tk.LEFT, padx=(8, 0))

            lbl_accion = tk.Label(
                frame_atajos_inner,
                text=accion,
                bg="#1a1a2e",
                fg="#8b949e",
                font=("Consolas", 9),
            )
            lbl_accion.pack(side=tk.LEFT, padx=(2, 8))

        # --- Bindings ---
        self.txt_editor.bind("<KeyRelease>", self._on_key_release)
        self.txt_editor.bind("<Control-o>", self._guardar)
        self.txt_editor.bind("<Control-O>", self._guardar)
        self.txt_editor.bind("<Control-x>", self._salir)
        self.txt_editor.bind("<Control-X>", self._salir)
        self.txt_editor.bind("<Control-k>", self._cortar_linea)
        self.txt_editor.bind("<Control-K>", self._cortar_linea)
        self.txt_editor.bind("<Control-z>", self._deshacer)
        self.txt_editor.bind("<Control-Z>", self._deshacer)

        # Cargar archivo si se especificó
        if archivo:
            self._cargar_archivo(archivo)

        # Actualizar líneas iniciales
        self._actualizar_numeros_linea()
        self.txt_editor.focus_set()

    # ------------------------------------------------------------------
    # Archivo
    # ------------------------------------------------------------------

    def _get_titulo_archivo(self) -> str:
        """Retorna el título del archivo actual."""
        if self._archivo_actual:
            nombre = self._archivo_actual.split("/")[-1]
            mod = " [Modificado]" if self._modificado else ""
            return f"  GNU nano — {nombre}{mod}"
        return "  GNU nano — [Nuevo archivo]"

    def _cargar_archivo(self, ruta: str) -> None:
        """Carga contenido de un archivo (placeholder)."""
        # En una integración completa, se leería del filesystem virtual
        self.txt_editor.delete("1.0", tk.END)
        contenido = (
            f"# Archivo: {ruta}\n"
            "# Edita tu archivo aquí\n"
            "\n"
        )
        self.txt_editor.insert("1.0", contenido)
        self._modificado = False
        self._actualizar_titulo()

    def _guardar(self, event=None) -> str:
        """Simula guardar el archivo."""
        contenido = self.txt_editor.get("1.0", "end-1c")
        lineas = len(contenido.split("\n"))
        chars = len(contenido)

        self._modificado = False
        self._actualizar_titulo()
        self.lbl_estado.configure(
            text=f"Guardado: {lineas} líneas, {chars} caracteres",
            fg="#3fb950",
        )

        # Limpiar mensaje después de 3 segundos
        self.after(
            3000,
            lambda: self.lbl_estado.configure(text="")
            if self.winfo_exists()
            else None,
        )

        return "break"

    def _salir(self, event=None) -> str:
        """Cierra el editor, preguntando si hay cambios sin guardar."""
        if self._modificado:
            respuesta = messagebox.askyesnocancel(
                "nano",
                "¿Guardar cambios antes de salir?",
                parent=self,
            )
            if respuesta is None:  # Cancelar
                return "break"
            if respuesta:  # Sí
                self._guardar()
        self.cerrar()
        return "break"

    # ------------------------------------------------------------------
    # Edición
    # ------------------------------------------------------------------

    def _cortar_linea(self, event=None) -> str:
        """Corta la línea actual."""
        linea_actual = self.txt_editor.index("insert linestart")
        linea_fin = self.txt_editor.index("insert lineend +1c")
        self.txt_editor.delete(linea_actual, linea_fin)
        self._on_key_release(None)
        return "break"

    def _deshacer(self, event=None) -> str:
        """Deshace la última acción."""
        try:
            self.txt_editor.edit_undo()
        except tk.TclError:
            pass
        return "break"

    # ------------------------------------------------------------------
    # UI Updates
    # ------------------------------------------------------------------

    def _on_key_release(self, event) -> None:
        """Actualiza estado al escribir."""
        if not self._modificado:
            self._modificado = True
            self._actualizar_titulo()
        self._actualizar_numeros_linea()

    def _actualizar_titulo(self) -> None:
        """Actualiza el label del título del archivo."""
        self.lbl_archivo.configure(text=self._get_titulo_archivo())

    def _actualizar_numeros_linea(self) -> None:
        """Actualiza los números de línea del margen."""
        self.txt_lineas.configure(state=tk.NORMAL)
        self.txt_lineas.delete("1.0", tk.END)

        contenido = self.txt_editor.get("1.0", "end-1c")
        num_lineas = contenido.count("\n") + 1

        numeros = "\n".join(str(i) for i in range(1, num_lineas + 1))
        self.txt_lineas.insert("1.0", numeros)
        self.txt_lineas.configure(state=tk.DISABLED)

    def _on_scroll_y(self, *args) -> None:
        """Sincroniza scroll entre editor y números de línea."""
        self.txt_editor.yview(*args)
        self.txt_lineas.yview(*args)
