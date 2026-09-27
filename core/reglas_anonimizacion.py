"""Reglas de sustitucion de identificadores (seccion 5 del documento de arquitectura).

Todos los tokens a eliminar se derivan de las columnas estructuradas de la
propia fila. Nunca se inventan ni se infieren del texto libre: si un dato no
esta en una columna identificadora, este modulo no lo toca.

La sustitucion es deliberadamente agresiva (fail-closed): ante la duda se
redacta de mas. Perder un fragmento de texto clinico es recuperable; dejar
escapar un identificador hacia un proveedor externo no lo es.
"""

from __future__ import annotations

import re

from core.contratos import COLUMNA_CEDULA, COLUMNA_DIRECCION, COLUMNA_NOMBRE, COLUMNA_TELEFONO

# Texto que reemplaza a cada identificador eliminado.
MARCADOR = "[ANON]"

# Letras y digitos del espanol. Se usan como "borde de palabra" propio porque
# \b de Python no funciona junto a signos como '#' o '.'.
_CARACTER_DE_PALABRA = "0-9A-Za-zÁÉÍÓÚáéíóúÑñ"

# Formas en que suele escribirse el prefijo de una cedula: "CC 52...", "C.C. 52...".
PREFIJOS_CEDULA = ("CC", "C.C.", "CC.", "cc")

# Palabras que nunca se redactan aunque coincidan con un componente del nombre.
# Evita destruir informacion clinica por una colision de vocabulario.
PALABRAS_PROTEGIDAS = frozenset(
    {
        "del", "los", "las", "san", "santa", "vive", "sola", "solo",
        "año", "años", "sin", "con", "por", "para", "que", "una", "uno",
    }
)


def generar_codigo_paciente(indice: int) -> str:
    """PAC-001, PAC-002, ... segun el orden de ID_Registro (seccion 5, paso 1)."""
    return f"PAC-{indice:03d}"


def _solo_digitos(valor: str) -> str:
    """'52.884.117' -> '52884117'."""
    return re.sub(r"\D", "", valor or "")


def variantes_de_numero(valor: str) -> list[str]:
    """Cedula o telefono en todos los formatos en que puede aparecer escrito."""
    digitos = _solo_digitos(valor)
    if not digitos:
        return []

    variantes = {valor.strip(), digitos}

    # Agrupacion de miles con puntos y con comas (52.884.117 / 52,884,117).
    for sep in (".", ",", " "):
        grupos = []
        resto = digitos
        while len(resto) > 3:
            grupos.insert(0, resto[-3:])
            resto = resto[:-3]
        if resto:
            grupos.insert(0, resto)
        variantes.add(sep.join(grupos))

    # Formato telefonico 300-555-0111 / 300 555 0111 / 3005550111.
    if len(digitos) == 10:
        for sep in ("-", " ", "."):
            variantes.add(f"{digitos[:3]}{sep}{digitos[3:6]}{sep}{digitos[6:]}")

    # Prefijos de documento, pegados y separados.
    con_prefijo = set()
    for v in variantes:
        for prefijo in PREFIJOS_CEDULA:
            con_prefijo.add(f"{prefijo} {v}")
            con_prefijo.add(f"{prefijo}{v}")
    variantes |= con_prefijo

    return [v for v in variantes if len(v) >= 4]


def variantes_de_nombre(valor: str) -> list[str]:
    """Nombre completo y cada componente por separado (seccion 5, paso 2)."""
    nombre = (valor or "").strip()
    if not nombre:
        return []
    variantes = {nombre}
    componentes = [c for c in re.split(r"\s+", nombre) if len(c) >= 3]
    for c in componentes:
        if c.lower() not in PALABRAS_PROTEGIDAS:
            variantes.add(c)
    # Pares consecutivos: "Marcela Suárez", "Suárez Rincón".
    partes = re.split(r"\s+", nombre)
    for i in range(len(partes) - 1):
        variantes.add(f"{partes[i]} {partes[i + 1]}")
    return sorted(variantes, key=len, reverse=True)


def variantes_de_direccion(valor: str) -> list[str]:
    """Direccion completa y el fragmento de via sin la ciudad."""
    direccion = (valor or "").strip()
    if not direccion:
        return []
    variantes = {direccion}
    # "Cra 45 #12-30, Bogotá" -> tambien "Cra 45 #12-30"
    if "," in direccion:
        via = direccion.split(",")[0].strip()
        if len(via) >= 5:
            variantes.add(via)
    return sorted(variantes, key=len, reverse=True)


def construir_tokens(registro: dict[str, str]) -> list[str]:
    """Lista completa de cadenas a eliminar, de la mas larga a la mas corta.

    El orden importa: se sustituye primero el nombre completo y despues sus
    componentes, para no dejar fragmentos sueltos tras un reemplazo parcial.
    """
    tokens: list[str] = []
    tokens += variantes_de_nombre(registro.get(COLUMNA_NOMBRE, ""))
    tokens += variantes_de_numero(registro.get(COLUMNA_CEDULA, ""))
    tokens += variantes_de_direccion(registro.get(COLUMNA_DIRECCION, ""))
    tokens += variantes_de_numero(registro.get(COLUMNA_TELEFONO, ""))

    # De mayor a menor longitud, sin duplicados, preservando el orden.
    vistos: set[str] = set()
    ordenados: list[str] = []
    for t in sorted(tokens, key=len, reverse=True):
        clave = t.lower()
        if t.strip() and clave not in vistos:
            vistos.add(clave)
            ordenados.append(t)
    return ordenados


def anonimizar_texto(texto: str, tokens: list[str]) -> str:
    """Sustituye cada token por el marcador y colapsa marcadores contiguos."""
    resultado = texto or ""
    for token in tokens:
        # Solo se reemplaza el token aislado, nunca como parte de otra palabra.
        patron = re.compile(
            rf"(?<![{_CARACTER_DE_PALABRA}]){re.escape(token)}(?![{_CARACTER_DE_PALABRA}])",
            re.IGNORECASE,
        )
        resultado = patron.sub(MARCADOR, resultado)

    # "CC [ANON]" y "[ANON], [ANON]" quedan feos y no aportan: se compactan.
    resultado = re.sub(r"(?:C\.?C\.?|cc)\s*" + re.escape(MARCADOR), MARCADOR, resultado)
    resultado = re.sub(r"(?:" + re.escape(MARCADOR) + r"[,;]?\s*){2,}", MARCADOR + " ", resultado)
    resultado = re.sub(r"\s{2,}", " ", resultado)
    return resultado.strip()
