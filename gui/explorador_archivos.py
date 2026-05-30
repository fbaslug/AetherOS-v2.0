"""Interfaz gráfica para el Gestor de Archivos (Sandbox).

Muestra el contenido del directorio actual, permite navegación,
creación de carpetas y eliminación de archivos.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import os

from servicios.interfaz import GestorArchivos
from gui import tema
from gui.ventana_base import VentanaInterna


class ExploradorArchivos(VentanaInterna):
    """Aplicación Explorador de Archivos."""

    def __init__(self, parent: tk.Widget, gestor: GestorArchivos) -> None:
        super().__init__(
            parent,
            titulo="Explorador de Archivos",
            ancho=800,
            alto=550,
            icono="📁"
        )
        self.gestor = gestor
        self.ruta_actual = ""

        # Toolbar superior (Navegación)
        toolbar = tk.Frame(self.area_contenido, bg=tema.FONDO_SECUNDARIO, height=40)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        btn_arriba = tk.Button(
            toolbar, text="⬆ Subir Nivel", bg=tema.FONDO_ALT, fg=tema.TEXTO,
            relief=tk.FLAT, command=self._subir_nivel
        )
        btn_arriba.pack(side=tk.LEFT, padx=5, pady=5)

        self.lbl_ruta = tk.Label(
            toolbar, text="/", bg=tema.FONDO_SECUNDARIO, fg=tema.TEXTO, font=tema.FUENTE_PRINCIPAL
        )
        self.lbl_ruta.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        # Barra lateral izquierda (Acciones rápidas)
        panel_izq = tk.Frame(self.area_contenido, bg=tema.FONDO_SECUNDARIO, width=150)
        panel_izq.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5), pady=5)
        panel_izq.pack_propagate(False)

        btn_nueva_carpeta = tk.Button(
            panel_izq, text="+ Nueva Carpeta", bg=tema.ACENTO, fg=tema.FONDO_PRINCIPAL,
            relief=tk.FLAT, command=self._nueva_carpeta
        )
        btn_nueva_carpeta.pack(fill=tk.X, padx=5, pady=5)

        btn_eliminar = tk.Button(
            panel_izq, text="✕ Eliminar", bg=tema.ERROR, fg=tema.TEXTO,
            relief=tk.FLAT, command=self._eliminar_seleccionado
        )
        btn_eliminar.pack(fill=tk.X, padx=5, pady=5)

        # Vista de archivos principal (Treeview)
        frame_tabla = tk.Frame(self.area_contenido, bg=tema.FONDO_VENTANA)
        frame_tabla.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, pady=5)

        columnas = ("icono", "nombre", "tipo", "tamaño", "permisos")
        self.tree = ttk.Treeview(frame_tabla, columns=columnas, show="headings")
        
        self.tree.heading("icono", text="")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("tamaño", text="Tamaño (B)")
        self.tree.heading("permisos", text="Permisos")

        self.tree.column("icono", width=40, anchor=tk.CENTER)
        self.tree.column("nombre", width=300)
        self.tree.column("tipo", width=100)
        self.tree.column("tamaño", width=100, anchor=tk.E)
        self.tree.column("permisos", width=100)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(frame_tabla, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_doble_clic)

        # Cargar inicial
        self._cargar_directorio()

    def _cargar_directorio(self) -> None:
        """Carga el contenido de la ruta actual."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        res = self.gestor.listar_directorio(self.ruta_actual)
        if res["exito"]:
            self.lbl_ruta.configure(text=f"Sandbox: /{self.ruta_actual}")
            elementos = res["datos"]
            
            # Ordenar: Directorios primero, luego alfabético
            elementos.sort(key=lambda x: (x["tipo"] != "directorio", x["nombre"].lower()))

            for el in elementos:
                icono = "📁" if el["tipo"] == "directorio" else "📄"
                self.tree.insert(
                    "", tk.END,
                    values=(icono, el["nombre"], el["tipo"], el["tamaño"], el["permisos"])
                )
        else:
            messagebox.showerror("Error", res["mensaje"], parent=self)

    def _subir_nivel(self) -> None:
        if not self.ruta_actual or self.ruta_actual == "/":
            return
        # Subir un directorio usando os.path
        padre = os.path.dirname(self.ruta_actual)
        if padre == self.ruta_actual or padre == "/":
            self.ruta_actual = ""
        else:
            self.ruta_actual = padre
        self._cargar_directorio()

    def _on_doble_clic(self, event) -> None:
        seleccion = self.tree.selection()
        if not seleccion:
            return

        item = self.tree.item(seleccion[0])
        nombre = item['values'][1]
        tipo = item['values'][2]

        if tipo == "directorio":
            # Entrar al directorio
            if self.ruta_actual:
                self.ruta_actual = f"{self.ruta_actual}/{nombre}"
            else:
                self.ruta_actual = nombre
            self._cargar_directorio()
        else:
            # Mostrar alerta
            messagebox.showinfo("Archivo", f"Seleccionaste el archivo: {nombre}\nLa apertura de archivos requiere la app correspondiente.", parent=self)

    def _nueva_carpeta(self) -> None:
        nombre = simpledialog.askstring("Nueva Carpeta", "Nombre de la carpeta:", parent=self)
        if nombre:
            ruta_crear = f"{self.ruta_actual}/{nombre}" if self.ruta_actual else nombre
            res = self.gestor.crear_directorio(ruta_crear)
            if res["exito"]:
                self._cargar_directorio()
            else:
                messagebox.showerror("Error", res["mensaje"], parent=self)

    def _eliminar_seleccionado(self) -> None:
        seleccion = self.tree.selection()
        if not seleccion:
            return

        item = self.tree.item(seleccion[0])
        nombre = item['values'][1]
        ruta_eliminar = f"{self.ruta_actual}/{nombre}" if self.ruta_actual else nombre

        if messagebox.askyesno("Confirmar", f"¿Eliminar permanentemente '{nombre}'?", parent=self):
            res = self.gestor.eliminar(ruta_eliminar)
            if res["exito"]:
                self._cargar_directorio()
            else:
                messagebox.showerror("Error", res["mensaje"], parent=self)
