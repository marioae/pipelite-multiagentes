"""Orquestador del pipeline multiagente — Clinica Vitalis.

Coordina las 3 etapas y aplica los gates de validacion entre ellas. No
interpreta datos medicos: solo pasa el resultado de una etapa a la siguiente,
en orden, y detiene el pipeline si una etapa falla o produce datos incompletos.

    Etapa 1  Agente 1  anonimiza         (reglas fijas, sin LLM)
    Etapa 2  Agente 2  clasifica         (el unico con criterio / LLM)
    Etapa 3  Agente 3  escribe el .xlsx  (reglas fijas, sin LLM) + escaneo anti-fuga

Uso:
    python3 orquestador.py --fuente propias   --track b
    python3 orquestador.py --fuente dataset   --track b
    python3 orquestador.py --fuente propias   --track a     # requiere OPENROUTER_API_KEY
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import config
from agents.agente1_anonimizador import FalloAnonimizacion, ResultadoAnonimizacion, anonimizar_lote
from agents.agente2_clasificador import clasificar_via_openrouter, clasificar_via_track_b
from agents.agente3_generador_salida import generar_salida
from core import auditoria
from core.contratos import RegistroClasificado, RegistroFallido
from core.xlsx_io import escribir_hoja, leer_tabla
from data.historias_propias import ENCABEZADOS, HISTORIAS_PROPIAS, como_filas

# Ancho de cada columna del entregable 1, en el orden de ENCABEZADOS.
ANCHOS_HISTORIAS_PROPIAS = [12, 30, 16, 26, 16, 17, 105]


def _cargar_registros(fuente: str) -> tuple[list[dict[str, str]], list[str], str]:
    """Devuelve (registros, encabezados, etiqueta) segun la fuente elegida.

    La etiqueta se usa en el nombre de todos los archivos que produce la corrida.
    """
    if fuente == "dataset":
        registros = leer_tabla(str(config.ARCHIVO_REFERENCIA), config.HOJA_ENTRADA)
        if not registros:
            raise SystemExit(f"No se leyeron registros de {config.ARCHIVO_REFERENCIA}")
        return registros, list(registros[0].keys()), "Dataset_Original"

    if fuente == "propias":
        return list(HISTORIAS_PROPIAS), list(ENCABEZADOS), "Historias_Propias"

    raise SystemExit(f"Fuente desconocida: {fuente}")


def _exportar_historias_propias() -> Path:
    """Entregable 1 del reto: las 3 historias propias como archivo .xlsx.

    Se genera dentro del orquestador y no con un script aparte, para que una
    reconstruccion desde cero produzca los 4 entregables sin pasos manuales.
    """
    config.DIR_SALIDA.mkdir(parents=True, exist_ok=True)
    ruta = config.DIR_SALIDA / "Historias_Propias_Reto.xlsx"
    escribir_hoja(str(ruta), config.HOJA_ENTRADA, como_filas(), anchos=ANCHOS_HISTORIAS_PROPIAS)
    return ruta


def _etapa1_anonimizar(
    registros: list[dict[str, str]], encabezados: list[str], etiqueta: str,
) -> tuple[list[ResultadoAnonimizacion], list[FalloAnonimizacion]]:
    """Agente 1 + mapa de auditoria. Devuelve (anonimizados, fallidos)."""
    print("ETAPA 1 · Anonimizacion (deterministica, sin LLM, sin red)")
    anonimizados, fallidos = anonimizar_lote(registros)
    print(f"  Anonimizados sin residuos : {len(anonimizados)}/{len(registros)}")
    for codigo, motivo in fallidos:
        print(f"  DETENIDO {codigo}: {motivo}")

    # Mapa de auditoria: unico punto con el vinculo codigo <-> identidad.
    ruta_mapa = auditoria.escribir_mapa(
        [(r.paquete.codigo_paciente, r.registro_original) for r in anonimizados],
        encabezados,
        config.DIR_INTERNO,
        nombre_archivo=f"mapa_auditoria_{etiqueta}.xlsx",
    )
    print(f"  Mapa de auditoria         : data/internal/{ruta_mapa.name} (fuera de output, en .gitignore)\n")
    return anonimizados, fallidos


def _etapa2_clasificar(
    anonimizados: list[ResultadoAnonimizacion], track: str, etiqueta: str,
) -> tuple[list[RegistroClasificado], list[RegistroFallido]]:
    """Agente 2. Solo recibe el paquete anonimizado, nunca el registro original.

    Devuelve (clasificados, fallidos_en_esta_etapa).
    """
    print(f"ETAPA 2 · Clasificacion clinica (Track {track.upper()})")
    clasificados: list[RegistroClasificado] = []
    fallidos: list[RegistroFallido] = []
    ruta_respuestas_track_b = config.RAIZ / "data" / f"clasificaciones_track_b_{etiqueta}.json"

    for resultado in anonimizados:
        paquete = resultado.paquete
        try:
            if track == "a":
                clasificados.append(clasificar_via_openrouter(paquete))
            else:
                clasificados.append(clasificar_via_track_b(paquete, ruta_respuestas_track_b))
        except Exception as e:  # noqa: BLE001 — cualquier fallo se marca, nunca se inventa una fila
            fallidos.append(
                RegistroFallido(paquete.codigo_paciente, "etapa 2 (clasificacion)", str(e)[:180])
            )
            print(f"  ERROR {paquete.codigo_paciente}: {type(e).__name__}")

    indeterminados = [r.codigo_paciente for r in clasificados if r.es_indeterminado]
    print(f"  Clasificados              : {len(clasificados)}/{len(anonimizados)}")
    print(f"  Marcados 'indeterminado'  : {len(indeterminados)} "
          f"({', '.join(indeterminados) or 'ninguno'})\n")
    return clasificados, fallidos


def _etapa3_escribir(
    clasificados: list[RegistroClasificado], fallidos: list[RegistroFallido],
    registros: list[dict[str, str]], etiqueta: str,
) -> dict:
    """Agente 3: escribe el .xlsx final y lo escanea releido desde disco."""
    print("ETAPA 3 · Escritura y verificacion anti-fuga final")
    ruta_salida = config.DIR_SALIDA / f"Formulario_Salida_{etiqueta}.xlsx"
    resumen = generar_salida(clasificados, fallidos, registros, ruta_salida)
    print(f"  Archivo                   : data/output/{Path(resumen['archivo']).name}")
    print(f"  Filas escritas            : {resumen['filas_escritas']}")
    print(f"  Celdas escaneadas         : {resumen['celdas_escaneadas']}")
    print(f"  Verificacion anti-fuga    : {resumen['verificacion_antifuga']}\n")
    return resumen


def ejecutar(fuente: str, track: str) -> dict:
    """Corre las 3 etapas en orden y devuelve el resumen de la corrida."""
    registros, encabezados, etiqueta = _cargar_registros(fuente)

    print(f"\n{'=' * 72}")
    print("  PIPELINE MULTIAGENTE — CLINICA VITALIS")
    print(f"  Fuente: {etiqueta} ({len(registros)} registros)   ·   Track: {track.upper()}")
    print(f"{'=' * 72}\n")

    if fuente == "propias":
        ruta_entrada = _exportar_historias_propias()
        print(f"ENTREGABLE 1 · Historias propias -> data/output/{ruta_entrada.name}\n")

    anonimizados, fallos_etapa1 = _etapa1_anonimizar(registros, encabezados, etiqueta)
    clasificados, fallos_etapa2 = _etapa2_clasificar(anonimizados, track, etiqueta)

    # Los fallos de ambas etapas llegan a la salida como filas "no procesada".
    fallidos = [RegistroFallido(codigo, "etapa 1 (anonimizacion)", motivo)
                for codigo, motivo in fallos_etapa1] + fallos_etapa2
    resumen = _etapa3_escribir(clasificados, fallidos, registros, etiqueta)

    resumen.update(
        # Ruta relativa: la evidencia no debe depender de la maquina donde se corrio.
        archivo=Path(resumen["archivo"]).resolve().relative_to(config.RAIZ).as_posix(),
        fuente=etiqueta,
        track=track,
        registros_entrada=len(registros),
        indeterminados=[r.codigo_paciente for r in clasificados if r.es_indeterminado],
    )
    return resumen


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline multiagente Clinica Vitalis")
    parser.add_argument("--fuente", choices=("propias", "dataset"), default="propias",
                        help="propias = las 3 historias del reto; dataset = las 12 de clase")
    parser.add_argument("--track", choices=("a", "b"), default="b",
                        help="a = OpenRouter (requiere API key); b = clasificacion orquestada en chat")
    args = parser.parse_args()

    resumen = ejecutar(args.fuente, args.track)

    config.DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    ruta_resumen = config.DIR_EVIDENCIAS / f"resumen_corrida_{resumen['fuente']}.json"
    ruta_resumen.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Resumen de la corrida -> evidencias/{ruta_resumen.name}")


if __name__ == "__main__":
    main()
