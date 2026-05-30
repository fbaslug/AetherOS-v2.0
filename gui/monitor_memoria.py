"""Interfaz gráfica para el Administrador de Memoria.

Muestra un mapa visual de los marcos, estadísticas globales y
tabla de procesos con su uso de memoria.
"""

import tkinter as tk
from tkinter import ttk

from core.admin_memoria import AdministradorMemoria
from gui import tema
from gui.ventana_base import VentanaInterna


class MonitorMemoria(VentanaInterna):
    """Aplicación Monitor de Memoria."""

    def __init__(self, parent: tk.Widget, admin_memoria: AdministradorMemoria) -> None:
        super().__init__(
            parent,
            titulo="Monitor de Memoria",
            ancho=700,
            alto=500,
            icono="💾"
        )
        self.memoria = admin_memoria

        # Split: Arriba stats y controles, Abajo mapa
        panel_superior = tk.Frame(self.area_contenido, bg=tema.FONDO_VENTANA)
        panel_superior.pack(fill=tk.X, pady=(0, 10))

        # Panel izquierdo: Stats
        self.frame_stats = tk.Frame(panel_superior, bg=tema.FONDO_VENTANA)
        self.frame_stats.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.lbl_uso = tk.Label(
            self.frame_stats,
            text="Uso: 0%",
            font=tema.FUENTE_TITULO,
            bg=tema.FONDO_VENTANA,
            fg=tema.TEXTO
        )
        self.lbl_uso.pack(anchor=tk.W)

        self.lbl_detalle = tk.Label(
            self.frame_stats,
            text="0 / 1024 Unidades",
            font=tema.FUENTE_PRINCIPAL,
            bg=tema.FONDO_VENTANA,
            fg=tema.TEXTO_SECUNDARIO
        )
        self.lbl_detalle.pack(anchor=tk.W)

        # Panel derecho: Controles
        panel_controles = tk.Frame(panel_superior, bg=tema.FONDO_VENTANA)
        panel_controles.pack(side=tk.RIGHT)

        btn_compactar = tk.Button(
            panel_controles,
            text="Compactar Memoria",
            bg=tema.ACENTO,
            fg=tema.FONDO_PRINCIPAL,
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            padx=10,
            command=self._compactar
        )
        btn_compactar.pack(pady=5)

        # Mapa de Marcos (Cuadrícula)
        self.frame_mapa = tk.Frame(self.area_contenido, bg=tema.FONDO_SECUNDARIO, bd=1, relief=tk.SOLID)
        self.frame_mapa.pack(fill=tk.BOTH, expand=True)

        self.celdas_marcos: dict[int, tk.Label] = {}

        # Iniciar actualización periódica
        self._actualizar_vista()

    def _compactar(self) -> None:
        self.memoria.compactar_memoria()
        self._actualizar_vista()

    def _actualizar_vista(self) -> None:
        if not self.winfo_exists():
            return

        res_uso = self.memoria.obtener_uso_memoria()
        res_mapa = self.memoria.obtener_mapa_memoria()

        if res_uso["exito"]:
            datos = res_uso["datos"]
            self.lbl_uso.configure(text=f"Uso: {datos['porcentaje_uso']}%")
            self.lbl_detalle.configure(
                text=f"{datos['memoria_usada']} / {datos['memoria_total']} Unidades "
                     f"({datos['marcos_ocupados']} marcos usados, {datos['marcos_libres']} libres)"
            )

        if res_mapa["exito"]:
            mapa = res_mapa["datos"]
            # Recrear cuadrícula
            for widget in self.frame_mapa.winfo_children():
                widget.destroy()

            # Cuadrícula 4x4 si son 16 marcos
            columnas = 4
            for i, marco in enumerate(mapa):
                fila = i // columnas
                col = i % columnas

                color_fondo = tema.ACENTO if marco["ocupado"] else tema.FONDO_PRINCIPAL
                color_texto = tema.FONDO_PRINCIPAL if marco["ocupado"] else tema.TEXTO_SECUNDARIO
                texto = f"M{marco['marco']}\nPID: {marco['pid']}" if marco["ocupado"] else f"M{marco['marco']}\nLibre"

                lbl = tk.Label(
                    self.frame_mapa,
                    text=texto,
                    bg=color_fondo,
                    fg=color_texto,
                    font=tema.FUENTE_PRINCIPAL,
                    relief=tk.RIDGE,
                    bd=1,
                    width=10,
                    height=3
                )
                lbl.grid(row=fila, column=col, padx=5, pady=5, sticky="nsew")
                
                self.frame_mapa.grid_columnconfigure(col, weight=1)
                self.frame_mapa.grid_rowconfigure(fila, weight=1)

        self.after(1000, self._actualizar_vista)
