"""Módulo de administración de memoria para AetherOS v2.0.

Implementa un sistema de paginación simulada con marcos de memoria
física, tablas de páginas por proceso, y operaciones de asignación,
liberación y compactación.

Configuración por defecto:
    - Memoria total: 1024 unidades
    - Tamaño de página/marco: 64 unidades
    - Total de marcos: 16
"""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict
from typing import Optional

from excepciones.errores import (
    BloqueNoEncontrado,
    MemoriaInsuficiente,
)
from modelos.tipos import (
    BloqueMemoria,
    MarcoMemoria,
    Pagina,
    ResultadoOperacion,
)

logger = logging.getLogger("AetherOS.Memoria")


class AdministradorMemoria:
    """Administrador de memoria con paginación simulada.

    Gestiona un espacio de memoria física dividido en marcos (frames)
    de tamaño fijo. Cada proceso recibe páginas virtuales mapeadas
    a marcos físicos mediante tablas de páginas individuales.

    Attributes:
        memoria_total: Capacidad total de memoria en unidades.
        tamaño_pagina: Tamaño de cada página/marco en unidades.
        total_marcos: Número total de marcos disponibles.
    """

    def __init__(
        self,
        memoria_total: int = 1024,
        tamaño_pagina: int = 64,
    ) -> None:
        """Inicializa el administrador de memoria.

        Args:
            memoria_total: Capacidad total de la memoria simulada.
            tamaño_pagina: Tamaño de cada página y marco de memoria.

        Raises:
            ValueError: Si los parámetros son inválidos.
        """
        if memoria_total <= 0 or tamaño_pagina <= 0:
            raise ValueError("memoria_total y tamaño_pagina deben ser positivos")
        if memoria_total % tamaño_pagina != 0:
            raise ValueError(
                f"memoria_total ({memoria_total}) debe ser múltiplo de "
                f"tamaño_pagina ({tamaño_pagina})"
            )

        self.memoria_total: int = memoria_total
        self.tamaño_pagina: int = tamaño_pagina
        self.total_marcos: int = memoria_total // tamaño_pagina

        self._marcos: list[MarcoMemoria] = [
            MarcoMemoria(numero_marco=i) for i in range(self.total_marcos)
        ]
        self._tablas_paginas: dict[int, list[Pagina]] = {}
        self._bloques: dict[int, BloqueMemoria] = {}
        self._siguiente_id_bloque: int = 1
        self._lock: threading.Lock = threading.Lock()

        logger.info(
            "AdministradorMemoria inicializado: total=%d, página=%d, marcos=%d",
            memoria_total,
            tamaño_pagina,
            self.total_marcos,
        )

    # ------------------------------------------------------------------
    # API Pública
    # ------------------------------------------------------------------

    def asignar_memoria(self, pid: int, tamaño: int) -> ResultadoOperacion:
        """Asigna páginas de memoria a un proceso.

        Calcula el número de páginas necesarias y busca marcos libres
        para mapearlas. La asignación es atómica: si no hay suficientes
        marcos, no se asigna nada.

        Args:
            pid: PID del proceso solicitante.
            tamaño: Unidades de memoria solicitadas.

        Returns:
            ResultadoOperacion con los detalles de la asignación.

        Raises:
            MemoriaInsuficiente: Si no hay suficientes marcos libres.
            ValueError: Si el tamaño es inválido.
        """
        if tamaño <= 0:
            return ResultadoOperacion(
                exito=False,
                mensaje="El tamaño de asignación debe ser positivo",
                datos=None,
                codigo_error=203,
            )

        with self._lock:
            paginas_necesarias = (tamaño + self.tamaño_pagina - 1) // self.tamaño_pagina
            marcos_libres = self._obtener_marcos_libres()

            if len(marcos_libres) < paginas_necesarias:
                disponible = len(marcos_libres) * self.tamaño_pagina
                raise MemoriaInsuficiente(tamaño, disponible)

            # Inicializar tabla de páginas del proceso si es nueva
            if pid not in self._tablas_paginas:
                self._tablas_paginas[pid] = []

            paginas_asignadas: list[Pagina] = []
            marcos_usados: list[int] = []

            pagina_inicio = len(self._tablas_paginas[pid])

            for i in range(paginas_necesarias):
                marco = marcos_libres[i]

                # Crear página virtual
                pagina = Pagina(
                    numero_pagina=pagina_inicio + i,
                    marco=marco.numero_marco,
                    en_memoria=True,
                    pid=pid,
                )
                paginas_asignadas.append(pagina)
                self._tablas_paginas[pid].append(pagina)

                # Marcar marco como ocupado
                marco.ocupado = True
                marco.pid_propietario = pid
                marco.pagina_asignada = pagina.numero_pagina

                marcos_usados.append(marco.numero_marco)

            # Crear registro de bloque
            id_bloque = self._siguiente_id_bloque
            self._siguiente_id_bloque += 1

            bloque = BloqueMemoria(
                id_bloque=id_bloque,
                tamaño=paginas_necesarias * self.tamaño_pagina,
                ocupado=True,
                pid_propietario=pid,
                direccion_inicio=marcos_usados[0] * self.tamaño_pagina,
                paginas=[p.numero_pagina for p in paginas_asignadas],
            )
            self._bloques[id_bloque] = bloque

            logger.info(
                "Memoria asignada: PID=%d, tamaño=%d, páginas=%d, marcos=%s",
                pid,
                tamaño,
                paginas_necesarias,
                marcos_usados,
            )

            return ResultadoOperacion(
                exito=True,
                mensaje=(
                    f"Asignadas {paginas_necesarias} página(s) a PID {pid} "
                    f"({paginas_necesarias * self.tamaño_pagina} unidades)"
                ),
                datos={
                    "id_bloque": id_bloque,
                    "pid": pid,
                    "paginas_asignadas": paginas_necesarias,
                    "memoria_asignada": paginas_necesarias * self.tamaño_pagina,
                    "marcos": marcos_usados,
                    "direccion_inicio": bloque.direccion_inicio,
                },
                codigo_error=0,
            )

    def liberar_memoria(self, pid: int) -> ResultadoOperacion:
        """Libera todas las páginas y marcos asignados a un proceso.

        Args:
            pid: PID del proceso cuya memoria se libera.

        Returns:
            ResultadoOperacion con las unidades liberadas.

        Raises:
            BloqueNoEncontrado: Si el proceso no tiene memoria asignada.
        """
        with self._lock:
            if pid not in self._tablas_paginas or not self._tablas_paginas[pid]:
                raise BloqueNoEncontrado(pid)

            paginas = self._tablas_paginas.pop(pid)
            marcos_liberados: list[int] = []

            for pagina in paginas:
                if pagina.en_memoria and 0 <= pagina.marco < self.total_marcos:
                    marco = self._marcos[pagina.marco]
                    marco.ocupado = False
                    marco.pid_propietario = -1
                    marco.pagina_asignada = -1
                    marcos_liberados.append(pagina.marco)

            # Limpiar bloques del proceso
            bloques_eliminados = [
                bid
                for bid, bloque in self._bloques.items()
                if bloque.pid_propietario == pid
            ]
            for bid in bloques_eliminados:
                del self._bloques[bid]

            memoria_liberada = len(marcos_liberados) * self.tamaño_pagina

            logger.info(
                "Memoria liberada: PID=%d, marcos=%s, total=%d unidades",
                pid,
                marcos_liberados,
                memoria_liberada,
            )

            return ResultadoOperacion(
                exito=True,
                mensaje=(
                    f"Liberadas {len(marcos_liberados)} página(s) de PID {pid} "
                    f"({memoria_liberada} unidades)"
                ),
                datos={
                    "pid": pid,
                    "marcos_liberados": marcos_liberados,
                    "memoria_liberada": memoria_liberada,
                },
                codigo_error=0,
            )

    def obtener_uso_memoria(self) -> ResultadoOperacion:
        """Retorna estadísticas globales de uso de memoria.

        Returns:
            ResultadoOperacion con métricas de memoria.
        """
        with self._lock:
            marcos_ocupados = sum(1 for m in self._marcos if m.ocupado)
            marcos_libres = self.total_marcos - marcos_ocupados

            uso_por_proceso: dict[int, int] = {}
            for pid, paginas in self._tablas_paginas.items():
                paginas_en_memoria = sum(1 for p in paginas if p.en_memoria)
                uso_por_proceso[pid] = paginas_en_memoria * self.tamaño_pagina

            return ResultadoOperacion(
                exito=True,
                mensaje="Estadísticas de uso de memoria",
                datos={
                    "memoria_total": self.memoria_total,
                    "tamaño_pagina": self.tamaño_pagina,
                    "total_marcos": self.total_marcos,
                    "marcos_ocupados": marcos_ocupados,
                    "marcos_libres": marcos_libres,
                    "memoria_usada": marcos_ocupados * self.tamaño_pagina,
                    "memoria_libre": marcos_libres * self.tamaño_pagina,
                    "porcentaje_uso": round(
                        (marcos_ocupados / self.total_marcos) * 100, 2
                    )
                    if self.total_marcos > 0
                    else 0.0,
                    "uso_por_proceso": uso_por_proceso,
                },
                codigo_error=0,
            )

    def obtener_memoria_proceso(self, pid: int) -> ResultadoOperacion:
        """Consulta las páginas asignadas a un proceso específico.

        Args:
            pid: PID del proceso a consultar.

        Returns:
            ResultadoOperacion con la lista de páginas del proceso.

        Raises:
            BloqueNoEncontrado: Si el proceso no tiene memoria asignada.
        """
        with self._lock:
            if pid not in self._tablas_paginas:
                raise BloqueNoEncontrado(pid)

            paginas = self._tablas_paginas[pid]
            datos_paginas = [
                {
                    "numero_pagina": p.numero_pagina,
                    "marco": p.marco,
                    "en_memoria": p.en_memoria,
                    "direccion_fisica": p.marco * self.tamaño_pagina
                    if p.en_memoria
                    else None,
                }
                for p in paginas
            ]

            return ResultadoOperacion(
                exito=True,
                mensaje=f"PID {pid}: {len(paginas)} página(s) asignada(s)",
                datos={
                    "pid": pid,
                    "total_paginas": len(paginas),
                    "memoria_total": len(paginas) * self.tamaño_pagina,
                    "paginas": datos_paginas,
                },
                codigo_error=0,
            )

    def compactar_memoria(self) -> ResultadoOperacion:
        """Reorganiza los marcos de memoria para eliminar fragmentación.

        Mueve todas las asignaciones al inicio de la memoria física,
        dejando los marcos libres contiguos al final.

        Returns:
            ResultadoOperacion con el resultado de la compactación.
        """
        with self._lock:
            marcos_ocupados = [m for m in self._marcos if m.ocupado]
            marcos_movidos = 0
            nuevo_indice = 0

            for marco in marcos_ocupados:
                if marco.numero_marco != nuevo_indice:
                    # Actualizar la página que referencia este marco
                    pid = marco.pid_propietario
                    if pid in self._tablas_paginas:
                        for pagina in self._tablas_paginas[pid]:
                            if pagina.marco == marco.numero_marco:
                                pagina.marco = nuevo_indice
                                break

                    # Mover datos del marco
                    marco_destino = self._marcos[nuevo_indice]
                    marco_destino.ocupado = True
                    marco_destino.pid_propietario = marco.pid_propietario
                    marco_destino.pagina_asignada = marco.pagina_asignada

                    marco.ocupado = False
                    marco.pid_propietario = -1
                    marco.pagina_asignada = -1

                    marcos_movidos += 1

                nuevo_indice += 1

            # Limpiar marcos restantes
            for i in range(nuevo_indice, self.total_marcos):
                self._marcos[i].ocupado = False
                self._marcos[i].pid_propietario = -1
                self._marcos[i].pagina_asignada = -1

            logger.info("Compactación completada: %d marcos movidos", marcos_movidos)

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Compactación completada: {marcos_movidos} marco(s) movido(s)",
                datos={
                    "marcos_movidos": marcos_movidos,
                    "marcos_ocupados": len(marcos_ocupados),
                    "marcos_libres": self.total_marcos - len(marcos_ocupados),
                },
                codigo_error=0,
            )

    def obtener_mapa_memoria(self) -> ResultadoOperacion:
        """Genera una representación del estado actual de la memoria.

        Returns:
            ResultadoOperacion con el mapa de marcos y su estado.
        """
        with self._lock:
            mapa = []
            for marco in self._marcos:
                mapa.append({
                    "marco": marco.numero_marco,
                    "direccion_inicio": marco.numero_marco * self.tamaño_pagina,
                    "direccion_fin": (marco.numero_marco + 1) * self.tamaño_pagina - 1,
                    "ocupado": marco.ocupado,
                    "pid": marco.pid_propietario if marco.ocupado else None,
                    "pagina": marco.pagina_asignada if marco.ocupado else None,
                })

            return ResultadoOperacion(
                exito=True,
                mensaje=f"Mapa de memoria: {self.total_marcos} marcos",
                datos=mapa,
                codigo_error=0,
            )

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------

    def _obtener_marcos_libres(self) -> list[MarcoMemoria]:
        """Retorna la lista de marcos no ocupados.

        Returns:
            Lista de MarcoMemoria disponibles, ordenados por índice.
        """
        return [m for m in self._marcos if not m.ocupado]
