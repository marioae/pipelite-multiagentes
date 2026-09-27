"""Verificacion anti-fuga de dos capas (secciones 5.4, 7.4 y 8 del documento de arquitectura).

Esto NO es un cuarto agente: es una funcion determinista que corre en cada
transicion de etapa. Nunca "interpreta" ni decide caso por caso que dato es
seguro copiar — aplica siempre la misma regla y puede detener el pipeline.

Capa 1 (exacta)  : las cadenas identificadoras tal cual aparecen en la fila.
Capa 2 (red de seguridad): variantes con puntuacion alterada, mayusculas y
                   minusculas, secuencias de digitos, y componentes sueltos
                   del nombre de 3 o mas caracteres.

Se usa en dos momentos distintos, con la misma logica:

  - buscar_residuos        -> tras el Agente 1, sobre el texto de UN registro.
  - escanear_archivo_final -> tras el Agente 3, sobre TODO el .xlsx entregable.
"""

from __future__ import annotations

import re
import unicodedata

from core.contratos import (
    COLUMNA_DIRECCION,
    COLUMNA_ID_REGISTRO,
    COLUMNA_NOMBRE,
    COLUMNAS_IDENTIFICADORAS,
    COLUMNAS_NUMERICAS,
)
from core.reglas_anonimizacion import PALABRAS_PROTEGIDAS

# Una cedula o telefono se considera filtrado si reaparecen al menos 6 digitos
# seguidos. Menos que eso produciria falsos positivos con edades, fechas o cifras
# de laboratorio.
LONGITUD_MINIMA_DIGITOS = 6
# Longitud minima de la via ("Cl 10 #5-20") para buscarla sin la ciudad.
LONGITUD_MINIMA_VIA = 5
# Componentes del nombre mas cortos que esto ("de", "la") no se buscan sueltos.
LONGITUD_MINIMA_COMPONENTE = 3


class FugaDetectada(Exception):
    """Un identificador sobrevivio donde no debia. Detiene el registro."""

    def __init__(self, codigo: str, residuos: list[str]):
        self.codigo = codigo
        self.residuos = residuos
        super().__init__(
            f"{codigo}: se detectaron {len(residuos)} residuo(s) identificador(es): {residuos}"
        )


class _TextoInspeccionado:
    """El texto a revisar, preparado una sola vez en las tres formas que usa la busqueda."""

    def __init__(self, texto: str):
        self.original_minusculas = (texto or "").lower()
        self.normalizado = _normalizar(texto)
        self.secuencias_digitos = _secuencias_de_digitos(texto)


def _normalizar(texto: str) -> str:
    """Minusculas sin acentos ni puntuacion, para comparar de forma laxa.

    Ejemplo: "Suárez-Rincón, Cl. 10" -> "suarez rincon cl 10".
    """
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^0-9a-z]+", " ", sin_acentos.lower()).strip()


def _secuencias_de_digitos(texto: str) -> set[str]:
    """Todas las corridas largas de digitos, ignorando separadores internos.

    Asi "52.884.117" y "52 884 117" se detectan igual que "52884117".
    """
    compacto = re.sub(r"[.\-\s,]", "", texto or "")
    return set(re.findall(r"\d{%d,}" % LONGITUD_MINIMA_DIGITOS, compacto))


def _residuos_de_registro(inspeccionado: _TextoInspeccionado, registro: dict[str, str]) -> list[str]:
    """Busca los 4 identificadores de un registro dentro del texto inspeccionado.

    Devuelve una descripcion por cada residuo encontrado; lista vacia = limpio.
    """
    residuos: list[str] = []

    for columna in COLUMNAS_IDENTIFICADORAS:
        valor = (registro.get(columna) or "").strip()
        if not valor:
            continue

        # --- Capa 1: coincidencia exacta, sin distinguir mayusculas ---
        if valor.lower() in inspeccionado.original_minusculas:
            residuos.append(f"{columna}: '{valor}' (capa 1, coincidencia exacta)")
            continue

        # --- Capa 2: red de seguridad, segun el tipo de dato ---
        if columna in COLUMNAS_NUMERICAS:
            digitos = re.sub(r"\D", "", valor)
            if len(digitos) >= LONGITUD_MINIMA_DIGITOS and digitos in inspeccionado.secuencias_digitos:
                residuos.append(f"{columna}: digitos '{digitos}' (capa 2, puntuacion alterada)")

        elif columna == COLUMNA_NOMBRE:
            for componente in re.split(r"\s+", valor):
                if len(componente) < LONGITUD_MINIMA_COMPONENTE or componente.lower() in PALABRAS_PROTEGIDAS:
                    continue
                normalizado = _normalizar(componente)
                if normalizado and re.search(rf"\b{re.escape(normalizado)}\b", inspeccionado.normalizado):
                    residuos.append(f"{columna}: componente '{componente}' (capa 2, fragmento suelto)")

        elif columna == COLUMNA_DIRECCION:
            via = valor.split(",")[0].strip()
            via_normalizada = _normalizar(via)
            if len(via_normalizada) >= LONGITUD_MINIMA_VIA and via_normalizada in inspeccionado.normalizado:
                residuos.append(f"{columna}: via '{via}' (capa 2, normalizada)")

    return residuos


def buscar_residuos(texto_anonimizado: str, registro: dict[str, str]) -> list[str]:
    """Devuelve la lista de identificadores que sobrevivieron. Vacia = limpio."""
    return _residuos_de_registro(_TextoInspeccionado(texto_anonimizado), registro)


def exigir_sin_residuos(codigo: str, texto_anonimizado: str, registro: dict[str, str]) -> None:
    """Lanza FugaDetectada si algo sobrevivio. No 'arregla en silencio'."""
    residuos = buscar_residuos(texto_anonimizado, registro)
    if residuos:
        raise FugaDetectada(codigo, residuos)


def escanear_archivo_final(celdas: list[list[str]], registros_originales: list[dict[str, str]]) -> list[str]:
    """Ultima linea de defensa (seccion 7, paso 4).

    Se corre sobre el .xlsx ya escrito y releido desde disco, no sobre los
    datos en memoria: es la unica forma de verificar lo que realmente se
    entrega. Busca los identificadores de TODOS los pacientes en TODAS las
    celdas, para detectar tambien un dato cruzado de un paciente a otro.
    """
    texto_completo = "\n".join(" ".join(fila) for fila in celdas)
    inspeccionado = _TextoInspeccionado(texto_completo)

    hallazgos: list[str] = []
    for registro in registros_originales:
        id_registro = registro.get(COLUMNA_ID_REGISTRO, "?")
        for residuo in _residuos_de_registro(inspeccionado, registro):
            hallazgos.append(f"{id_registro}/{residuo} aparece en la salida")
    return hallazgos
