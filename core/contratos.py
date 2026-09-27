"""Contratos de datos entre agentes (seccion 4 del documento de arquitectura).

El documento de arquitectura pide `pydantic`. Como en este equipo no hay `pip`,
se usan `dataclasses` de la libreria estandar con validacion explicita en
`__post_init__`. El requisito de fondo se mantiene intacto: campos explicitos,
nunca un diccionario abierto, y validacion que rechaza cualquier campo fuera
del esquema en tiempo de ejecucion.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, fields

# --- Columnas de la hoja de entrada (Historias_Clinicas_Entrada) -----------
# Se nombran una sola vez aqui para que ningun modulo repita el texto literal
# de un encabezado (un acento de menos romperia la busqueda sin avisar).
COLUMNA_ID_REGISTRO = "ID_Registro"
COLUMNA_NOMBRE = "Nombre completo"
COLUMNA_CEDULA = "Cédula"
COLUMNA_DIRECCION = "Dirección"
COLUMNA_TELEFONO = "Teléfono"
COLUMNA_NOTA_CLINICA = "Nota clínica (texto libre)"

# Las cuatro columnas que jamas pueden cruzar de la etapa 1 a la etapa 2.
COLUMNAS_IDENTIFICADORAS = (COLUMNA_NOMBRE, COLUMNA_CEDULA, COLUMNA_DIRECCION, COLUMNA_TELEFONO)
# Identificadores numericos: se comparan por su secuencia de digitos.
COLUMNAS_NUMERICAS = (COLUMNA_CEDULA, COLUMNA_TELEFONO)

# --- Valores permitidos en la salida del Agente 2 ---------------------------
NIVELES_RIESGO = ("bajo", "medio", "alto")
NIVELES_CONFIANZA = ("alta", "media", "baja")
VALORES_SI_NO_REGISTRADO = ("Sí", "No", "No registrado")
DIAGNOSTICO_INDETERMINADO = "indeterminado"

# Las unicas dos claves que el Agente 2 (el LLM) tiene permitido recibir.
CLAVES_PAYLOAD_AGENTE2 = frozenset({"codigo_paciente", "texto_anonimizado"})
PREFIJO_CODIGO_PACIENTE = "PAC-"

# Encabezados exactos y en orden del archivo de referencia (seccion 4.3).
ENCABEZADOS_SALIDA = (
    "código_paciente",
    "enfermedad_probable",
    "nivel_riesgo",
    "comportamiento_observado",
    "confianza",
    "antecedentes",
    "fuma",
    "consumo_sustancias",
)


class ViolacionDeContrato(ValueError):
    """Se lanza cuando un payload no respeta el esquema acordado."""


@dataclass(frozen=True)
class PaqueteAnonimizado:
    """Contrato 4.1 — salida Agente 1, entrada Agente 2.

    Es el contrato mas critico del sistema: exactamente estas dos claves,
    ninguna otra. La exclusion de identificadores es estructural, no una
    convencion de "no incluirlos".
    """

    codigo_paciente: str
    texto_anonimizado: str

    def __post_init__(self) -> None:
        if not self.codigo_paciente.startswith(PREFIJO_CODIGO_PACIENTE):
            raise ViolacionDeContrato(
                f"codigo_paciente debe tener formato PAC-NNN, recibido: {self.codigo_paciente!r}"
            )
        if not self.texto_anonimizado.strip():
            raise ViolacionDeContrato("texto_anonimizado no puede estar vacio")

    def como_payload(self) -> dict[str, str]:
        """El diccionario exacto que se serializa hacia el LLM."""
        return {
            "codigo_paciente": self.codigo_paciente,
            "texto_anonimizado": self.texto_anonimizado,
        }


def validar_payload_agente2(payload: dict) -> None:
    """Gate del orquestador: rechaza cualquier clave fuera del contrato 4.1.

    Se ejecuta sobre el diccionario que efectivamente se va a serializar hacia
    la red, no sobre el objeto en memoria: es ahi donde una fuga seria real.
    """
    recibidas = set(payload)
    if recibidas != CLAVES_PAYLOAD_AGENTE2:
        sobrantes = recibidas - CLAVES_PAYLOAD_AGENTE2
        faltantes = CLAVES_PAYLOAD_AGENTE2 - recibidas
        detalle = []
        if sobrantes:
            detalle.append(f"claves no permitidas: {sorted(sobrantes)}")
        if faltantes:
            detalle.append(f"claves faltantes: {sorted(faltantes)}")
        raise ViolacionDeContrato(
            "El payload hacia el Agente 2 viola el contrato 4.1 — " + "; ".join(detalle)
        )


@dataclass(frozen=True)
class RegistroClasificado:
    """Contrato 4.2 — salida Agente 2, entrada Agente 3."""

    codigo_paciente: str
    enfermedad_probable: str
    nivel_riesgo: str
    comportamiento_observado: str
    confianza: str
    antecedentes: str
    fuma: str
    consumo_sustancias: str

    def __post_init__(self) -> None:
        if self.nivel_riesgo not in NIVELES_RIESGO:
            raise ViolacionDeContrato(
                f"nivel_riesgo invalido: {self.nivel_riesgo!r} (esperado: {NIVELES_RIESGO})"
            )
        if self.confianza not in NIVELES_CONFIANZA:
            raise ViolacionDeContrato(
                f"confianza invalida: {self.confianza!r} (esperado: {NIVELES_CONFIANZA})"
            )
        for campo in ("fuma", "consumo_sustancias"):
            valor = getattr(self, campo)
            if valor not in VALORES_SI_NO_REGISTRADO:
                raise ViolacionDeContrato(
                    f"{campo} invalido: {valor!r} (esperado: {VALORES_SI_NO_REGISTRADO})"
                )
        # Regla de negocio explicita, no un fallback silencioso (seccion 4.2).
        if self.es_indeterminado and self.confianza != "baja":
            raise ViolacionDeContrato(
                f"{self.codigo_paciente}: enfermedad_probable='indeterminado' exige "
                f"confianza='baja', pero llego confianza={self.confianza!r}"
            )

    @property
    def es_indeterminado(self) -> bool:
        """True si el agente declaro que la evidencia no alcanza para un diagnostico."""
        return self.enfermedad_probable.strip().lower() == DIAGNOSTICO_INDETERMINADO

    def como_fila(self) -> list[str]:
        """Fila en el orden exacto de ENCABEZADOS_SALIDA."""
        return [
            self.codigo_paciente,
            self.enfermedad_probable,
            self.nivel_riesgo,
            self.comportamiento_observado,
            self.confianza,
            self.antecedentes,
            self.fuma,
            self.consumo_sustancias,
        ]

    @classmethod
    def desde_dict(cls, codigo: str, datos: dict) -> "RegistroClasificado":
        """Construye el registro desde la respuesta JSON del modelo."""
        esperados = {f.name for f in fields(cls)} - {"codigo_paciente"}
        faltantes = esperados - set(datos)
        if faltantes:
            raise ViolacionDeContrato(
                f"{codigo}: la respuesta del modelo no trae los campos {sorted(faltantes)}"
            )
        return cls(codigo_paciente=codigo, **{k: str(datos[k]).strip() for k in esperados})


@dataclass(frozen=True)
class RegistroFallido:
    """Un registro que no pudo completar el pipeline.

    Regla 5 de la especificacion: si una historia falla en cualquier etapa debe
    quedar registrada como "no procesada", nunca omitida en silencio.
    """

    codigo_paciente: str
    etapa: str
    motivo: str

    def como_fila(self) -> list[str]:
        """Fila visible en la salida para que el fallo no pase desapercibido."""
        return [
            self.codigo_paciente,
            "no procesada",
            "bajo",
            f"Fallo en {self.etapa}: {self.motivo}",
            "baja",
            "no disponible",
            "No registrado",
            "No registrado",
        ]
