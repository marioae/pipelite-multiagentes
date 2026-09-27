"""Agente 3 — Generador de salida (seccion 7 del documento de arquitectura).

Naturaleza: DETERMINISTICO, sin LLM. Automatizacion pura: el mapeo de columnas
es siempre el mismo y no hay ambiguedad en la entrada.

Incluye la ultima linea de defensa del sistema: el escaneo anti-fuga se corre
sobre el .xlsx ya escrito y releido desde disco, no sobre los datos en memoria.
Es la unica forma de verificar lo que realmente se entrega.
"""

from __future__ import annotations

from pathlib import Path

import config
from core.contratos import ENCABEZADOS_SALIDA, RegistroClasificado, RegistroFallido
from core.verificacion_antifuga import escanear_archivo_final
from core.xlsx_io import escribir_hoja, leer_hojas

# Ancho de cada columna de ENCABEZADOS_SALIDA, en caracteres. La cuarta
# (comportamiento_observado) es la mas ancha porque lleva el texto largo.
ANCHOS_COLUMNAS_SALIDA = [16, 30, 13, 62, 12, 34, 10, 20]


class FugaEnArchivoFinal(Exception):
    """El archivo generado contiene identificadores. No es entregable."""


def generar_salida(
    clasificados: list[RegistroClasificado],
    fallidos: list[RegistroFallido],
    registros_originales: list[dict[str, str]],
    ruta_salida: Path,
    nombre_hoja: str = config.HOJA_SALIDA,
) -> dict:
    """Escribe el .xlsx final y lo verifica. Devuelve un resumen de la corrida.

    El archivo contiene unicamente la hoja de salida: sin hoja de entrada, sin
    mapa de auditoria, sin columnas adicionales (seccion 7, paso 5). Tampoco
    lleva la fila de ejemplo resaltada del archivo de referencia, que la propia
    leyenda del original advierte no mezclar con resultados reales.
    """
    # Primero los clasificados y despues los fallidos, cada grupo por codigo.
    filas: list[list[str]] = [list(ENCABEZADOS_SALIDA)]
    filas += [r.como_fila() for r in sorted(clasificados, key=lambda r: r.codigo_paciente)]
    filas += [f.como_fila() for f in sorted(fallidos, key=lambda f: f.codigo_paciente)]

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    escribir_hoja(str(ruta_salida), nombre_hoja, filas, anchos=ANCHOS_COLUMNAS_SALIDA)

    # --- Verificacion anti-fuga final, sobre el archivo releido desde disco ---
    celdas = leer_hojas(str(ruta_salida)).get(nombre_hoja, [])
    hallazgos = escanear_archivo_final(celdas, registros_originales)
    if hallazgos:
        raise FugaEnArchivoFinal(
            f"El archivo {ruta_salida.name} contiene {len(hallazgos)} identificador(es): {hallazgos}"
        )

    return {
        "archivo": str(ruta_salida),
        "filas_escritas": len(filas) - 1,
        "clasificados": len(clasificados),
        "fallidos": len(fallidos),
        "verificacion_antifuga": "LIMPIO",
        "celdas_escaneadas": sum(len(f) for f in celdas),
    }
