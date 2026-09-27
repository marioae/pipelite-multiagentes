"""Compara la corrida propia contra el oraculo de referencia (seccion 10.1).

Las 12 filas ya llenas de Formulario_Salida_Vitalis.xlsx no son una respuesta a
igualar caracter por caracter: son un set de referencia para verificar que los
campos categoricos coinciden o son clinicamente defendibles.

Ejecutar desde la raiz del proyecto:
    python3 comparar_con_oraculo.py

Ademas de mostrar el resultado en pantalla, lo guarda en
evidencias/salida_comparacion_oraculo.txt (en UTF-8) para el dossier.
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import config  # noqa: E402
from core.xlsx_io import leer_hojas  # noqa: E402

CAMPOS = ("enfermedad_probable", "nivel_riesgo", "confianza", "fuma", "consumo_sustancias")


def main() -> None:
    referencia = leer_hojas(str(config.ARCHIVO_REFERENCIA))["Formulario_Salida"]
    propia = leer_hojas(str(config.DIR_SALIDA / "Formulario_Salida_Dataset_Original.xlsx"))["Formulario_Salida"]

    encabezados = referencia[0]
    indices = {c: encabezados.index(c) for c in CAMPOS}
    ref = {f[0]: f for f in referencia[1:] if f and f[0].startswith("PAC")}
    mia = {f[0]: f for f in propia[1:]}

    def valor(fila: list[str], campo: str) -> str:
        i = indices[campo]
        return fila[i].strip() if i < len(fila) else ""

    divergencias: list[tuple[str, str, str, str]] = []
    comparaciones = 0
    for codigo in sorted(mia):
        if codigo not in ref:
            continue
        for campo in CAMPOS:
            comparaciones += 1
            a, b = valor(ref[codigo], campo), valor(mia[codigo], campo)
            if a.lower() != b.lower():
                divergencias.append((codigo, campo, a, b))

    print(f"{'CODIGO':9} {'CAMPO':22} {'REFERENCIA':38} {'ESTA CORRIDA':38}")
    print("-" * 112)
    for codigo, campo, a, b in divergencias:
        print(f"{codigo:9} {campo:22} {a[:36]:38} {b[:36]:38}")
    print("-" * 112)

    coincidencias = comparaciones - len(divergencias)
    pct = 100 * coincidencias / comparaciones if comparaciones else 0
    print(f"Coincidencias: {coincidencias}/{comparaciones} ({pct:.0f}%)")
    print(f"Divergencias : {len(divergencias)} — justificadas en evidencias/comparacion_con_oraculo.md")

    # Regla indeterminado en ambas fuentes.
    i_enf, i_conf = indices["enfermedad_probable"], indices["confianza"]
    for etiqueta, datos in (("referencia", ref), ("esta corrida", mia)):
        indet = [c for c, f in datos.items() if valor(f, "enfermedad_probable").lower() == "indeterminado"]
        print(f"\n'indeterminado' en {etiqueta}: {len(indet)} -> {sorted(indet)}")
        malos = [c for c in indet if valor(datos[c], "confianza").lower() != "baja"]
        print(f"  con confianza distinta de 'baja': {len(malos)} {malos if malos else ''}")


if __name__ == "__main__":
    # Se escribe el archivo directamente en vez de pedir "> archivo.txt": en
    # Windows esa redireccion usa la codificacion de la consola y rompe las tildes.
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    print(buffer.getvalue(), end="")
    ruta = config.DIR_EVIDENCIAS / "salida_comparacion_oraculo.txt"
    ruta.write_text(buffer.getvalue(), encoding="utf-8")
    print(f"\nResultado guardado en evidencias/{ruta.name}")
