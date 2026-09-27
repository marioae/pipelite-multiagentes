"""Lectura y escritura de .xlsx usando unicamente la libreria estandar.

Motivo de esta decision (desvio documentado frente a la seccion 11 del
documento de arquitectura, que propone openpyxl + pandas):

    En el equipo donde se ejecuta este pipeline no hay `pip` disponible y la
    instalacion de paquetes requiere privilegios de administrador. Reescribir
    la E/S de Excel sobre `zipfile` + `xml.etree` elimina toda dependencia
    externa y permite que el pipeline corra sin instalar nada.

    Es ademas coherente con la seccion 5 del documento de arquitectura, que
    exige que los agentes 1 y 3 sean "lo mas simple, mas auditable y mas
    facil de probar exhaustivamente de todo el pipeline": menos dependencias
    es menos superficie que auditar.

Un .xlsx es un ZIP con XML dentro. Este modulo cubre el subconjunto que el
pipeline necesita: leer celdas de texto y escribir hojas nuevas.
"""

from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


# --------------------------------------------------------------------------
# Lectura
# --------------------------------------------------------------------------

def _columna_a_indice(ref: str) -> int:
    """Convierte la referencia de celda ('B7') al indice de columna 0-based."""
    letras = re.match(r"([A-Z]+)", ref or "A").group(1)
    n = 0
    for ch in letras:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def leer_hojas(ruta: str) -> dict[str, list[list[str]]]:
    """Devuelve {nombre_de_hoja: [[celda, ...], ...]} con todo el texto.

    Las filas se devuelven densas: las celdas vacias intermedias se rellenan
    con cadena vacia para que los indices de columna sean estables.
    """
    with zipfile.ZipFile(ruta) as z:
        nombres = z.namelist()

        # Cadenas compartidas (cuando el archivo no usa inlineStr).
        compartidas: list[str] = []
        if "xl/sharedStrings.xml" in nombres:
            raiz = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in raiz:
                compartidas.append("".join(t.text or "" for t in si.iter(f"{{{NS_MAIN}}}t")))

        # Mapa rId -> archivo de hoja. El Target puede venir como ruta absoluta
        # desde la raiz del paquete ("/xl/worksheets/sheet1.xml") o relativa a
        # xl/ ("worksheets/sheet1.xml"); ambas formas son validas en OOXML.
        destino_por_rid: dict[str, str] = {}
        if "xl/_rels/workbook.xml.rels" in nombres:
            raiz = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            for rel in raiz:
                destino = rel.get("Target") or ""
                destino_por_rid[rel.get("Id")] = (
                    destino.lstrip("/") if destino.startswith("/") else "xl/" + destino
                )

        # Orden y nombre de las hojas segun el workbook.
        hojas: dict[str, str] = {}
        libro = ET.fromstring(z.read("xl/workbook.xml"))
        for i, hoja in enumerate(libro.iter(f"{{{NS_MAIN}}}sheet"), start=1):
            rid = hoja.get(f"{{{NS_REL_DOC}}}id")
            ruta_hoja = destino_por_rid.get(rid) or f"xl/worksheets/sheet{i}.xml"
            hojas[hoja.get("name")] = ruta_hoja

        resultado: dict[str, list[list[str]]] = {}
        for nombre, ruta_hoja in hojas.items():
            if ruta_hoja not in nombres:
                resultado[nombre] = []
                continue
            resultado[nombre] = _leer_filas(z.read(ruta_hoja), compartidas)
        return resultado


def _leer_filas(xml_bytes: bytes, compartidas: list[str]) -> list[list[str]]:
    raiz = ET.fromstring(xml_bytes)
    filas: list[list[str]] = []
    for fila in raiz.iter(f"{{{NS_MAIN}}}row"):
        celdas: list[str] = []
        for c in fila.iter(f"{{{NS_MAIN}}}c"):
            idx = _columna_a_indice(c.get("r", ""))
            while len(celdas) < idx:
                celdas.append("")
            tipo = c.get("t")
            if tipo == "inlineStr":
                nodo = c.find(f"{{{NS_MAIN}}}is")
                valor = "".join(t.text or "" for t in nodo.iter(f"{{{NS_MAIN}}}t")) if nodo is not None else ""
            else:
                v = c.find(f"{{{NS_MAIN}}}v")
                if v is None or v.text is None:
                    valor = ""
                elif tipo == "s":
                    valor = compartidas[int(v.text)]
                else:
                    valor = v.text
            celdas.append(valor)
        while celdas and celdas[-1] == "":
            celdas.pop()
        if celdas:
            filas.append(celdas)
    return filas


def leer_tabla(ruta: str, hoja: str, fila_encabezado: int = 0) -> list[dict[str, str]]:
    """Lee una hoja como lista de diccionarios usando `fila_encabezado`."""
    filas = leer_hojas(ruta).get(hoja, [])
    if len(filas) <= fila_encabezado:
        return []
    encabezados = [h.strip() for h in filas[fila_encabezado]]
    registros: list[dict[str, str]] = []
    for fila in filas[fila_encabezado + 1:]:
        if not any(v.strip() for v in fila):
            continue
        registro = {}
        for i, clave in enumerate(encabezados):
            registro[clave] = fila[i] if i < len(fila) else ""
        registros.append(registro)
    return registros


# --------------------------------------------------------------------------
# Escritura
# --------------------------------------------------------------------------

_RELS_RAIZ = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

# Estilo 0 = normal (Arial 10). Estilo 1 = encabezado (Arial 10 negrita, fondo gris claro).
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="10"/><name val="Arial"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Arial"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F3A5F"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
</cellXfs>
</styleSheet>"""


def _ref_columna(idx: int) -> str:
    letras = ""
    idx += 1
    while idx:
        idx, resto = divmod(idx - 1, 26)
        letras = chr(ord("A") + resto) + letras
    return letras


def _xml_hoja(filas: list[list[str]], anchos: list[int] | None) -> str:
    partes: list[str] = []
    for r, fila in enumerate(filas, start=1):
        celdas = []
        estilo = ' s="1"' if r == 1 else ' s="0"'
        for c, valor in enumerate(fila):
            texto = escape("" if valor is None else str(valor))
            celdas.append(
                f'<c r="{_ref_columna(c)}{r}"{estilo} t="inlineStr"><is><t xml:space="preserve">{texto}</t></is></c>'
            )
        partes.append(f'<row r="{r}">{"".join(celdas)}</row>')

    cols = ""
    if anchos:
        defs = "".join(
            f'<col min="{i+1}" max="{i+1}" width="{w}" customWidth="1"/>'
            for i, w in enumerate(anchos)
        )
        cols = f"<cols>{defs}</cols>"

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{NS_MAIN}">'
        f'<sheetFormatPr baseColWidth="8" defaultRowHeight="15"/>{cols}'
        f'<sheetData>{"".join(partes)}</sheetData></worksheet>'
    )


def escribir_libro(ruta: str,
                   hojas: list[tuple[str, list[list[str]], list[int] | None]]) -> None:
    """Escribe un .xlsx con varias hojas, en el orden dado: [(nombre, filas, anchos), ...].

    La primera fila de cada hoja se estiliza como encabezado. Todas las celdas
    se escriben como `inlineStr`, igual que los archivos originales del curso,
    de modo que no hace falta tabla de cadenas compartidas.
    """
    n = len(hojas)
    tipos_hojas = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/'
        f'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, n + 1)
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f'{tipos_hojas}'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '</Types>'
    )
    rels_hojas = "".join(
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        f'relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, n + 1)
    )
    rels_libro = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'{rels_hojas}'
        f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/styles" Target="styles.xml"/>'
        '</Relationships>'
    )
    hojas_xml = "".join(
        f'<sheet name="{escape(nombre)}" sheetId="{i}" r:id="rId{i}"/>'
        for i, (nombre, _, _) in enumerate(hojas, start=1)
    )
    libro = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL_DOC}">'
        f'<sheets>{hojas_xml}</sheets>'
        "</workbook>"
    )

    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", _RELS_RAIZ)
        z.writestr("xl/workbook.xml", libro)
        z.writestr("xl/_rels/workbook.xml.rels", rels_libro)
        z.writestr("xl/styles.xml", _STYLES)
        for i, (_, filas, anchos) in enumerate(hojas, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _xml_hoja(filas, anchos))


def escribir_hoja(ruta: str, nombre_hoja: str, filas: list[list[str]],
                  anchos: list[int] | None = None) -> None:
    """Escribe un .xlsx de una sola hoja. La primera fila se estiliza como encabezado."""
    escribir_libro(ruta, [(nombre_hoja, filas, anchos)])
