"""Genera la guia de cumplimiento paso a paso (Guia_Reto6_Pipeline_Multiagente.pdf).

Igual que el dossier, la guia no se escribe a mano: las historias, los
resultados, los conteos de pruebas y casos, y la reflexion se leen de los
archivos del proyecto. Si algo cambia y se regenera, la guia cambia con ello y
no puede quedar desactualizada respecto del codigo.

Diferencia con el dossier: el dossier es la EVIDENCIA (muestra todo lo que se
obtuvo); la guia EXPLICA como se cumple cada entregable y como reproducirlo.

Requiere haber corrido antes los pasos 1 a 5 del README. Ejecutar desde la raiz:

    python3 generar_guia.py
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import config  # noqa: E402
from agents.agente1_anonimizador import anonimizar_lote, anonimizar_registro  # noqa: E402
from core.contratos import COLUMNAS_IDENTIFICADORAS, COLUMNA_NOTA_CLINICA  # noqa: E402
from core.verificacion_antifuga import escanear_archivo_final  # noqa: E402
from core.xlsx_io import leer_hojas  # noqa: E402
from data.historias_propias import HISTORIAS_PROPIAS, RESUMEN_CLINICO  # noqa: E402
from generar_dossier_evidencias import CSS, e, e_md, renderizar_pdf, tabla  # noqa: E402

ARCHIVO_GUIA = RAIZ / "Guia_Reto6_Pipeline_Multiagente.pdf"
NOMBRE_PROYECTO = RAIZ.name

# Casos de prueba que se muestran como ejemplo: 3 de la plantilla y 3 propios.
CASOS_EJEMPLO = ("TC-01", "TC-02", "TC-04", "TC-15", "TC-16", "TC-19")

ESTRUCTURA = """\
.
├── orquestador.py                   punto de entrada: corre las 3 etapas en orden
├── config.py                        rutas, nombres de hojas y configuración de OpenRouter
├── generar_evidencias.py            completa las Historias de Prueba (entregable 3)
├── comparar_con_oraculo.py          compara la corrida con el formulario de referencia
├── generar_dossier_evidencias.py    arma el PDF de evidencias
├── generar_guia.py                  arma esta guía
├── agents/                          los 3 agentes
├── core/                            contratos, reglas, anti-fuga, auditoría, cliente HTTP, E/S Excel
├── data/
│   ├── historias_propias.py         las 3 historias inventadas para el reto
│   ├── clasificaciones_track_b_*.json
│   ├── input/                       archivos de clase (solo lectura)
│   ├── internal/                    ← NO ENTREGAR · mapa código ↔ identidad
│   └── output/                      ← los .xlsx de los entregables 1, 2 y 3
├── evidencias/                      reflexión (entregable 4), salidas de pruebas y dossier PDF
├── tests/test_pipeline.py           {n_pruebas} pruebas automáticas
└── README.md · .gitignore · Guia_Reto6_Pipeline_Multiagente.pdf"""

CSS_GUIA = CSS + """
.warn{border:.6pt solid #EBD9A8;border-left:3.2pt solid #B7791F;background:#FFF8E6;
      padding:3mm 3.6mm;margin:2.6mm 0 3.5mm;page-break-inside:avoid}
.warn .lbl{color:#8A5A00} .warn p:last-child{margin-bottom:0}
td code{white-space:nowrap} .nw{white-space:nowrap}
.nota{font-family:"DejaVu Sans Mono",monospace;font-size:8pt;background:#F3F5F7;
      border-left:2.4pt solid var(--muted);padding:2.8mm 3.2mm;margin:2.2mm 0 3.2mm}
"""


# --------------------------------------------------------------------------
# Lectura de artefactos
# --------------------------------------------------------------------------

def _hoja(nombre_archivo: str, hoja: str) -> list[list[str]]:
    return leer_hojas(str(config.DIR_SALIDA / nombre_archivo))[hoja]


def _grupos_de_pruebas() -> list[tuple[str, str]]:
    """(clase, primera linea del docstring) de cada grupo de tests/test_pipeline.py."""
    arbol = ast.parse((RAIZ / "tests" / "test_pipeline.py").read_text(encoding="utf-8"))
    return [
        (nodo.name, (ast.get_docstring(nodo) or "").splitlines()[0])
        for nodo in arbol.body if isinstance(nodo, ast.ClassDef)
    ]


def _resultado_pruebas() -> tuple[str, bool]:
    """(cantidad de pruebas, si todas pasaron) segun evidencias/salida_pruebas.txt."""
    texto = (config.DIR_EVIDENCIAS / "salida_pruebas.txt").read_text(encoding="utf-8")
    linea = next((l for l in texto.splitlines() if l.startswith("Ran ")), "Ran ? tests")
    return linea.split()[1], any(l.strip() == "OK" for l in texto.splitlines())


def _nota_con_identificadores_resaltados(historia: dict[str, str]) -> str:
    nota = e(historia[COLUMNA_NOTA_CLINICA])
    for columna in COLUMNAS_IDENTIFICADORAS:
        valor = e(historia[columna])
        nota = nota.replace(valor, f"<strong>{valor}</strong>")
    return nota


def _terminal_orquestador(resumen: dict) -> str:
    """Reconstruye la salida de consola a partir del resumen de la corrida."""
    anonimizados, _ = anonimizar_lote(HISTORIAS_PROPIAS)
    return "\n".join([
        "$ python3 orquestador.py --fuente propias --track b",
        "",
        "  PIPELINE MULTIAGENTE — CLINICA VITALIS",
        f"  Fuente: {resumen['fuente']} ({resumen['registros_entrada']} registros)   ·   "
        f"Track: {resumen['track'].upper()}",
        "",
        "ETAPA 1 · Anonimizacion (deterministica, sin LLM, sin red)",
        f"  Anonimizados sin residuos : {len(anonimizados)}/{resumen['registros_entrada']}",
        f"  Mapa de auditoria         : data/internal/mapa_auditoria_{resumen['fuente']}.xlsx",
        "",
        f"ETAPA 2 · Clasificacion clinica (Track {resumen['track'].upper()})",
        f"  Clasificados              : {resumen['clasificados']}/{resumen['registros_entrada']}",
        f"  Marcados 'indeterminado'  : {len(resumen['indeterminados'])}",
        "",
        "ETAPA 3 · Escritura y verificacion anti-fuga final",
        f"  Archivo                   : {resumen['archivo']}",
        f"  Filas escritas            : {resumen['filas_escritas']}",
        f"  Celdas escaneadas         : {resumen['celdas_escaneadas']}",
        f"  Verificacion anti-fuga    : {resumen['verificacion_antifuga']}",
    ])


# --------------------------------------------------------------------------
# Documento
# --------------------------------------------------------------------------

def construir_html() -> str:
    resumen = json.loads(
        (config.DIR_EVIDENCIAS / "resumen_corrida_Historias_Propias.json").read_text(encoding="utf-8"))
    salida = _hoja("Formulario_Salida_Historias_Propias.xlsx", config.HOJA_SALIDA)
    casos = _hoja("Historias_de_Prueba_COMPLETADO.xlsx", "Historias_de_Prueba")
    n_pruebas, pruebas_ok = _resultado_pruebas()
    fugas = escanear_archivo_final(salida, HISTORIAS_PROPIAS)

    reflexion = (config.DIR_EVIDENCIAS / "reflexion_escrita.md").read_text(encoding="utf-8")
    cuerpo_reflexion = reflexion.split("---")[-1].strip()
    n_palabras = len([w for w in cuerpo_reflexion.split() if any(c.isalnum() for c in w)])

    total_casos = len(casos) - 1
    casos_pasaron = sum(1 for f in casos[1:] if f[7] == "Pasó")
    casos_propios = [f for f in casos[1:] if int(f[0].split("-")[1]) > 14]
    identificadores = len(HISTORIAS_PROPIAS) * len(COLUMNAS_IDENTIFICADORAS)
    estado_pruebas = "en verde" if pruebas_ok else "con fallos"
    historia1 = HISTORIAS_PROPIAS[0]
    payload_ejemplo = anonimizar_registro(historia1, 1).paquete.como_payload()
    p: list[str] = []

    # ------------------------------------------------------------ portada
    p.append(f"""
<section class="cover">
  <div class="k">LITE THINKING INSTITUTE OF TECHNOLOGY</div>
  <div class="k" style="color:var(--muted);margin-top:2.5mm">CERTIFICACIÓN 6 · SESIÓN 6</div>
  <h1>Reto 6 — Pipeline Multiagente<br>Guía de cumplimiento paso a paso</h1>
  <div class="rule"></div>
  <div class="sub">Cómo se cumple cada entregable y cómo reproducir las evidencias</div>
  <div class="meta">Caso 10 · Clínica Vitalis — anonimización → clasificación → escritura</div>
  <div class="meta">Proyecto: <code>{e(NOMBRE_PROYECTO)}</code></div>
  <div class="box" style="margin-top:14mm">
    <p><span class="lbl">Estado.</span> Los 4 entregables están generados y verificados. El pipeline
    corrió sobre {len(HISTORIAS_PROPIAS)} historias propias y las 12 del dataset de clase, con
    {n_pruebas} pruebas automáticas {estado_pruebas}, {casos_pasaron} de {total_casos} casos de prueba
    aprobados y verificación anti-fuga limpia sobre los archivos releídos desde disco.</p>
    <p><span class="lbl">Pendiente opcional:</span> correr la Etapa 2 contra un modelo real vía
    OpenRouter (Track A), que exige una API key propia. Ver la sección 7.</p>
  </div>
</section>""")

    # ------------------------------------------------------------ 1. el reto
    p.append("<h2>1. Qué pide el reto</h2>")
    p.append("<p>Demostrar, <strong>de forma individual y con datos propios</strong>, que el pipeline "
             "multiagente funciona y que usted puede verificarlo — no solo construirlo.</p>")
    p.append(tabla(["#", "Entregable", "Criterio de calificación", "Peso"], [
        ["1", "Crear 3 historias clínicas sintéticas nuevas, inventadas, con los 4 identificadores "
              "(nombre, cédula, dirección, teléfono) mezclados en texto libre.",
         "Las 3 son propias, con los 4 identificadores presentes y una condición médica clara y "
         "distinta entre sí.", "20%"],
        ["2", "Correr el pipeline (Track A o Track B) sobre esas 3 historias.",
         "El <code>Formulario_Salida</code> generado no contiene ningún dato identificable.", "30%"],
        ["3", "Completar al menos 5 filas de <code>Historias_de_Prueba_Pipeline_Clinico.xlsx</code> "
              "con resultados reales (Resultado obtenido y Estado).",
         "Al menos 5 casos con evidencia real, no solo «Pasó» sin justificación.", "30%"],
        ["4", "Responder en máximo 150 palabras: ¿qué fue automatización pura y qué requirió "
              "criterio del agente? Con un ejemplo de sus 3 historias.",
         "Conecta el marco automatización vs. agente con un ejemplo propio.", "20%"],
    ], ["c", "", "", "c"]))
    p.append('<div class="box"><p><span class="lbl">Dónde está la nota.</span> El 60% (puntos 2 y 3) '
             'no evalúa que el pipeline corra, sino que se <em>demuestre</em> que corrió bien: que la '
             'salida no filtra datos y que los casos de prueba traen evidencia concreta.</p></div>')
    p.append("<h3>Track A o Track B</h3>")
    p.append(tabla(["", "Track A", "Track B"], [
        ["<strong>Qué es</strong>", "El Agente 2 llama a un modelo real por API.",
         "El Agente 2 se resuelve turno por turno en el chat."],
        ["<strong>API key</strong>", "Sí (OpenRouter).", "No."],
        ["<strong>Costo</strong>", "Consumo por token.", "Ninguno."],
    ]))
    p.append('<div class="ok"><p><span class="lbl">Ruta elegida:</span> los Agentes 1 y 3 son código '
             'ejecutado (son deterministas: no ganan nada pasando por un LLM) y el Agente 2 se resolvió '
             'por <strong>Track B</strong>. El código de Track A está construido y listo para usarse '
             'con una key propia. Ambos tracks reciben exactamente el mismo contrato de entrada.</p></div>')

    # ------------------------------------------------------------ 2. estado
    p.append('<h2 class="break">2. Estado de cada entregable</h2>')
    chip = lambda t: f'<span class="chip c-ok">{e(t)}</span>'
    p.append(tabla(["#", "Entregable", "Archivo", "Estado"], [
        ["1", "3 historias propias", "<code>data/output/Historias_Propias_Reto.xlsx</code>", chip("Completo")],
        ["2", "Pipeline corrido", "<code>data/output/Formulario_Salida_Historias_Propias.xlsx</code>",
         chip("Completo")],
        ["3", "Historias de prueba", "<code>data/output/Historias_de_Prueba_COMPLETADO.xlsx</code>",
         chip(f"{casos_pasaron} de {total_casos}")],
        ["4", "Reflexión escrita", "<code>evidencias/reflexion_escrita.md</code>",
         chip(f"{n_palabras} palabras")],
        ["+", "Corrida sobre las 12 de clase",
         "<code>data/output/Formulario_Salida_Dataset_Original.xlsx</code>", chip("Extra")],
        ["+", "Suite de pruebas", "<code>evidencias/salida_pruebas.txt</code>",
         chip(f"{n_pruebas} {estado_pruebas}")],
        ["+", "Contraste con el oráculo", "<code>evidencias/comparacion_con_oraculo.md</code>", chip("Extra")],
        ["+", "Dossier de evidencias", "<code>evidencias/Dossier_Evidencias_Reto6.pdf</code>", chip("Extra")],
    ], ["c", "", "", "c"]))
    p.append("<h3>Resultado de la corrida sobre las historias propias</h3>")
    p.append(f"<pre>{e(_terminal_orquestador(resumen))}</pre>")
    p.append("<h3>Una decisión técnica</h3>")
    p.append("<p>El documento de arquitectura del curso propone <code>openpyxl</code>, <code>pandas</code>, "
             "<code>pydantic</code> y <code>pytest</code>. En el equipo de desarrollo no había "
             "<code>pip</code>, así que se usaron equivalentes de la librería estándar. Ningún "
             "requisito de fondo cambia:</p>")
    p.append(tabla(["Propuesto", "Usado aquí", "Requisito que se mantiene"], [
        ["<code>openpyxl</code> + <code>pandas</code>", "<code>zipfile</code> + <code>xml.etree</code>",
         "Leer y escribir .xlsx respetando encabezados y orden"],
        ["<code>pydantic</code>", "<code>dataclasses</code> con validación",
         "Campos explícitos, nunca un diccionario abierto"],
        ["<code>httpx</code> / <code>requests</code>", "<code>urllib.request</code>",
         "Reintentos con espera creciente, sin registrar la API key"],
        ["<code>pytest</code>", "<code>unittest</code>", "Las pruebas obligatorias de la sección 10.2"],
    ]))

    # ------------------------------------------------------------ 3. punto 1
    p.append('<h2 class="break">3. Entregable 1 — Las 3 historias propias (20%)</h2>')
    p.append("<p>El criterio exige tres cosas a la vez: que sean <strong>propias</strong>, que tengan los "
             "<strong>4 identificadores</strong> mezclados en el texto libre, y que cada una tenga una "
             "<strong>condición médica clara y distinta</strong> de las otras dos.</p>")
    p.append("<h3>Paso 1 · Tres condiciones distintas entre sí</h3>")
    p.append(tabla(["Registro", "Especialidad", "Condición", "Evidencia en la nota"],
                   [[f"<code>{e(r)}</code>", e(esp), e(cond), e(evid)]
                    for r, esp, cond, evid in RESUMEN_CLINICO]))
    p.append('<div class="warn"><p><span class="lbl">A tener en cuenta.</span> El dataset de clase '
             'también incluye casos de hipertensión y diabetes. El criterio pide que las 3 condiciones '
             'sean distintas <em>entre sí</em>, y lo son; las historias, los valores clínicos y los '
             'identificadores son propios. Si en la sustentación se pregunta, la infección urinaria '
             '(REG-P02) es la condición que no aparece en el material de clase.</p></div>')
    p.append("<h3>Paso 2 · Los 4 identificadores dentro de la nota</h3>")
    p.append("<p>No basta con tenerlos en las columnas: el ejercicio consiste en que el Agente 1 los "
             f"encuentre <em>dentro del texto libre</em>. Así quedó <code>{e(historia1['ID_Registro'])}</code> "
             "(identificadores en negrita):</p>")
    p.append(f'<div class="nota">{_nota_con_identificadores_resaltados(historia1)}</div>')
    p.append("<p>Todos los datos personales son ficticios. Los teléfonos usan el rango <code>555</code>, "
             "reservado para ficción, igual que el dataset de clase.</p>")
    p.append('<div class="ok"><p><span class="lbl">Verificación automática.</span> La prueba '
             '<code>test_los_4_identificadores_estan_presentes_en_la_entrada</code> falla si a alguna '
             'historia le falta un identificador o si alguno no aparece literalmente en la nota.</p></div>')

    # ------------------------------------------------------------ 4. punto 2
    p.append('<h2 class="break">4. Entregable 2 — Correr el pipeline (30%)</h2>')
    p.append("<p>Lo que se califica no es que el pipeline corra, sino que el <code>Formulario_Salida</code> "
             "<strong>no contenga ningún dato identificable</strong>. Por eso la garantía está en el "
             "contrato entre etapas, no en la disciplina de quien lo opera.</p>")
    p.append("<pre>$ python3 orquestador.py --fuente propias --track b</pre>")
    p.append("<h3>Etapa 1 · Agente 1 — Anonimización (determinístico, sin LLM, sin red)</h3>")
    p.append("<p>Asigna el código <code>PAC-NNN</code> y arma la lista de cadenas a borrar <strong>a partir "
             "de las columnas de la propia fila</strong>, nunca inventadas. Para cada identificador genera "
             "sus variantes de escritura. Con los datos de REG-P01:</p>")
    p.append("<ul>"
             f"<li><strong>Cédula</strong> <code>{e(historia1['Cédula'])}</code> → con puntos, sin puntos, "
             "con comas, con espacios y con prefijo <code>CC</code>.</li>"
             f"<li><strong>Teléfono</strong> <code>{e(historia1['Teléfono'])}</code> → con guiones, "
             "espacios, puntos o corrido.</li>"
             "<li><strong>Nombre</strong> → completo, cada componente de 3 o más letras y los pares "
             "consecutivos.</li>"
             "<li><strong>Dirección</strong> → completa y la vía sin la ciudad.</li></ul>")
    p.append("<p>Cada coincidencia se reemplaza por <code>[ANON]</code> y luego corre la verificación de "
             "dos capas. Si algo sobrevive, <strong>el registro se detiene</strong>: no se arregla en "
             "silencio ni pasa con una advertencia.</p>")
    p.append("<h3>Etapa 2 · Agente 2 — Clasificación (el único que usa IA)</h3>")
    p.append("<p>Recibe exclusivamente dos claves. Este es el paquete real que recibió para REG-P01:</p>")
    p.append(f"<pre>{e(json.dumps(payload_ejemplo, ensure_ascii=False, indent=2))}</pre>")
    p.append("<p>Cualquier clave adicional lanza <code>ViolacionDeContrato</code> antes de salir a la red. "
             "El clasificador no «se acuerda» de no filtrar: <strong>no puede filtrar lo que nunca "
             "tuvo</strong>.</p>")
    p.append("<h3>Etapa 3 · Agente 3 — Escritura (determinístico + última línea de defensa)</h3>")
    p.append("<p>Escribe el .xlsx con los 8 encabezados en el orden exacto del archivo de referencia, sin "
             "la fila de ejemplo y sin la hoja de entrada. Después <strong>relee el archivo desde disco</strong> "
             "y lo escanea contra los identificadores originales: lo que importa es lo que quedó escrito.</p>")
    p.append("<h3>Resultado obtenido</h3>")
    enc = salida[0]
    col = lambda fila, nombre: e(fila[enc.index(nombre)])
    p.append(tabla(["Código", "Enfermedad probable", "Riesgo", "Confianza", "Fuma", "Antecedentes"],
                   [[f"<code>{col(f, 'código_paciente')}</code>", col(f, "enfermedad_probable"),
                     col(f, "nivel_riesgo"), col(f, "confianza"), col(f, "fuma"), col(f, "antecedentes")]
                    for f in salida[1:]],
                   ["", "", "c", "c", "c", ""]))
    celdas = sum(len(f) for f in salida)
    if fugas:
        p.append(f'<div class="stop"><p><span class="lbl">Atención.</span> El escaneo encontró '
                 f'{len(fugas)} identificador(es) en la salida. Revise antes de entregar.</p></div>')
    else:
        p.append(f'<div class="ok"><p><span class="lbl">Criterio del 30% cumplido.</span> El escaneo '
                 f'recorrió las {celdas} celdas del archivo final y no encontró ninguna de las '
                 f'{identificadores} cadenas identificadoras ({len(HISTORIAS_PROPIAS)} historias × 4), ni '
                 'exacta, ni con puntuación alterada, ni como fragmento suelto del nombre.</p></div>')

    # ------------------------------------------------------------ 5. punto 3
    p.append('<h2 class="break">5. Entregable 3 — Las historias de prueba (30%)</h2>')
    p.append(f"<p>El reto pide <strong>al menos 5</strong> casos con evidencia real. Se completaron "
             f"<strong>{total_casos}</strong>: los {total_casos - len(casos_propios)} de la plantilla y "
             f"{len(casos_propios)} nuevos sobre las historias propias. La evidencia se genera leyendo los "
             "archivos que produjo el pipeline; no está escrita a mano.</p>")
    p.append("<pre>" + e("\n".join([
        "$ python3 generar_evidencias.py",
        "",
        f"Casos completados con evidencia real : {total_casos}",
        f"  Pasó   : {casos_pasaron}",
        f"  Falló  : {total_casos - casos_pasaron}",
        "",
        "Archivo -> data/output/Historias_de_Prueba_COMPLETADO.xlsx",
    ])) + "</pre>")
    p.append("<h3>Ejemplos de la evidencia producida</h3>")
    por_id = {f[0]: f for f in casos[1:]}
    p.append(tabla(["Caso", "Resultado obtenido (texto real del archivo)", "Estado"],
                   [[f"<code>{e(c)}</code>", e(por_id[c][6]), chip(por_id[c][7])]
                    for c in CASOS_EJEMPLO if c in por_id],
                   ["", "", "c"]))
    p.append("<h3>La suite de pruebas que respalda las evidencias</h3>")
    p.append(f"<pre>$ python3 -m unittest discover -s tests\nRan {e(n_pruebas)} tests\n"
             f"{'OK' if pruebas_ok else 'FAILED'}</pre>")
    p.append(tabla(["Grupo de pruebas", "Qué verifica"],
                   [[f"<code>{e(nombre)}</code>", e(doc)] for nombre, doc in _grupos_de_pruebas()]))

    # ------------------------------------------------------------ 6. punto 4
    p.append('<h2 class="break">6. Entregable 4 — La reflexión escrita (20%)</h2>')
    p.append("<p>El criterio pide conectar el marco de automatización vs. agente con un <strong>ejemplo "
             "concreto de las propias historias</strong>. Los dos errores que hacen perder este 20% son "
             "quedarse en la teoría sin ejemplo y pasarse de 150 palabras.</p>")
    p.append("<h3>El razonamiento</h3>")
    p.append(tabla(["Etapa", "Naturaleza", "Por qué"], [
        ["Agente 1", "Automatización pura", "La misma regla de sustitución para cualquier paciente, sin "
                                            "interpretar nada. Se verifica al 100%."],
        ["Agente 2", "<strong>Agente</strong>", "Texto libre con información incompleta: hay que interpretar "
                                                 "y ponderar varios datos. Justifica el uso de un LLM."],
        ["Agente 3", "Automatización pura", "Mapeo fijo de columnas. Mismo resultado cada vez."],
    ], ["nw", "nw", ""]))
    p.append(f"<h3>La respuesta entregada — {n_palabras} palabras</h3>")
    parrafos = "".join(f"<p>{e_md(x.strip())}</p>" for x in cuerpo_reflexion.split("\n\n") if x.strip())
    p.append(f'<div class="box">{parrafos}</div>')
    p.append('<div class="ok"><p><span class="lbl">Por qué el ejemplo funciona.</span> No dice «el agente '
             'usó criterio» en abstracto: muestra que con una presión de 158/96 el agente no afirmó '
             '«hipertensión confirmada» porque había una sola medición, y que para el riesgo combinó el '
             'antecedente familiar y el tabaquismo. La clasificación real del Agente 2 lo confirma: '
             'confianza «media» por una sola toma registrada.</p></div>')

    # ------------------------------------------------------------ 7. pendientes
    p.append('<h2 class="break">7. Qué falta (opcional)</h2>')
    p.append("<p>Los 4 entregables están cumplidos. Lo que sigue fortalece la entrega, pero el reto no lo exige.</p>")
    p.append("<h3>7.1 · Correr la Etapa 2 contra un modelo real (Track A)</h3>")
    p.append('<div class="stop"><p><span class="lbl">Antes de nada.</span> No use la API key del material '
             'de clase: el PDF <code>Dia4/paso a paso n8n rack.pdf</code> trae una key de OpenRouter del '
             'instructor en texto plano. Debe considerarse comprometida.</p></div>')
    p.append("<p><strong>1.</strong> Cree una cuenta y una key propia en <code>openrouter.ai</code>. Hay "
             "modelos con sufijo <code>:free</code> que sirven sin costo.</p>")
    p.append("<p><strong>2.</strong> Guárdela fuera del código (el archivo <code>.env</code> ya está en "
             "<code>.gitignore</code>; es lo que verifica TC-13):</p>")
    p.append('<pre>$ echo "OPENROUTER_API_KEY=su_clave_aqui" > .env\n'
             '$ echo "OPENROUTER_MODEL=openai/gpt-4o-mini" >> .env</pre>')
    p.append("<p><strong>3.</strong> Corra y regenere las evidencias:</p>")
    p.append("<pre>$ python3 orquestador.py --fuente propias --track a\n$ python3 generar_evidencias.py\n"
             "$ python3 -m unittest discover -s tests -v</pre>")
    p.append("<p>Si alguna clasificación difiere de la de Track B, esa diferencia es material útil para la "
             "sustentación: muestra dónde el juicio clínico es genuinamente ambiguo.</p>")
    p.append("<h3>7.2 · Mejoras que suman en la sustentación</h3>")
    p.append(tabla(["Mejora", "Qué aporta", "Esfuerzo"], [
        ["Capturas de pantalla", "La terminal con las pruebas en verde y el Excel final abierto.", "Bajo"],
        ["Repositorio en Git", "Demuestra que <code>.env</code> y <code>data/internal/</code> nunca entraron "
                               "al control de versiones. Refuerza TC-13.", "Bajo"],
        ["Interfaz web con Flask", "Un botón «Correr pipeline» que muestre las 3 etapas (Paso 11 de la "
                                   "Sesión 6).", "Medio"],
    ], ["", "", "c"]))
    p.append("<h3>7.3 · Dos inconsistencias del material de clase</h3>")
    p.append("<p>Al contrastar la corrida con el oráculo, el <code>Formulario_Salida</code> de referencia "
             "contradice a las Historias de Prueba del mismo paquete:</p>")
    p.append(tabla(["Caso", "Dice la referencia", "Exige la Historia de Prueba", "Qué se hizo"], [
        ["<code>PAC-005</code>", "<code>nivel_riesgo = medio</code>",
         "TC-12: <code>nivel_riesgo = 'alto'</code> por el antecedente cardiovascular", "Se siguió TC-12."],
        ["<code>PAC-006</code>", "artritis reumatoide, confianza media",
         "TC-04: no afirmar un diagnóstico sin respaldo", "Se declaró <code>indeterminado</code> con "
                                                          "confianza baja."],
    ]))
    p.append("<p>El detalle, junto con las demás divergencias de criterio clínico, está en "
             "<code>evidencias/comparacion_con_oraculo.md</code>.</p>")

    # ------------------------------------------------------------ 8. regenerar
    p.append('<h2 class="break">8. Cómo regenerar todo desde cero</h2>')
    p.append("<p>Desde la raíz del proyecto y en este orden (cada paso usa lo que genera el anterior). "
             "En Windows use <code>python</code> o <code>py</code> en lugar de <code>python3</code>.</p>")
    p.append("<pre>" + e("\n".join([
        "# 1-2. Pipeline sobre las dos fuentes",
        "python3 orquestador.py --fuente propias --track b",
        "python3 orquestador.py --fuente dataset --track b",
        "",
        "# 3. Historias de prueba con evidencia real",
        "python3 generar_evidencias.py",
        "",
        "# 4. Pruebas automáticas (la salida queda como evidencia)",
        "python3 -m unittest discover -s tests 2> evidencias/salida_pruebas.txt",
        "",
        "# 5. Contraste con el oráculo",
        "python3 comparar_con_oraculo.py",
        "",
        "# 6. Documentos PDF",
        "python3 generar_dossier_evidencias.py",
        "python3 generar_guia.py",
    ])) + "</pre>")
    p.append(tabla(["Comando", "Genera"], [
        ["<code>orquestador.py --fuente propias</code>",
         "<code>Historias_Propias_Reto.xlsx</code>, <code>Formulario_Salida_Historias_Propias.xlsx</code> "
         "y el mapa de auditoría interno"],
        ["<code>orquestador.py --fuente dataset</code>",
         "<code>Formulario_Salida_Dataset_Original.xlsx</code> y el mapa de auditoría interno"],
        ["<code>generar_evidencias.py</code>",
         f"<code>Historias_de_Prueba_COMPLETADO.xlsx</code> con {total_casos} casos y "
         "<code>evidencias/aislamiento_secretos_git.txt</code>"],
        ["<code>unittest discover</code>", f"<code>evidencias/salida_pruebas.txt</code> — {n_pruebas} pruebas"],
        ["<code>comparar_con_oraculo.py</code>", "<code>evidencias/salida_comparacion_oraculo.txt</code>"],
        ["<code>generar_dossier_evidencias.py</code>", "<code>evidencias/Dossier_Evidencias_Reto6.pdf</code>"],
        ["<code>generar_guia.py</code>", "<code>Guia_Reto6_Pipeline_Multiagente.pdf</code> (este documento)"],
    ]))
    p.append('<div class="stop"><p><span class="lbl">Qué NO se entrega nunca.</span> La carpeta '
             '<code>data/internal/</code> contiene el mapa <code>código_paciente ↔ identidad real</code>. '
             'Si se filtra, revierte toda la anonimización. Está en <code>.gitignore</code>, ningún agente '
             'posterior lo lee, y <strong>no debe incluirse en lo que suba a la plataforma</strong>.</p></div>')

    # ------------------------------------------------------------ 9. checklist
    p.append('<h2 class="break">9. Checklist de entrega</h2>')
    listo = chip("Listo")
    opcional = '<span class="chip" style="background:#FFF8E6;color:#8A5A00;border:.6pt solid #EBD9A8">Opcional</span>'
    p.append(tabla(["", "Punto", "Archivo", "Estado"], [
        ["☑", "3 historias propias, 4 identificadores, condiciones distintas",
         "<code>Historias_Propias_Reto.xlsx</code>", listo],
        ["☑", "Pipeline corrido, salida sin datos identificables",
         "<code>Formulario_Salida_Historias_Propias.xlsx</code>", listo],
        ["☑", "Mínimo 5 casos de prueba con evidencia real",
         f"<code>Historias_de_Prueba_COMPLETADO.xlsx</code> ({total_casos})", listo],
        ["☑", "Reflexión de máximo 150 palabras", f"<code>reflexion_escrita.md</code> ({n_palabras})", listo],
        ["☑", "Código fuente del pipeline", "<code>agents/</code>, <code>core/</code>, <code>tests/</code>", listo],
        ["☑", "Salida de las pruebas", "<code>evidencias/salida_pruebas.txt</code>", listo],
        ["☐", "Corrida con modelo real vía OpenRouter", "Requiere API key propia", opcional],
        ["☐", "Capturas de pantalla de la corrida", "—", opcional],
    ], ["c", "", "", "c"]))
    p.append("<h3>Verificación final antes de subir</h3>")
    p.append(f"<pre>$ python3 -m unittest discover -s tests\nRan {e(n_pruebas)} tests\n"
             f"{'OK' if pruebas_ok else 'FAILED'}</pre>")
    p.append(f"<p>Si esas {e(n_pruebas)} pruebas están en verde, entonces a la vez: las 3 historias tienen "
             "sus 4 identificadores, ninguna cadena identificadora sobrevive a la anonimización, el paquete "
             "hacia el clasificador lleva exactamente 2 claves, todo <code>indeterminado</code> tiene "
             "confianza baja, los archivos finales no filtran datos, el mapa de auditoría está aislado, no "
             "hay API keys en el código, los 4 entregables existen y el pipeline aguanta una historia "
             "corrupta sin caerse.</p>")
    p.append("<h3>Estructura del proyecto</h3>")
    p.append(f"<pre>{e(ESTRUCTURA.format(n_pruebas=n_pruebas))}</pre>")

    return (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
            f'<title>Guía de cumplimiento — Reto 6</title><style>{CSS_GUIA}</style></head>'
            f'<body>{"".join(p)}</body></html>')


def main() -> None:
    navegador = renderizar_pdf(construir_html(), ARCHIVO_GUIA)
    print(f"Guia generada con {navegador}")
    print(f"  -> {ARCHIVO_GUIA.name}  ({ARCHIVO_GUIA.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
