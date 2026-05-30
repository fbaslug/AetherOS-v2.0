"""Interfaz gráfica para la Gestión de Procesos.

Muestra una tabla con los procesos activos, permite crear
nuevos procesos, terminarlos y forzar ciclos de planificación.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random

from core.gestion_procesos import GestorProcesos
from modelos.tipos import EstadoProceso
from gui import tema
from gui.ventana_base import VentanaInterna


class AdminProcesos(VentanaInterna):
    """Aplicación Administrador de Procesos."""

    def __init__(self, parent: tk.Widget, gestor: GestorProcesos) -> None:
        super().__init__(
            parent,
            titulo="Administrador de Procesos",
            ancho=750,
            alto=500,
            icono="📊"
        )
        self.gestor = gestor

        # Barra de Herramientas
        toolbar = tk.Frame(self.area_contenido, bg=tema.FONDO_VENTANA)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        btn_crear = tk.Button(
            toolbar,
            text="+ Nuevo Proceso",
            bg=tema.ACENTO,
            fg=tema.FONDO_PRINCIPAL,
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            command=self._crear_proceso_demo
        )
        btn_crear.pack(side=tk.LEFT, padx=5)

        btn_planificar = tk.Button(
            toolbar,
            text="▶ Planificar Ciclo (CPU)",
            bg=tema.FONDO_SECUNDARIO,
            fg=tema.TEXTO,
            relief=tk.FLAT,
            command=self._planificar
        )
        btn_planificar.pack(side=tk.LEFT, padx=5)

        self.btn_terminar = tk.Button(
            toolbar,
            text="✕ Terminar Seleccionado",
            bg=tema.ERROR,
            fg=tema.TEXTO,
            relief=tk.FLAT,
            state=tk.DISABLED,
            command=self._terminar_seleccionado
        )
        self.btn_terminar.pack(side=tk.RIGHT, padx=5)

        # Tabla de Procesos
        frame_tabla = tk.Frame(self.area_contenido, bg=tema.FONDO_VENTANA)
        frame_tabla.pack(fill=tk.BOTH, expand=True)

        columnas = ("pid", "nombre", "estado", "prioridad", "cpu", "memoria")
        self.tree = ttk.Treeview(frame_tabla, columns=columnas, show="headings")
        
        self.tree.heading("pid", text="PID")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("estado", text="Estado")
        self.tree.heading("prioridad", text="Prioridad")
        self.tree.heading("cpu", text="CPU (q)")
        self.tree.heading("memoria", text="Memoria")

        self.tree.column("pid", width=50, anchor=tk.CENTER)
        self.tree.column("nombre", width=200)
        self.tree.column("estado", width=120, anchor=tk.CENTER)
        self.tree.column("prioridad", width=80, anchor=tk.CENTER)
        self.tree.column("cpu", width=80, anchor=tk.CENTER)
        self.tree.column("memoria", width=80, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(frame_tabla, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Iniciar actualización
        self._actualizar_lista()

    def _crear_proceso_demo(self) -> None:
        nombres = ["Navegador", "Terminal", "Editor de Texto", "Gestor de Archivos", "Reproductor", "Servicio Red"]
        nombre = f"{random.choice(nombres)} ({random.randint(100, 999)})"
        prioridad = random.randint(1, 8)
        self.gestor.crear_proceso(nombre, prioridad)
        self._actualizar_lista()

    def _planificar(self) -> None:
        # Simulamos que la CPU consume el quantum del actual y luego planifica
        stats = self.gestor.obtener_estadisticas().get("datos", {})
        pid_actual = stats.get("pid_ejecutando")
        
        if pid_actual is not None:
            self.gestor.consumir_quantum(pid_actual, self.gestor.quantum)
            
        self.gestor.planificar()
        self._actualizar_lista()

    def _on_select(self, event) -> None:
        seleccion = self.tree.selection()
        if seleccion:
            self.btn_terminar.configure(state=tk.NORMAL)
        else:
            self.btn_terminar.configure(state=tk.DISABLED)

    def _terminar_seleccionado(self) -> None:
        seleccion = self.tree.selection()
        if not seleccion:
            return
            
        item = self.tree.item(seleccion[0])
        pid = item['values'][0]
        
        try:
            self.gestor.terminar_proceso(int(pid))
            self._actualizar_lista()
            self.btn_terminar.configure(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _actualizar_lista(self) -> None:
        if not self.winfo_exists():
            return
            
        # Guardar selección actual
        seleccionados = self.tree.selection()
        valores_sel = [self.tree.item(s)['values'][0] for s in seleccionados] if seleccionados else []

        # Limpiar
        for item in self.tree.get_children():
            self.tree.delete(item)

        res = self.gestor.listar_procesos(incluir_terminados=False)
        if res["exito"]:
            for proc in res["datos"]:
                iid = self.tree.insert(
                    "", tk.END,
                    values=(
                        proc["pid"],
                        proc["nombre"],
                        proc["estado"],
                        proc["prioridad"],
                        proc["tiempo_cpu"],
                        proc["memoria_asignada"]
                    )
                )
                if proc["pid"] in valores_sel:
                    self.tree.selection_add(iid)

        self.after(1000, self._actualizar_lista)
