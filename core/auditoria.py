"""Mapa de auditoria codigo_paciente <-> identidad real (seccion 9).

Este es el activo MAS SENSIBLE del sistema: revierte toda la anonimizacion de
una sola vez si se filtra. Al mismo tiempo tiene un uso legitimo — si el equipo
clinico necesita contactar a PAC-007 por su migrana, tiene que poder volver del
codigo a la persona. El diseno no oculta el vinculo: lo aisla.

Reglas de aislamiento que este modulo hace cumplir:

  - El archivo vive unicamente en data/internal/, nunca en data/output/.
  - Este es el UNICO modulo con acceso a ese archivo. Ni agente2_clasificador
    ni agente3_generador_salida lo importan (verificado por test automatico).
  - Esta en .gitignore desde el primer commit.
  - El pipeline lo escribe, pero no lo vuelve a leer en ninguna etapa posterior.
  - Nada de lo que escribe aqui aparece en logs, ni en modo debug.
"""

from __future__ import annotations

from pathlib import Path

from core.xlsx_io import escribir_hoja

COLUMNA_CODIGO = "codigo_paciente"
HOJA_MAPA = "Mapa_Auditoria"
NOMBRE_ARCHIVO_POR_DEFECTO = "historias_clinicas_con_codigo.xlsx"


def escribir_mapa(
    registros_con_codigo: list[tuple[str, dict[str, str]]],
    encabezados_entrada: list[str],
    dir_interno: Path,
    nombre_archivo: str = NOMBRE_ARCHIVO_POR_DEFECTO,
) -> Path:
    """Guarda la hoja de entrada original con `codigo_paciente` anadido.

    Se enriquece la hoja existente en vez de mantener una tabla de auditoria
    separada: evita tener dos copias desincronizables de los mismos datos
    identificables, y deja un unico punto de consulta para seguimiento.
    """
    dir_interno.mkdir(parents=True, exist_ok=True)
    ruta = dir_interno / nombre_archivo

    encabezados = [COLUMNA_CODIGO] + list(encabezados_entrada)
    filas: list[list[str]] = [encabezados]
    for codigo, registro in registros_con_codigo:
        filas.append([codigo] + [registro.get(c, "") for c in encabezados_entrada])

    escribir_hoja(str(ruta), HOJA_MAPA, filas)
    return ruta
