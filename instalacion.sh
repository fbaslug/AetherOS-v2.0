#!/usr/bin/env bash
# ============================================================
#  AetherOS v2.0 — Script de Instalación para Linux
#  Uso: chmod +x instalacion.sh && ./instalacion.sh
# ============================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Colores para salida en terminal
# ---------------------------------------------------------------------------
ROJO='\033[0;31m'
VERDE='\033[0;32m'
AMARILLO='\033[1;33m'
CYAN='\033[0;36m'
NEGRITA='\033[1m'
RESET='\033[0m'

# ---------------------------------------------------------------------------
# Funciones de utilidad
# ---------------------------------------------------------------------------
info()    { echo -e "${CYAN}[INFO]${RESET}  $1"; }
ok()      { echo -e "${VERDE}[  OK]${RESET}  $1"; }
warn()    { echo -e "${AMARILLO}[WARN]${RESET}  $1"; }
error()   { echo -e "${ROJO}[ERROR]${RESET} $1"; }

# Directorio donde reside este script (raíz del proyecto)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=10
SANDBOX_DIR="$HOME/AetherOS_Root"

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo ""
echo -e "${NEGRITA}╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${NEGRITA}║         AetherOS v2.0 — Instalación para Linux         ║${RESET}"
echo -e "${NEGRITA}╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""

# ---------------------------------------------------------------------------
# 1. Detectar gestor de paquetes
# ---------------------------------------------------------------------------
detectar_gestor() {
    if command -v apt-get &>/dev/null; then
        echo "apt"
    elif command -v dnf &>/dev/null; then
        echo "dnf"
    elif command -v pacman &>/dev/null; then
        echo "pacman"
    elif command -v zypper &>/dev/null; then
        echo "zypper"
    else
        echo "desconocido"
    fi
}

GESTOR=$(detectar_gestor)
info "Gestor de paquetes detectado: ${NEGRITA}${GESTOR}${RESET}"

# ---------------------------------------------------------------------------
# 2. Verificar / Instalar Python 3.10+
# ---------------------------------------------------------------------------
verificar_python() {
    # Buscar el ejecutable de Python 3 disponible
    local python_cmd=""

    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            # Verificar que sea Python 3
            local version_completa
            version_completa=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+\.\d+' || true)
            if [[ -n "$version_completa" ]]; then
                local major minor
                major=$(echo "$version_completa" | cut -d. -f1)
                minor=$(echo "$version_completa" | cut -d. -f2)
                if [[ "$major" -ge "$PYTHON_MIN_MAJOR" && "$minor" -ge "$PYTHON_MIN_MINOR" ]]; then
                    python_cmd="$cmd"
                    echo "$python_cmd|$version_completa"
                    return 0
                fi
            fi
        fi
    done

    return 1
}

instalar_python() {
    info "Instalando Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+..."
    echo ""
    warn "Se requieren permisos de administrador (sudo)."
    echo ""

    case "$GESTOR" in
        apt)
            sudo apt-get update -y
            sudo apt-get install -y python3 python3-venv python3-pip
            ;;
        dnf)
            sudo dnf install -y python3 python3-pip
            ;;
        pacman)
            sudo pacman -Sy --noconfirm python python-pip
            ;;
        zypper)
            sudo zypper install -y python3 python3-pip
            ;;
        *)
            error "No se pudo detectar un gestor de paquetes compatible."
            error "Instala Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ manualmente y vuelve a ejecutar este script."
            exit 1
            ;;
    esac
}

info "Verificando Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+..."

PYTHON_RESULTADO=$(verificar_python || true)

if [[ -n "$PYTHON_RESULTADO" ]]; then
    PYTHON_CMD=$(echo "$PYTHON_RESULTADO" | cut -d'|' -f1)
    PYTHON_VER=$(echo "$PYTHON_RESULTADO" | cut -d'|' -f2)
    ok "Python ${PYTHON_VER} encontrado (${PYTHON_CMD})"
else
    warn "Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+ no encontrado."
    echo ""
    read -rp "¿Deseas instalar Python automáticamente? [S/n]: " respuesta
    respuesta="${respuesta:-S}"

    if [[ "$respuesta" =~ ^[Ss]$ ]]; then
        instalar_python

        # Verificar de nuevo
        PYTHON_RESULTADO=$(verificar_python || true)
        if [[ -n "$PYTHON_RESULTADO" ]]; then
            PYTHON_CMD=$(echo "$PYTHON_RESULTADO" | cut -d'|' -f1)
            PYTHON_VER=$(echo "$PYTHON_RESULTADO" | cut -d'|' -f2)
            ok "Python ${PYTHON_VER} instalado correctamente"
        else
            error "No se pudo instalar Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+."
            error "Instálalo manualmente y vuelve a ejecutar este script."
            exit 1
        fi
    else
        error "Python es obligatorio para AetherOS v2.0. Abortando."
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# 3. Verificar xterm (necesario para terminal_module.py)
# ---------------------------------------------------------------------------
info "Verificando xterm..."

if command -v xterm &>/dev/null; then
    XTERM_VER=$(xterm -version 2>&1 | head -1 || echo "instalado")
    ok "xterm encontrado: ${XTERM_VER}"
else
    warn "xterm no encontrado."
    echo ""
    read -rp "¿Deseas instalar xterm? (opcional, para terminal integrada) [S/n]: " respuesta
    respuesta="${respuesta:-S}"

    if [[ "$respuesta" =~ ^[Ss]$ ]]; then
        case "$GESTOR" in
            apt)    sudo apt-get install -y xterm ;;
            dnf)    sudo dnf install -y xterm ;;
            pacman) sudo pacman -Sy --noconfirm xterm ;;
            zypper) sudo zypper install -y xterm ;;
            *)      warn "Instala xterm manualmente si deseas usar la terminal integrada." ;;
        esac

        if command -v xterm &>/dev/null; then
            ok "xterm instalado correctamente"
        else
            warn "xterm no se pudo instalar. La terminal integrada funcionará sin él usando bash directo."
        fi
    else
        warn "xterm omitido. La terminal integrada funcionará sin él usando bash directo."
    fi
fi

# ---------------------------------------------------------------------------
# 4. Verificar estructura del proyecto
# ---------------------------------------------------------------------------
info "Verificando estructura del proyecto en: ${NEGRITA}${SCRIPT_DIR}${RESET}"

ARCHIVOS_REQUERIDOS=(
    "main.py"
    "core/__init__.py"
    "core/sistema.py"
    "core/gestion_procesos.py"
    "core/admin_memoria.py"
    "core/controladores_dispositivo.py"
    "servicios/__init__.py"
    "servicios/interfaz.py"
    "servicios/terminal_module.py"
    "modelos/__init__.py"
    "modelos/tipos.py"
    "excepciones/__init__.py"
    "excepciones/errores.py"
)

archivos_faltantes=0
for archivo in "${ARCHIVOS_REQUERIDOS[@]}"; do
    ruta_completa="${SCRIPT_DIR}/${archivo}"
    if [[ -f "$ruta_completa" ]]; then
        ok "${archivo}"
    else
        error "Faltante: ${archivo}"
        archivos_faltantes=$((archivos_faltantes + 1))
    fi
done

if [[ "$archivos_faltantes" -gt 0 ]]; then
    echo ""
    error "${archivos_faltantes} archivo(s) faltante(s). Verifica que el proyecto esté completo."
    exit 1
fi

ok "Todos los archivos del proyecto verificados (${#ARCHIVOS_REQUERIDOS[@]}/${#ARCHIVOS_REQUERIDOS[@]})"

# ---------------------------------------------------------------------------
# 5. Verificar compilación de módulos Python
# ---------------------------------------------------------------------------
echo ""
info "Verificando compilación de módulos Python..."

errores_compilacion=0
for archivo in "${ARCHIVOS_REQUERIDOS[@]}"; do
    if [[ "$archivo" == *.py ]]; then
        ruta_completa="${SCRIPT_DIR}/${archivo}"
        if $PYTHON_CMD -m py_compile "$ruta_completa" 2>/dev/null; then
            ok "Compilación: ${archivo}"
        else
            error "Error de compilación: ${archivo}"
            errores_compilacion=$((errores_compilacion + 1))
        fi
    fi
done

if [[ "$errores_compilacion" -gt 0 ]]; then
    echo ""
    error "${errores_compilacion} error(es) de compilación. Revisa los archivos."
    exit 1
fi

# ---------------------------------------------------------------------------
# 6. Crear directorio sandbox
# ---------------------------------------------------------------------------
echo ""
info "Configurando directorio sandbox: ${NEGRITA}${SANDBOX_DIR}${RESET}"

if [[ -d "$SANDBOX_DIR" ]]; then
    ok "Directorio sandbox ya existe: ${SANDBOX_DIR}"
else
    mkdir -p "$SANDBOX_DIR"
    ok "Directorio sandbox creado: ${SANDBOX_DIR}"
fi

# ---------------------------------------------------------------------------
# 7. Asignar permisos de ejecución
# ---------------------------------------------------------------------------
info "Asignando permisos de ejecución a main.py..."
chmod +x "${SCRIPT_DIR}/main.py"
ok "Permisos asignados"

# ---------------------------------------------------------------------------
# 8. Crear script de lanzamiento rápido
# ---------------------------------------------------------------------------
LAUNCHER="${SCRIPT_DIR}/aetheros.sh"

cat > "$LAUNCHER" << 'LAUNCHER_EOF'
#!/usr/bin/env bash
# Lanzador rápido de AetherOS v2.0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detectar Python
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        exec "$cmd" main.py "$@"
    fi
done

echo "Error: Python 3 no encontrado. Ejecuta instalacion.sh primero."
exit 1
LAUNCHER_EOF

chmod +x "$LAUNCHER"
ok "Lanzador creado: ${NEGRITA}aetheros.sh${RESET}"

# ---------------------------------------------------------------------------
# 9. Prueba de importación rápida
# ---------------------------------------------------------------------------
echo ""
info "Ejecutando prueba de importación..."

cd "$SCRIPT_DIR"
IMPORT_TEST=$($PYTHON_CMD -c "
from core.sistema import SistemaAetherOS
from servicios.interfaz import GestorArchivos
from servicios.terminal_module import TerminalIntegrada
from excepciones.errores import AetherOSError
from modelos.tipos import ResultadoOperacion
print('OK')
" 2>&1)

if [[ "$IMPORT_TEST" == "OK" ]]; then
    ok "Todos los módulos se importan correctamente"
else
    error "Error en importación de módulos:"
    echo "$IMPORT_TEST"
    exit 1
fi

# ---------------------------------------------------------------------------
# Resumen final
# ---------------------------------------------------------------------------
echo ""
echo -e "${NEGRITA}╔══════════════════════════════════════════════════════════╗${RESET}"
echo -e "${NEGRITA}║       ✓ AetherOS v2.0 — Instalación Completada         ║${RESET}"
echo -e "${NEGRITA}╚══════════════════════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  ${VERDE}Python:${RESET}    ${PYTHON_VER} (${PYTHON_CMD})"
echo -e "  ${VERDE}Proyecto:${RESET}  ${SCRIPT_DIR}"
echo -e "  ${VERDE}Sandbox:${RESET}   ${SANDBOX_DIR}"
echo ""
echo -e "  ${NEGRITA}Para ejecutar AetherOS:${RESET}"
echo -e "    ${CYAN}./aetheros.sh${RESET}"
echo -e "    ${CYAN}${PYTHON_CMD} main.py${RESET}"
echo ""

# ---------------------------------------------------------------------------
# 10. Preguntar si desea ejecutar la demo
# ---------------------------------------------------------------------------
read -rp "¿Deseas ejecutar la demo de AetherOS ahora? [S/n]: " respuesta
respuesta="${respuesta:-S}"

if [[ "$respuesta" =~ ^[Ss]$ ]]; then
    echo ""
    info "Ejecutando AetherOS v2.0..."
    echo ""
    cd "$SCRIPT_DIR"
    $PYTHON_CMD main.py
else
    echo ""
    info "Puedes ejecutar la demo cuando quieras con: ${NEGRITA}./aetheros.sh${RESET}"
fi

echo ""
ok "¡Listo! AetherOS v2.0 está configurado."
