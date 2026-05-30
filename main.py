"""Entry point de demostración de AetherOS v2.0.

Ejecuta una secuencia de operaciones sobre todos los subsistemas
del kernel para validar la integración completa:
    1. Inicialización del sistema
    2. Gestión de procesos (crear, planificar, terminar)
    3. Administración de memoria (asignar, consultar, liberar)
    4. Controladores de dispositivo (registrar, operaciones E/S)
    5. Gestión de archivos (crear, listar, renombrar, eliminar)
    6. Terminal integrada (verificación de plataforma)
    7. Estado global del sistema
    8. Apagado ordenado
"""

from __future__ import annotations

import argparse
import json
import platform
import sys

# Asegurar salida UTF-8 en Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from core.sistema import SistemaAetherOS
from excepciones.errores import AetherOSError, ShellNoDisponible
from modelos.tipos import (
    EstadoProceso,
    TipoDispositivo,
    TipoOperacionES,
)
from servicios.interfaz import GestorArchivos
from servicios.terminal_module import TerminalIntegrada


def _separador(titulo: str) -> None:
    """Imprime un separador visual con título."""
    print(f"\n{'='*60}")
    print(f"  {titulo}")
    print(f"{'='*60}\n")


def _imprimir_resultado(resultado: dict[str, object], indent: int = 2) -> None:
    """Imprime un ResultadoOperacion formateado."""
    print(json.dumps(resultado, indent=indent, default=str, ensure_ascii=False))


def demo_procesos(sistema: SistemaAetherOS) -> None:
    """Demuestra el subsistema de gestión de procesos.

    Args:
        sistema: Instancia del sistema AetherOS.
    """
    _separador("GESTIÓN DE PROCESOS")

    # Crear procesos con distintas prioridades
    procesos_demo = [
        ("Navegador Web", 3),
        ("Editor de Texto", 5),
        ("Reproductor Multimedia", 7),
        ("Servicio de Red", 1),
        ("Monitor del Sistema", 2),
    ]

    pids: list[int] = []
    for nombre, prioridad in procesos_demo:
        resultado = sistema.procesos.crear_proceso(nombre, prioridad)
        print(f"  ✓ {resultado['mensaje']}")
        pids.append(resultado["datos"]["pid"])

    # Listar procesos
    print("\n  --- Procesos activos ---")
    resultado = sistema.procesos.listar_procesos()
    for proc in resultado["datos"]:
        print(
            f"    PID={proc['pid']:3d} | {proc['nombre']:<25s} | "
            f"Estado={proc['estado']:<12s} | Prioridad={proc['prioridad']}"
        )

    # Planificación: ejecutar varios ciclos
    print("\n  --- Ciclos de planificación (Round-Robin + Prioridad) ---")
    for ciclo in range(3):
        resultado = sistema.procesos.planificar()
        if resultado["datos"]:
            proc = resultado["datos"]
            print(
                f"    Ciclo {ciclo+1}: PID={proc['pid']} "
                f"({proc['nombre']}) seleccionado [Prioridad={proc['prioridad']}]"
            )

            # Simular consumo de quantum
            sistema.procesos.consumir_quantum(proc["pid"], 2)
        else:
            print(f"    Ciclo {ciclo+1}: Cola vacía")

    # Bloquear un proceso (simular espera de E/S)
    if len(pids) > 2:
        # Primero se debe poner en EJECUTANDO (transición válida desde LISTO)
        resultado = sistema.procesos.cambiar_estado(pids[2], EstadoProceso.EJECUTANDO)
        print(f"\n  ▶ {resultado['mensaje']}")

        # Ahora sí se puede bloquear (EJECUTANDO -> BLOQUEADO)
        resultado = sistema.procesos.cambiar_estado(pids[2], EstadoProceso.BLOQUEADO)
        print(f"  ⏸ {resultado['mensaje']}")

        # Desbloquear (BLOQUEADO -> LISTO)
        resultado = sistema.procesos.cambiar_estado(pids[2], EstadoProceso.LISTO)
        print(f"  ▶ {resultado['mensaje']}")

    # Terminar un proceso
    resultado = sistema.procesos.terminar_proceso(pids[0])
    print(f"\n  ✗ {resultado['mensaje']}")

    # Estadísticas
    print("\n  --- Estadísticas ---")
    resultado = sistema.procesos.obtener_estadisticas()
    stats = resultado["datos"]
    print(f"    Total creados:     {stats['total_creados']}")
    print(f"    Total terminados:  {stats['total_terminados']}")
    print(f"    Activos:           {stats['procesos_activos']}")
    print(f"    Cambios contexto:  {stats['cambios_contexto']}")


def demo_memoria(sistema: SistemaAetherOS) -> None:
    """Demuestra el subsistema de administración de memoria.

    Args:
        sistema: Instancia del sistema AetherOS.
    """
    _separador("ADMINISTRACIÓN DE MEMORIA")

    # Asignar memoria a procesos
    asignaciones = [
        (1, 128),   # 2 páginas
        (2, 200),   # 4 páginas (redondeo hacia arriba)
        (3, 64),    # 1 página
    ]

    for pid, tamaño in asignaciones:
        try:
            resultado = sistema.memoria.asignar_memoria(pid, tamaño)
            datos = resultado["datos"]
            print(
                f"  ✓ PID={pid}: {datos['memoria_asignada']} unidades "
                f"({datos['paginas_asignadas']} páginas, marcos={datos['marcos']})"
            )
        except AetherOSError as e:
            print(f"  ✗ PID={pid}: {e.mensaje}")

    # Uso global de memoria
    print("\n  --- Uso de memoria ---")
    resultado = sistema.memoria.obtener_uso_memoria()
    uso = resultado["datos"]
    print(f"    Total:      {uso['memoria_total']} unidades")
    print(f"    Usada:      {uso['memoria_usada']} unidades")
    print(f"    Libre:      {uso['memoria_libre']} unidades")
    print(f"    Uso:        {uso['porcentaje_uso']}%")
    print(f"    Por proceso: {uso['uso_por_proceso']}")

    # Mapa de memoria (visual)
    print("\n  --- Mapa de memoria ---")
    resultado = sistema.memoria.obtener_mapa_memoria()
    for marco in resultado["datos"]:
        estado = "██" if marco["ocupado"] else "░░"
        pid_str = f"PID={marco['pid']}" if marco["ocupado"] else "libre"
        print(
            f"    Marco {marco['marco']:2d} [{marco['direccion_inicio']:4d}-"
            f"{marco['direccion_fin']:4d}] {estado} {pid_str}"
        )

    # Liberar memoria de un proceso
    print("\n  --- Liberación ---")
    resultado = sistema.memoria.liberar_memoria(3)
    print(f"  ✓ {resultado['mensaje']}")

    # Compactar memoria
    resultado = sistema.memoria.compactar_memoria()
    print(f"  ✓ {resultado['mensaje']}")

    # Consultar memoria de un proceso específico
    resultado = sistema.memoria.obtener_memoria_proceso(1)
    datos = resultado["datos"]
    print(f"\n  Memoria de PID=1: {datos['total_paginas']} página(s)")
    for pag in datos["paginas"]:
        print(
            f"    Página {pag['numero_pagina']}: Marco={pag['marco']}, "
            f"Dir.Física={pag['direccion_fisica']}"
        )


def demo_dispositivos(sistema: SistemaAetherOS) -> None:
    """Demuestra el subsistema de controladores de dispositivo.

    Args:
        sistema: Instancia del sistema AetherOS.
    """
    _separador("CONTROLADORES DE DISPOSITIVO")

    # Listar dispositivos pre-registrados
    print("  --- Dispositivos registrados ---")
    resultado = sistema.dispositivos.listar_dispositivos()
    for dev in resultado["datos"]:
        print(
            f"    ID={dev['id_dispositivo']:2d} | {dev['nombre']:<20s} | "
            f"Tipo={dev['tipo']:<10s} | Estado={dev['estado']}"
        )

    # Registrar dispositivo nuevo
    resultado = sistema.dispositivos.registrar_dispositivo(
        "Impresora Láser", TipoDispositivo.IMPRESORA
    )
    print(f"\n  ✓ {resultado['mensaje']}")

    # Operaciones de E/S
    print("\n  --- Operaciones de E/S ---")

    # Escritura al disco
    resultado = sistema.dispositivos.enviar_operacion(
        3, TipoOperacionES.ESCRITURA, {"archivo": "datos.txt", "contenido": "Hola AetherOS"}
    )
    print(f"  ✓ Disco - {resultado['mensaje']}")

    # Lectura del teclado
    resultado = sistema.dispositivos.enviar_operacion(
        1, TipoOperacionES.LECTURA, None
    )
    print(f"  ✓ Teclado - {resultado['mensaje']}")

    # Control de la red
    resultado = sistema.dispositivos.enviar_operacion(
        4, TipoOperacionES.CONTROL, "obtener_estado"
    )
    print(f"  ✓ Red - {resultado['mensaje']}")

    # Log de operaciones del disco
    print("\n  --- Log del Disco (ID=3) ---")
    resultado = sistema.dispositivos.obtener_log_operaciones(3)
    for op in resultado["datos"]:
        print(
            f"    [{op['tipo']}] Datos: {op.get('datos_entrada', 'N/A')} "
            f"- Exitosa: {op['exitosa']}"
        )

    # Estadísticas
    print("\n  --- Estadísticas ---")
    resultado = sistema.dispositivos.obtener_estadisticas()
    stats = resultado["datos"]
    print(f"    Total dispositivos: {stats['total_dispositivos']}")
    print(f"    Total operaciones:  {stats['total_operaciones']}")
    print(f"    Por estado:         {stats['conteo_por_estado']}")


def demo_archivos() -> None:
    """Demuestra el servicio de gestión de archivos."""
    _separador("GESTIÓN DE ARCHIVOS (Sandbox)")

    gestor = GestorArchivos()
    print(f"  Directorio raíz: {gestor.raiz}\n")

    # Crear directorios
    resultado = gestor.crear_directorio("documentos")
    print(f"  ✓ {resultado['mensaje']}")

    resultado = gestor.crear_directorio("documentos/proyectos")
    print(f"  ✓ {resultado['mensaje']}")

    resultado = gestor.crear_directorio("temporal")
    print(f"  ✓ {resultado['mensaje']}")

    # Listar directorio raíz
    print("\n  --- Contenido del sandbox ---")
    resultado = gestor.listar_directorio(".")
    for entrada in resultado["datos"]:
        icono = "📁" if entrada["tipo"] == "directorio" else "📄"
        print(f"    {icono} {entrada['nombre']:<25s} [{entrada['tipo']}]")

    # Obtener info de un directorio
    print("\n  --- Info de 'documentos' ---")
    resultado = gestor.obtener_info("documentos")
    datos = resultado["datos"]
    print(f"    Tipo:      {datos['tipo']}")
    print(f"    Permisos:  {datos['permisos']}")
    print(f"    Elementos: {datos.get('elementos', 'N/A')}")

    # Renombrar directorio
    resultado = gestor.renombrar("temporal", "cache")
    print(f"\n  ✓ {resultado['mensaje']}")

    # Verificar existencia
    resultado = gestor.existe("cache")
    print(f"  ✓ {resultado['mensaje']}")

    resultado = gestor.existe("temporal")
    print(f"  ✓ {resultado['mensaje']}")

    # Eliminar directorio vacío
    resultado = gestor.eliminar_directorio("cache")
    print(f"  ✓ {resultado['mensaje']}")

    # Intentar path traversal (debe fallar)
    print("\n  --- Prueba de seguridad: path traversal ---")
    try:
        gestor.listar_directorio("../../etc")
        print("  ✗ ERROR: Path traversal no fue bloqueado")
    except AetherOSError as e:
        print(f"  ✓ Bloqueado correctamente: {e.mensaje}")


def demo_terminal() -> None:
    """Demuestra el subsistema de terminal integrada."""
    _separador("TERMINAL INTEGRADA")

    terminal = TerminalIntegrada()
    print(f"  Plataforma: {platform.system()}")

    # Verificar estado
    resultado = terminal.esta_activa()
    datos = resultado["datos"]
    print(f"  Soporte PTY: {datos['soporte_pty']}")
    print(f"  Terminal activa: {datos['activa']}")

    if platform.system() != "Linux":
        print("\n  --- Prueba de detección de plataforma ---")
        try:
            terminal.iniciar_sesion()
        except ShellNoDisponible as e:
            print(f"  ✓ ShellNoDisponible: {e.mensaje}")
    else:
        # En Linux: demo completa
        print("\n  --- Sesión interactiva ---")
        resultado = terminal.iniciar_sesion()
        if resultado["exito"]:
            print(f"  ✓ {resultado['mensaje']} (PID={resultado['datos']['pid']})")

            # Ejecutar comandos
            for cmd in ["echo 'Hola desde AetherOS'", "uname -a", "pwd"]:
                resultado = terminal.ejecutar_comando(cmd)
                print(f"  $ {cmd}")
                if resultado["datos"] and resultado["datos"].get("salida"):
                    for linea in resultado["datos"]["salida"].strip().split("\n"):
                        print(f"    {linea}")

            # Cerrar sesión
            resultado = terminal.cerrar_sesion()
            print(f"\n  ✓ {resultado['mensaje']}")


def demo_estado_sistema(sistema: SistemaAetherOS) -> None:
    """Muestra el estado global del sistema serializado a JSON.

    Args:
        sistema: Instancia del sistema AetherOS.
    """
    _separador("ESTADO GLOBAL DEL SISTEMA")

    resultado = sistema.obtener_estado_sistema()

    if resultado["exito"]:
        # Serializar a JSON para demostrar que es compatible
        json_str = json.dumps(resultado["datos"], indent=2, default=str, ensure_ascii=False)
        print(f"  Estado serializable a JSON: {len(json_str)} bytes")
        print(f"\n{json_str}")
    else:
        print(f"  ✗ Error: {resultado['mensaje']}")


def ejecutar_demo_cli(sistema: SistemaAetherOS) -> None:
    """Ejecuta la demo original en modo texto."""
    print("\n" + "╔" + "═"*58 + "╗")
    print("║" + " AetherOS v2.0 — Demo de Integración".center(58) + "║")
    print("╚" + "═"*58 + "╝")

    resultado = sistema.iniciar()
    print(f"\n  ✓ {resultado['mensaje']}")

    try:
        # Ejecutar demos de cada subsistema
        demo_procesos(sistema)
        demo_memoria(sistema)
        demo_dispositivos(sistema)
        demo_archivos()
        demo_terminal()
        demo_estado_sistema(sistema)

    except AetherOSError as e:
        print(f"\n  ✗ Error de AetherOS: {e.mensaje} (código={e.codigo})")
    except Exception as e:
        print(f"\n  ✗ Error inesperado: {e}")
    finally:
        # Apagado ordenado
        _separador("APAGADO DEL SISTEMA")
        resultado = sistema.apagar()
        print(f"  ✓ {resultado['mensaje']}")
        datos = resultado.get("datos", {})
        if datos:
            print(f"    Procesos terminados: {datos.get('procesos_terminados', 0)}")
            print(f"    Tiempo activo:       {datos.get('tiempo_activo_segundos', 0)}s")

    print("\n" + "╔" + "═"*58 + "╗")
    print("║" + " Demo completada exitosamente".center(58) + "║")
    print("╚" + "═"*58 + "╝\n")


def main() -> None:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(description="AetherOS v2.0")
    parser.add_argument("--demo", action="store_true", help="Ejecuta la demo en texto (CLI)")
    args = parser.parse_args()

    # Inicializar sistema subyacente
    sistema = SistemaAetherOS(
        quantum=4,
        max_procesos=256,
        memoria_total=1024,
        tamaño_pagina=64,
    )

    if args.demo:
        ejecutar_demo_cli(sistema)
    else:
        try:
            # Intenta importar y lanzar la GUI
            import tkinter as tk
            from gui.app import lanzar_gui
            lanzar_gui(sistema)
        except ImportError:
            print("Error: No se pudo importar 'tkinter'. Ejecuta instalacion.sh para instalar python3-tk.")
            print("Fallback a la demo en modo texto...\n")
            ejecutar_demo_cli(sistema)


if __name__ == "__main__":
    main()
