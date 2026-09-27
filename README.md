# Reto 6 — Pipeline Multiagente · Clínica Vitalis

Entrega del Reto 6 de la Certificación 6 (IA y AIOps para Arquitectura de Software).

El pipeline procesa historias clínicas en tres etapas: **anonimización → clasificación → escritura**.
Los datos personales del paciente nunca llegan al modelo de IA, y eso no depende del cuidado de
quien lo opera: lo impide el contrato de datos entre etapas.

`Guia_Reto6_Pipeline_Multiagente.pdf` explica paso a paso cómo se cumple cada entregable, y
`evidencias/Dossier_Evidencias_Reto6.pdf` reúne todas las evidencias. Ambos PDF se generan a partir
de los archivos del proyecto, así que siempre coinciden con el código y los resultados.

## Cómo funciona

```text
Historia clínica          ETAPA 1                 ETAPA 2                  ETAPA 3
(con nombre, cédula,  ─►  Agente 1          ─►    Agente 2           ─►    Agente 3
 dirección, teléfono)     Anonimizador            Clasificador             Generador de salida
                          reglas fijas, sin IA    único que usa IA         reglas fijas, sin IA
                          │                       recibe SOLO:             escribe el .xlsx y lo
                          │                       código + texto limpio    relee para buscar fugas
                          ▼
                     Mapa de auditoría
                     (código ↔ identidad, en data/internal/, nunca se entrega)
```

| Etapa | Tipo de trabajo | Por qué |
|---|---|---|
| 1. Anonimización | Automatización pura | La regla es siempre la misma: quitar los 4 identificadores. Se verifica al 100%. |
| 2. Clasificación | Agente con criterio | Hay que interpretar texto libre, datos incompletos y ponderar el riesgo. |
| 3. Escritura | Automatización pura | El mapeo de columnas es fijo; al final se escanea el archivo contra fugas. |

Entre cada etapa corre una **verificación anti-fuga** que detiene el registro si sobrevive
algún identificador, aunque sea con otra puntuación (`52 884 117` en lugar de `52.884.117`)
o como apellido suelto.

### Track A y Track B

El Agente 2 tiene dos modos. Ambos reciben exactamente lo mismo: `codigo_paciente` y
`texto_anonimizado`.

- **Track B** (por defecto, sin API key): usa las clasificaciones hechas turno por turno en el
  chat del curso, guardadas en `data/clasificaciones_track_b_*.json`.
- **Track A**: llama a un modelo real a través de OpenRouter. Requiere una API key
  (ver [Track A](#track-a-clasificación-con-openrouter)).

## Requisitos

- **Python 3.10 o superior.** No hace falta instalar ninguna dependencia.
- **Chrome, Chromium o Microsoft Edge**, solo para generar los PDF (dossier y guía).

> En Windows el comando suele ser `python` o `py` en lugar de `python3`.

El documento de arquitectura del curso (sección 11) propone `openpyxl`, `pandas`, `pydantic` y
`pytest`. Aquí se reemplazan por equivalentes de la librería estándar, porque en el equipo de
desarrollo no había `pip`. Los requisitos de fondo se mantienen:

| Propuesto | Usado aquí | Requisito que se mantiene |
|---|---|---|
| `openpyxl` + `pandas` | `core/xlsx_io.py` (`zipfile` + `xml.etree`) | Leer y escribir `.xlsx` respetando encabezados y orden |
| `pydantic` | `dataclasses` con validación en `__post_init__` | Campos explícitos, nunca un diccionario abierto |
| `httpx` / `requests` | `urllib.request` | Reintentos con espera creciente, sin registrar la API key |
| `pytest` | `unittest` | Las pruebas obligatorias de la sección 10.2 |

## Ejecución

Ejecute los comandos desde la raíz del proyecto y **en este orden**, porque cada paso usa
archivos que genera el anterior:

```bash
# 1. Pipeline sobre las 3 historias propias (genera los entregables 1 y 2)
python3 orquestador.py --fuente propias --track b

# 2. Pipeline sobre las 12 historias del dataset de clase
python3 orquestador.py --fuente dataset --track b

# 3. Completar las Historias de Prueba con la evidencia de las corridas (entregable 3)
#    y registrar que git ignora .env y data/internal/
python3 generar_evidencias.py

# 4. Pruebas automáticas (28). La salida se guarda como evidencia para el dossier
python3 -m unittest discover -s tests 2> evidencias/salida_pruebas.txt

# 5. Contrastar la corrida del dataset contra el oráculo de referencia
#    (guarda el resultado en evidencias/salida_comparacion_oraculo.txt)
python3 comparar_con_oraculo.py

# 6. Documentos PDF: dossier de evidencias y guía de cumplimiento
python3 generar_dossier_evidencias.py
python3 generar_guia.py
```

Estos seis pasos reconstruyen la entrega completa desde cero. Para ver el detalle de cada
prueba en pantalla, use `python3 -m unittest discover -s tests -v`.

### Track A (clasificación con OpenRouter)

Necesita una API key propia. **No use la del material de clase:** el PDF
`Dia4/paso a paso n8n rack.pdf` trae una key del instructor en texto plano y debe
considerarse comprometida.

```bash
echo "OPENROUTER_API_KEY=su_clave_aqui" > .env
echo "OPENROUTER_MODEL=openai/gpt-4o-mini" >> .env   # opcional; este es el valor por defecto
python3 orquestador.py --fuente propias --track a
```

El archivo `.env` está en `.gitignore`. La key se lee de las variables de entorno y no aparece en
ningún archivo del repositorio (lo verifica `TestSeguridadCredenciales`).

## Estructura del proyecto

```text
.
├── orquestador.py                   punto de entrada: corre las 3 etapas en orden
├── config.py                        rutas, nombres de hojas y configuración de OpenRouter
├── generar_evidencias.py            completa las Historias de Prueba (entregable 3)
├── comparar_con_oraculo.py          compara la corrida con el formulario de referencia
├── generar_dossier_evidencias.py    arma el PDF de evidencias
├── generar_guia.py                  arma la guía de cumplimiento en PDF
├── Guia_Reto6_Pipeline_Multiagente.pdf  guía de cumplimiento paso a paso
├── agents/
│   ├── agente1_anonimizador.py      etapa 1: quita los identificadores (sin IA)
│   ├── agente2_clasificador.py      etapa 2: clasifica (único que usa IA)
│   └── agente3_generador_salida.py  etapa 3: escribe el .xlsx y hace el escaneo final
├── core/
│   ├── contratos.py                 formato de los datos entre etapas y nombres de columnas
│   ├── reglas_anonimizacion.py      cómo se detecta cada identificador y sus variantes
│   ├── verificacion_antifuga.py     búsqueda de identificadores que hayan sobrevivido
│   ├── auditoria.py                 único módulo que escribe el mapa código ↔ identidad
│   ├── cliente_openrouter.py        llamadas a OpenRouter con reintentos (Track A)
│   └── xlsx_io.py                   lectura y escritura de Excel sin dependencias
├── data/
│   ├── historias_propias.py         las 3 historias inventadas para el reto
│   ├── clasificaciones_track_b_*.json  clasificaciones del Agente 2 en Track B
│   ├── input/                       archivos entregados en clase (solo lectura)
│   ├── internal/                    mapa código ↔ identidad (NUNCA se entrega)
│   └── output/                      archivos .xlsx generados
├── evidencias/                      reflexión, resúmenes, salidas de pruebas y dossier PDF
└── tests/test_pipeline.py           28 pruebas automáticas
```

## Entregables del reto

| # | Entregable | Archivo |
|---|---|---|
| 1 | 3 historias propias con los 4 identificadores | `data/output/Historias_Propias_Reto.xlsx` |
| 2 | Pipeline corrido sobre esas 3 historias | `data/output/Formulario_Salida_Historias_Propias.xlsx` |
| 3 | Historias de prueba completadas: 19 casos (TC-01 a TC-19), 14 de la plantilla y 5 sobre las historias propias | `data/output/Historias_de_Prueba_COMPLETADO.xlsx` |
| 4 | Reflexión escrita (máximo 150 palabras) | `evidencias/reflexion_escrita.md` |

Material de apoyo:

- `data/output/Formulario_Salida_Dataset_Original.xlsx`: corrida sobre las 12 historias de clase.
- `evidencias/comparacion_con_oraculo.md`: contraste de esa corrida con el formulario de
  referencia y justificación de cada diferencia.
- `evidencias/Dossier_Evidencias_Reto6.pdf`: todas las evidencias en un solo documento.
- `evidencias/aislamiento_secretos_git.txt`: git ignora `.env` y `data/internal/` (TC-13).
- `Guia_Reto6_Pipeline_Multiagente.pdf`: guía de cumplimiento paso a paso.

**No suba `data/internal/`** a la plataforma de entrega: contiene la identidad real de cada paciente.

## Garantías de seguridad

- **El modelo solo ve dos campos.** El paquete hacia el Agente 2 contiene exactamente
  `codigo_paciente` y `texto_anonimizado`. Cualquier otra clave lanza `ViolacionDeContrato`
  antes de salir a la red.
- **Anti-fuga en dos puntos.** Tras la etapa 1 se revisa cada texto anonimizado, y tras la
  etapa 3 se relee el `.xlsx` desde disco y se escanea contra los identificadores originales.
- **El mapa de auditoría está aislado.** Vive solo en `data/internal/`, está en `.gitignore`,
  y ni el Agente 2 ni el Agente 3 lo importan (una prueba lo comprueba analizando el código).
- **Ninguna historia se pierde en silencio.** Si un registro falla en cualquier etapa, aparece
  en la salida como "no procesada" junto con el motivo.
- **Sin diagnósticos inventados.** Si la evidencia no alcanza, el Agente 2 debe responder
  "indeterminado" con confianza "baja", y el contrato rechaza cualquier otra combinación.
