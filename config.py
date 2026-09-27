"""Configuracion del pipeline. Nunca valores hardcodeados (seccion 6 y 11).

La API key se lee SIEMPRE de variable de entorno. No aparece en el codigo, no
se sube al repositorio y no se escribe en logs. El modelo tambien es un valor
de configuracion externo, para poder cambiarlo sin tocar logica.
"""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

DIR_ENTRADA = RAIZ / "data" / "input"
DIR_INTERNO = RAIZ / "data" / "internal"   # mapa de auditoria — nunca en output, nunca en git
DIR_SALIDA = RAIZ / "data" / "output"
DIR_EVIDENCIAS = RAIZ / "evidencias"

ARCHIVO_REFERENCIA = DIR_ENTRADA / "Formulario_Salida_Vitalis.xlsx"
ARCHIVO_HISTORIAS_PRUEBA = DIR_ENTRADA / "Historias_de_Prueba_Pipeline_Clinico.xlsx"

HOJA_ENTRADA = "Historias_Clinicas_Entrada"
HOJA_SALIDA = "Formulario_Salida"

# --- Agente 2 -------------------------------------------------------------
URL_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
MAX_REINTENTOS = 2          # seccion 6: maximo 2 reintentos, luego error_clasificacion
ESPERA_BASE_SEGUNDOS = 2.0  # backoff exponencial: 2 s, 4 s, ...
TIMEOUT_SEGUNDOS = 90       # tiempo maximo de espera por cada llamada al modelo
MODELO_POR_DEFECTO = "openai/gpt-4o-mini"


def _cargar_dotenv() -> None:
    """Lee un .env simple si existe. No sobreescribe variables ya definidas."""
    ruta = RAIZ / ".env"
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_dotenv()


def api_key_openrouter() -> str:
    """Devuelve la key o lanza un error claro. Jamas la imprime."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Falta OPENROUTER_API_KEY. Definala como variable de entorno o en un "
            "archivo .env en la raiz del proyecto (que ya esta en .gitignore). "
            "Nunca la escriba directamente en el codigo."
        )
    return key


def modelo_openrouter() -> str:
    """Modelo a usar en Track A; se cambia con OPENROUTER_MODEL sin tocar codigo."""
    return os.environ.get("OPENROUTER_MODEL", MODELO_POR_DEFECTO).strip()
