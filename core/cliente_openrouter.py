"""Cliente HTTP contra OpenRouter usando solo `urllib` de la libreria estandar.

El documento de arquitectura sugiere `httpx`/`requests`; se usa `urllib.request`
por la misma razon que el resto del pipeline evita dependencias externas (ver
cabecera de core/xlsx_io.py). El comportamiento requerido es identico:
reintentos con backoff, y nunca loguear la API key.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import config


class ErrorClasificacion(Exception):
    """El modelo no devolvio una respuesta utilizable tras agotar reintentos."""


def _extraer_json(contenido: str) -> dict:
    """Parsea la respuesta del modelo, tolerando que venga envuelta en ```json."""
    texto = (contenido or "").strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1] if "```" in texto[3:] else texto[3:]
        if texto.lstrip().lower().startswith("json"):
            texto = texto.lstrip()[4:]
    inicio, fin = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fin == -1:
        raise ValueError(f"la respuesta no contiene un objeto JSON: {contenido[:200]!r}")
    return json.loads(texto[inicio:fin + 1])


def clasificar(payload: dict[str, str], prompt_sistema: str) -> dict:
    """Envia el payload del contrato 4.1 y devuelve el JSON clasificado.

    `payload` ya viene validado por el orquestador: exactamente las claves
    codigo_paciente y texto_anonimizado, nada mas.
    """
    cuerpo = {
        "model": config.modelo_openrouter(),
        "messages": [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    datos = json.dumps(cuerpo).encode("utf-8")

    ultimo_error: Exception | None = None
    for intento in range(config.MAX_REINTENTOS + 1):
        try:
            peticion = urllib.request.Request(
                config.URL_OPENROUTER,
                data=datos,
                headers={
                    "Authorization": f"Bearer {config.api_key_openrouter()}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(peticion, timeout=config.TIMEOUT_SEGUNDOS) as respuesta:
                cruda = json.loads(respuesta.read().decode("utf-8"))
            return _extraer_json(cruda["choices"][0]["message"]["content"])

        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError) as e:
            ultimo_error = e
            # El mensaje de error nunca incluye la key ni el texto clinico.
            if intento < config.MAX_REINTENTOS:
                time.sleep(config.ESPERA_BASE_SEGUNDOS * (2 ** intento))

    raise ErrorClasificacion(
        f"{payload['codigo_paciente']}: fallaron {config.MAX_REINTENTOS + 1} intentos "
        f"({type(ultimo_error).__name__}). No se inventa una fila."
    )
