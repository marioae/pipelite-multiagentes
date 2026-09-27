"""Agente 2 — Clasificador clinico (seccion 6 del documento de arquitectura).

Naturaleza: el UNICO agente con razonamiento no deterministico, y el unico
punto del sistema autorizado a llamar a un LLM externo.

Segun el criterio de automatizacion vs. agente: esta etapa SI es un agente.
La entrada es texto libre no estructurado, con ambiguedad real (sintomas que
no siempre apuntan a un diagnostico claro, informacion faltante) y requiere
razonamiento clinico, no un mapeo fijo. Por eso justifica el costo, la latencia
y el no-determinismo de un LLM — y por eso mismo es al unico al que hay que
restringirle brutalmente lo que puede ver.

Dos backends, mismo contrato de entrada y de salida:

    "openrouter" (Track A) — llama al modelo via API.
    "track_b"    (Track B) — lee las clasificaciones producidas orquestando
                             el pipeline turno por turno en el chat, tal como
                             describe la Sesion 6. No requiere API key.

El backend NO cambia lo que el agente puede ver: en ambos casos recibe
exclusivamente el contrato 4.1.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.contratos import (
    PaqueteAnonimizado,
    RegistroClasificado,
    ViolacionDeContrato,
    validar_payload_agente2,
)

PROMPT_SISTEMA = """Eres un clasificador clinico dentro de un pipeline multiagente.

El texto que recibes YA ESTA ANONIMIZADO. Los datos identificables del paciente
(nombre, cedula, direccion, telefono) fueron sustituidos por el marcador [ANON]
antes de llegar a ti. Bajo ninguna circunstancia debes inferir, inventar ni
solicitar un nombre: tu unica referencia al paciente es codigo_paciente.

Devuelve EXCLUSIVAMENTE un objeto JSON con estas claves:

  enfermedad_probable      Texto corto. Si la evidencia es insuficiente, escribe
                           exactamente "indeterminado". NUNCA inventes un
                           diagnostico plausible para rellenar.
  nivel_riesgo             Uno de: bajo | medio | alto
  comportamiento_observado Resumen corto de la evidencia que sustenta tu
                           clasificacion. Si declaraste "indeterminado",
                           explica QUE evidencia falta — no dejes algo generico.
  confianza                Uno de: alta | media | baja. Es una declaracion sobre
                           tu propia certeza, no un valor decorativo. Si
                           enfermedad_probable es "indeterminado", confianza
                           DEBE ser "baja".
  antecedentes             Texto corto, o "ninguno registrado".
  fuma                     Uno de: Sí | No | No registrado
  consumo_sustancias       Uno de: Sí | No | No registrado

Criterio para fuma y consumo_sustancias: solo marca "Sí" cuando el texto lo
afirma de forma explicita. El consumo ocasional de alcohol de fin de semana no
cuenta como "Sí" en consumo_sustancias; el consumo frecuente si.
"""


def clasificar_via_openrouter(paquete: PaqueteAnonimizado) -> RegistroClasificado:
    """Track A — clasificacion real contra el modelo configurado."""
    from core.cliente_openrouter import clasificar  # import diferido: Track B no lo necesita

    payload = paquete.como_payload()
    validar_payload_agente2(payload)  # gate: exactamente 2 claves, nada mas
    datos = clasificar(payload, PROMPT_SISTEMA)
    return RegistroClasificado.desde_dict(paquete.codigo_paciente, datos)


def clasificar_via_track_b(paquete: PaqueteAnonimizado, ruta_respuestas: Path) -> RegistroClasificado:
    """Track B — lee la clasificacion producida turno por turno en el chat.

    El archivo de respuestas contiene, por codigo de paciente, exactamente los
    7 campos del contrato 4.2. El gate de contrato se aplica igual que en
    Track A: se valida el payload que el agente habria recibido.
    """
    payload = paquete.como_payload()
    validar_payload_agente2(payload)  # mismo gate, mismo contrato

    respuestas = json.loads(Path(ruta_respuestas).read_text(encoding="utf-8"))
    datos = respuestas.get(paquete.codigo_paciente)
    if datos is None:
        raise ViolacionDeContrato(
            f"{paquete.codigo_paciente}: no hay clasificacion registrada en {ruta_respuestas.name}"
        )
    return RegistroClasificado.desde_dict(paquete.codigo_paciente, datos)
