"""Interfaz gráfica para Controladores de Dispositivo.

Lista los dispositivos, muestra su estado y permite enviar
operaciones de prueba (E/S) para verificar los logs.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from core.controladores_dispositivo import ControladorDispositivos
from modelos.tipos import TipoOperacionES
from gui import tema
from gui.ventana_base import VentanaInterna


class GestorDispositivos(VentanaInterna):
    """Aplicación Gestor de Dispositivos."""

    def __init__(self, parent: tk.Widget, dispositivos: ControladorDispositivos) -> None:
        super().__init__(
            parent,
            titulo="Gestor de Dispositivos",
            ancho=800,
            alto=500,
            icono="🖧"
        )
        self.controlador = dispositivos

        # Split: Izquierda Lista, Derecha Detalles/Log
        self.paned = ttk.PanedWindow(self.area_contenido, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        # Panel Izquierdo: Lista
        frame_lista = tk.Frame(self.paned, bg=tema.FONDO_VENTANA)
        self.paned.add(frame_lista, weight=1)

        columnas = ("id", "nombre", "tipo", "estado")
        self.tree = ttk.Treeview(frame_lista, columns=columnas, show="headings")
        self.tree.heading("id", text="ID")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("estado", text="Estado")

        self.tree.column("id", width=40, anchor=tk.CENTER)
        self.tree.column("nombre", width=150)
        self.tree.column("tipo", width=80)
        self.tree.column("estado", width=80)

        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Panel Derecho: Detalles y Log
        frame_detalles = tk.Frame(self.paned, bg=tema.FONDO_SECUNDARIO)
        self.paned.add(frame_detalles, weight=2)

        lbl_titulo_detalles = tk.Label(
            frame_detalles,
            text="Detalles del Dispositivo",
            font=tema.FUENTE_TITULO,
            bg=tema.FONDO_SECUNDARIO,
            fg=tema.TEXTO
        )
        lbl_titulo_detalles.pack(pady=(10, 5))

        self.txt_log = tk.Text(
            frame_detalles,
            bg=tema.FONDO_PRINCIPAL,
            fg=tema.TEXTO,
            font=tema.FUENTE_MONO,
            height=15,
            state=tk.DISABLED
        )
        self.txt_log.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        frame_acciones = tk.Frame(frame_detalles, bg=tema.FONDO_SECUNDARIO)
        frame_acciones.pack(fill=tk.X, padx=10, pady=10)

        self.btn_leer = tk.Button(
            frame_acciones, text="Leer (Input)", state=tk.DISABLED,
            bg=tema.FONDO_ALT, fg=tema.TEXTO, command=lambda: self._enviar_op(TipoOperacionES.LECTURA)
        )
        self.btn_leer.pack(side=tk.LEFT, padx=5)

        self.btn_escribir = tk.Button(
            frame_acciones, text="Escribir (Output)", state=tk.DISABLED,
            bg=tema.FONDO_ALT, fg=tema.TEXTO, command=lambda: self._enviar_op(TipoOperacionES.ESCRITURA, "Datos de prueba")
        )
        self.btn_escribir.pack(side=tk.LEFT, padx=5)

        self.btn_control = tk.Button(
            frame_acciones, text="Control (Status)", state=tk.DISABLED,
            bg=tema.FONDO_ALT, fg=tema.TEXTO, command=lambda: self._enviar_op(TipoOperacionES.CONTROL)
        )
        self.btn_control.pack(side=tk.LEFT, padx=5)

        self._dispositivo_actual = None
        self._actualizar_lista()

    def _actualizar_lista(self) -> None:
        if not self.winfo_exists():
            return
            
        seleccionados = self.tree.selection()
        valores_sel = [self.tree.item(s)['values'][0] for s in seleccionados] if seleccionados else []

        for item in self.tree.get_children():
            self.tree.delete(item)

        res = self.controlador.listar_dispositivos()
        if res["exito"]:
            for dev in res["datos"]:
                iid = self.tree.insert(
                    "", tk.END,
                    values=(dev["id_dispositivo"], dev["nombre"], dev["tipo"], dev["estado"])
                )
                if dev["id_dispositivo"] in valores_sel:
                    self.tree.selection_add(iid)

        self._actualizar_log()
        self.after(2000, self._actualizar_lista)

    def _on_select(self, event) -> None:
        seleccion = self.tree.selection()
        if seleccion:
            self._dispositivo_actual = self.tree.item(seleccion[0])['values'][0]
            self.btn_leer.configure(state=tk.NORMAL)
            self.btn_escribir.configure(state=tk.NORMAL)
            self.btn_control.configure(state=tk.NORMAL)
            self._actualizar_log()
        else:
            self._dispositivo_actual = None
            self.btn_leer.configure(state=tk.DISABLED)
            self.btn_escribir.configure(state=tk.DISABLED)
            self.btn_control.configure(state=tk.DISABLED)

    def _enviar_op(self, tipo: TipoOperacionES, datos=None) -> None:
        if self._dispositivo_actual is not None:
            try:
                self.controlador.enviar_operacion(self._dispositivo_actual, tipo, datos)
                self._actualizar_log()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self)

    def _actualizar_log(self) -> None:
        if self._dispositivo_actual is None:
            self.txt_log.configure(state=tk.NORMAL)
            self.txt_log.delete(1.0, tk.END)
            self.txt_log.configure(state=tk.DISABLED)
            return

        res = self.controlador.obtener_log_operaciones(self._dispositivo_actual)
        if res["exito"]:
            self.txt_log.configure(state=tk.NORMAL)
            self.txt_log.delete(1.0, tk.END)
            for op in res["datos"][-15:]:  # Últimas 15
                self.txt_log.insert(tk.END, f"[{op['tipo']}] Datos: {op.get('datos_salida', 'OK')}\n")
            self.txt_log.configure(state=tk.DISABLED)
            self.txt_log.see(tk.END)
