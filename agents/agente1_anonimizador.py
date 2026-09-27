"""Agente 1 — Anonimizador (seccion 5 del documento de arquitectura).

Naturaleza: DETERMINISTICO. Sin LLM, sin red externa.

Esto no es preferencia de estilo: es el control de seguridad principal del
sistema. El unico paso que toca los 4 identificadores en crudo debe ser el mas
simple y el mas facil de probar exhaustivamente de todo el pipeline.

Segun el criterio de automatizacion vs. agente (seccion 3 del documento), esta
etapa es AUTOMATIZACION PURA: el camino es siempre el mismo, no hay ambiguedad
real en la entrada, y el costo de un error es alto. Por eso reglas explicitas,
no criterio de un modelo.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.contratos import COLUMNA_NOTA_CLINICA, PaqueteAnonimizado
from core.reglas_anonimizacion import (
    anonimizar_texto,
    construir_tokens,
    generar_codigo_paciente,
)
from core.verificacion_antifuga import FugaDetectada, exigir_sin_residuos

# (codigo_paciente, motivo) de un registro que no supero la etapa 1.
FalloAnonimizacion = tuple[str, str]


@dataclass(frozen=True)
class ResultadoAnonimizacion:
    """Lo que el Agente 1 entrega por cada registro.

    - paquete           : lo UNICO que viaja al Agente 2 (codigo + texto limpio).
    - registro_original : la fila con identificadores; solo la usan el mapa de
                          auditoria y las verificaciones anti-fuga, nunca el LLM.
    - tokens_aplicados  : las cadenas que se eliminaron, como rastro de auditoria.
    """

    paquete: PaqueteAnonimizado
    registro_original: dict[str, str]
    tokens_aplicados: list[str]


def anonimizar_registro(registro: dict[str, str], indice: int) -> ResultadoAnonimizacion:
    """Procesa una fila de Historias_Clinicas_Entrada.

    Lanza FugaDetectada si la verificacion de dos capas encuentra cualquier
    residuo. El registro NO avanza al Agente 2: no se arregla en silencio ni
    se deja pasar con una advertencia (seccion 5, paso 4).
    """
    codigo = generar_codigo_paciente(indice)
    nota = registro.get(COLUMNA_NOTA_CLINICA, "") or ""

    if not nota.strip():
        raise ValueError(f"{codigo}: la nota clinica esta vacia")

    tokens = construir_tokens(registro)
    texto_anonimizado = anonimizar_texto(nota, tokens)

    # Gate obligatorio antes de dejar avanzar el registro.
    exigir_sin_residuos(codigo, texto_anonimizado, registro)

    paquete = PaqueteAnonimizado(
        codigo_paciente=codigo,
        texto_anonimizado=texto_anonimizado,
    )
    return ResultadoAnonimizacion(paquete, registro, tokens)


def anonimizar_lote(
    registros: list[dict[str, str]],
) -> tuple[list[ResultadoAnonimizacion], list[FalloAnonimizacion]]:
    """Procesa todos los registros. Devuelve (exitosos, fallidos).

    Un registro que falla no detiene el lote — queda marcado y se continua con
    los demas (regla 5: nunca omitido en silencio, nunca silencioso el fallo).
    El codigo PAC-NNN depende de la posicion en el lote, no del resultado: asi
    un fallo no desplaza los codigos de los registros siguientes.
    """
    exitosos: list[ResultadoAnonimizacion] = []
    fallidos: list[FalloAnonimizacion] = []

    for indice, registro in enumerate(registros, start=1):
        codigo = generar_codigo_paciente(indice)
        try:
            exitosos.append(anonimizar_registro(registro, indice))
        except FugaDetectada as e:
            fallidos.append((codigo, f"requiere_revision_manual — {'; '.join(e.residuos)}"))
        except ValueError as e:
            fallidos.append((codigo, f"registro_invalido — {e}"))

    return exitosos, fallidos
