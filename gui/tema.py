"""Sistema de diseño y tema visual para la GUI de AetherOS.

Define los colores, fuentes y estilos estándar utilizados en todo
el entorno de escritorio para mantener consistencia visual.
Utiliza un esquema 'Dark Mode' moderno.
"""

# ---------------------------------------------------------------------------
# Paleta de Colores (Dark Mode)
# ---------------------------------------------------------------------------
FONDO_PRINCIPAL = "#0d1117"     # Fondo más oscuro (escritorio)
FONDO_SECUNDARIO = "#161b22"    # Gris oscuro (barras, paneles)
FONDO_VENTANA = "#1c2128"       # Fondo de ventanas
FONDO_ALT = "#21262d"           # Fondo alternativo (filas de tablas)

ACENTO = "#00d4ff"              # Cyan eléctrico (bordes, selección, botones)
ACENTO_HOVER = "#33ddff"        # Cyan más claro para hover
ACENTO_PRESIONADO = "#0099cc"   # Cyan oscuro para estado activo

TEXTO = "#e6edf3"               # Blanco suave (texto principal)
TEXTO_SECUNDARIO = "#8b949e"    # Gris (texto secundario, deshabilitado)

EXITO = "#3fb950"               # Verde
ADVERTENCIA = "#d29922"         # Amarillo
ERROR = "#f85149"               # Rojo

# ---------------------------------------------------------------------------
# Fuentes
# ---------------------------------------------------------------------------
FUENTE_PRINCIPAL = ("Segoe UI", 10)
FUENTE_TITULO = ("Segoe UI", 12, "bold")
FUENTE_GRANDE = ("Segoe UI", 24, "bold")
FUENTE_MONO = ("Consolas", 10)

# ---------------------------------------------------------------------------
# Utilidades de Estilo
# ---------------------------------------------------------------------------

def configurar_estilos_ttk(ttk_style) -> None:
    """Configura los estilos base de ttk para que coincidan con el tema."""
    ttk_style.theme_use("clam")

    # Estilo general para Treeview (Tablas)
    ttk_style.configure(
        "Treeview",
        background=FONDO_VENTANA,
        foreground=TEXTO,
        fieldbackground=FONDO_VENTANA,
        borderwidth=0,
        font=FUENTE_PRINCIPAL,
        rowheight=25,
    )
    ttk_style.map(
        "Treeview",
        background=[("selected", ACENTO)],
        foreground=[("selected", FONDO_PRINCIPAL)],
    )

    # Encabezados de Treeview
    ttk_style.configure(
        "Treeview.Heading",
        background=FONDO_SECUNDARIO,
        foreground=TEXTO_SECUNDARIO,
        borderwidth=1,
        font=("Segoe UI", 9, "bold"),
    )
    ttk_style.map(
        "Treeview.Heading",
        background=[("active", FONDO_ALT)],
    )

    # Scrollbars
    ttk_style.configure(
        "Vertical.TScrollbar",
        background=FONDO_SECUNDARIO,
        troughcolor=FONDO_PRINCIPAL,
        bordercolor=FONDO_PRINCIPAL,
        arrowcolor=TEXTO_SECUNDARIO,
    )
    ttk_style.map(
        "Vertical.TScrollbar",
        background=[("active", FONDO_ALT)],
    )
