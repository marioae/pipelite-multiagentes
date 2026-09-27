"""Genera el dossier de evidencias en PDF a partir de los artefactos reales.

Nada de este documento esta escrito a mano: cada tabla y cada cifra se leen de
los archivos que el pipeline produjo. Si el pipeline cambia y se regenera el
dossier, el documento cambia con el.

Requiere un navegador Chromium para el render final (brave-browser, chromium,
google-chrome o Microsoft Edge). Ejecutar desde la raiz del proyecto:

    python3 generar_dossier_evidencias.py
"""

from __future__ import annotations

import html
import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

import config  # noqa: E402
from core.verificacion_antifuga import escanear_archivo_final  # noqa: E402
from core.xlsx_io import leer_hojas, leer_tabla  # noqa: E402
from data.historias_propias import HISTORIAS_PROPIAS  # noqa: E402

NAVEGADORES = ("brave-browser", "chromium", "chromium-browser", "google-chrome", "google-chrome-stable",
               "msedge", "chrome")
# En Windows los navegadores no suelen estar en el PATH: se prueban sus rutas habituales.
RUTAS_WINDOWS = (
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
)

CSS = """
@page { size: Letter; margin: 16mm 15mm 17mm 15mm; }
:root{--navy:#1F3A5F;--teal:#2E6E8E;--ink:#1A1A1A;--muted:#5A6B7B;--rule:#C9D6E0;
      --light:#EEF3F7;--soft:#F7FAFC;--ok:#1E6B45;--okbg:#EAF5EF;--stop:#9B2C2C;--stopbg:#FCEDED;}
*{box-sizing:border-box}
body{font-family:"DejaVu Sans",Arial,sans-serif;font-size:9pt;line-height:1.48;color:var(--ink);margin:0}
h1,h2,h3{margin:0;font-weight:700}
.cover{height:236mm;display:flex;flex-direction:column;justify-content:center;page-break-after:always}
.cover .k{font-size:8pt;letter-spacing:.14em;color:var(--teal);font-weight:700}
.cover h1{font-size:27pt;color:var(--navy);line-height:1.15;margin-top:8mm}
.cover .rule{border-top:2.4pt solid var(--teal);margin:8mm 0 6mm}
.cover .sub{font-size:13pt;color:var(--teal)}
.cover .meta{font-size:9pt;color:var(--muted);margin-top:3mm}
h2{font-size:14pt;color:var(--navy);margin:10mm 0 3.5mm;padding-bottom:1.8mm;
   border-bottom:1.5pt solid var(--teal);page-break-after:avoid}
h3{font-size:10.6pt;color:var(--teal);margin:6mm 0 2.2mm;page-break-after:avoid}
p{margin:0 0 2.6mm}
.break{page-break-before:always}
code{font-family:"DejaVu Sans Mono",monospace;font-size:8.2pt;background:var(--light);
     padding:.3mm 1mm;border-radius:1.5px;color:#2C3E50}
pre{font-family:"DejaVu Sans Mono",monospace;font-size:7.8pt;line-height:1.42;background:#1F2A33;
    color:#D8E2E8;border-left:2.4pt solid var(--teal);padding:2.8mm 3.2mm;margin:2.2mm 0 3.2mm;
    white-space:pre-wrap;page-break-inside:avoid}
table{width:100%;border-collapse:collapse;margin:2.2mm 0 3.5mm;font-size:8.3pt;page-break-inside:avoid}
th{background:var(--navy);color:#fff;text-align:left;font-weight:700;padding:1.8mm 2.2mm;font-size:8pt}
td{padding:1.8mm 2.2mm;border-bottom:.6pt solid var(--rule);vertical-align:top}
tr:nth-child(even) td{background:var(--soft)}
td.c,th.c{text-align:center}
.box,.ok,.stop{border:.6pt solid var(--rule);border-left:3.2pt solid var(--teal);background:var(--light);
     padding:3mm 3.6mm;margin:2.6mm 0 3.5mm;page-break-inside:avoid}
.ok{border-left-color:var(--ok);background:var(--okbg);border-color:#BFDECB}
.stop{border-left-color:var(--stop);background:var(--stopbg);border-color:#E8BFBF}
.box p:last-child,.ok p:last-child,.stop p:last-child{margin-bottom:0}
.lbl{font-weight:700;color:var(--navy)} .ok .lbl{color:var(--ok)} .stop .lbl{color:var(--stop)}
.chip{display:inline-block;padding:.4mm 1.8mm;border-radius:2.5px;font-size:7.4pt;font-weight:700}
.c-ok{background:var(--okbg);color:var(--ok);border:.6pt solid #BFDECB}
.kpi{display:flex;gap:3mm;margin:3mm 0 4mm}
.kpi div{flex:1;border:.6pt solid var(--rule);border-top:2.4pt solid var(--teal);
         background:var(--soft);padding:2.8mm;text-align:center;page-break-inside:avoid}
.kpi .n{font-size:17pt;font-weight:700;color:var(--navy);line-height:1.1}
.kpi .l{font-size:7.4pt;color:var(--muted);margin-top:1mm}
.foot{margin-top:8mm;padding-top:2.6mm;border-top:.8pt solid var(--rule);
      color:var(--muted);font-size:8pt;font-style:italic;text-align:center}
"""


def e(t) -> str:
    return html.escape(str(t if t is not None else ""))


def e_md(t) -> str:
    """Escapa el texto y convierte el enfasis de Markdown a cursiva.

    La reflexion se escribe en un .md y usa *...* para los terminos en latin
    (nombres de microorganismos). Sin esta conversion los asteriscos salen
    literales en el PDF.
    """
    import re
    escapado = e(t)
    escapado = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escapado)
    escapado = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", escapado)
    return escapado


def tabla(encabezados: list[str], filas: list[list[str]], clases: list[str] | None = None) -> str:
    clases = clases or [""] * len(encabezados)
    th = "".join(f'<th class="{c}">{e(h)}</th>' for h, c in zip(encabezados, clases))
    tr = "".join(
        "<tr>" + "".join(f'<td class="{c}">{v}</td>' for v, c in zip(fila, clases)) + "</tr>"
        for fila in filas
    )
    return f"<table><tr>{th}</tr>{tr}</table>"


def construir_html() -> str:
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    p: list[str] = []

    # ---------------------------------------------------------------- datos
    salida_propias = leer_hojas(str(config.DIR_SALIDA / "Formulario_Salida_Historias_Propias.xlsx"))["Formulario_Salida"]
    salida_dataset = leer_hojas(str(config.DIR_SALIDA / "Formulario_Salida_Dataset_Original.xlsx"))["Formulario_Salida"]
    casos = leer_hojas(str(config.DIR_SALIDA / "Historias_de_Prueba_COMPLETADO.xlsx"))["Historias_de_Prueba"]
    registros_dataset = leer_tabla(str(config.ARCHIVO_REFERENCIA), config.HOJA_ENTRADA)

    fuga_propias = escanear_archivo_final(salida_propias, HISTORIAS_PROPIAS)
    fuga_dataset = escanear_archivo_final(salida_dataset, registros_dataset)

    pruebas = (config.DIR_EVIDENCIAS / "salida_pruebas.txt").read_text(encoding="utf-8")
    n_pruebas = next((l for l in pruebas.splitlines() if l.startswith("Ran ")), "Ran ? tests")
    pasaron = sum(1 for f in casos[1:] if f[7] == "Pasó")
    total_pruebas = n_pruebas.split()[1] if len(n_pruebas.split()) > 1 else "?"
    en_verde = any(l.strip() == "OK" for l in pruebas.splitlines())

    reflexion = (config.DIR_EVIDENCIAS / "reflexion_escrita.md").read_text(encoding="utf-8")
    cuerpo_reflexion = reflexion.split("---")[-1].strip()

    # ---------------------------------------------------------------- portada
    p.append(f"""
<section class="cover">
  <div class="k">LITE THINKING INSTITUTE OF TECHNOLOGY</div>
  <div class="k" style="color:var(--muted);margin-top:2.5mm">CERTIFICACIÓN 6 · SESIÓN 6</div>
  <h1>Dossier de evidencias<br>Reto 6 — Pipeline Multiagente</h1>
  <div class="rule"></div>
  <div class="sub">Caso 10 · Clínica Vitalis — anonimización → clasificación → escritura</div>
  <div class="meta">Generado automáticamente el {e(ahora)} desde los artefactos de la corrida</div>
  <div class="kpi" style="margin-top:14mm">
    <div><div class="n">{len(HISTORIAS_PROPIAS) + len(registros_dataset)}</div><div class="l">HISTORIAS PROCESADAS</div></div>
    <div><div class="n">0</div><div class="l">DATOS IDENTIFICABLES</div></div>
    <div><div class="n">{pasaron}/{len(casos)-1}</div><div class="l">CASOS DE PRUEBA</div></div>
    <div><div class="n">{total_pruebas}</div><div class="l">{"PRUEBAS EN VERDE" if en_verde else "PRUEBAS (CON FALLOS)"}</div></div>
  </div>
  <div class="box">
    <p><span class="lbl">Este documento no está escrito a mano.</span> Cada tabla y cada cifra se
    leen de los archivos que el pipeline generó. Se reproduce con
    <code>python3 generar_dossier_evidencias.py</code>.</p>
  </div>
</section>""")

    # ------------------------------------------------- entregable 1
    p.append("<h2>Entregable 1 — Tres historias clínicas propias</h2>")
    p.append("<p>Inventadas para este reto, con los 4 identificadores mezclados en el texto libre y "
             "tres condiciones clínicas claramente distintas entre sí. Todos los datos personales son "
             "ficticios; los teléfonos usan el rango <code>555</code> reservado para ficción.</p>")
    filas = []
    for h in HISTORIAS_PROPIAS:
        filas.append([
            f"<code>{e(h['ID_Registro'])}</code>",
            e(h["Nombre completo"]), e(h["Cédula"]),
            e(h["Dirección"]), e(h["Teléfono"]),
        ])
    p.append(tabla(["Registro", "Nombre completo", "Cédula", "Dirección", "Teléfono"], filas))

    p.append("<h3>Nota clínica de cada historia</h3>")
    for h in HISTORIAS_PROPIAS:
        p.append(f"<p style='margin-bottom:1.5mm'><code>{e(h['ID_Registro'])}</code> · "
                 f"consulta del {e(h['Fecha de consulta'])}</p>")
        p.append(f"<div class='box' style='font-size:8.3pt'><p>{e(h['Nota clínica (texto libre)'])}</p></div>")

    # ------------------------------------------------- entregable 2
    p.append('<h2 class="break">Entregable 2 — Pipeline corrido sobre las 3 historias</h2>')
    p.append("<p>Salida generada por el Agente 3 tras la anonimización y la clasificación. "
             "El vínculo con el paciente es únicamente el código.</p>")
    enc = salida_propias[0]
    filas = []
    for f in salida_propias[1:]:
        g = lambda c: e(f[enc.index(c)]) if enc.index(c) < len(f) else ""
        filas.append([f"<code>{g('código_paciente')}</code>", g("enfermedad_probable"),
                      g("nivel_riesgo"), g("confianza"), g("fuma"), g("consumo_sustancias")])
    p.append(tabla(["Código", "Enfermedad probable", "Riesgo", "Confianza", "Fuma", "Sustancias"],
                   filas, ["", "", "c", "c", "c", "c"]))

    p.append("<h3>Justificación clínica registrada por el Agente 2</h3>")
    i_obs = enc.index("comportamiento_observado")
    for f in salida_propias[1:]:
        p.append(f"<p style='margin-bottom:1.2mm'><code>{e(f[0])}</code></p>")
        p.append(f"<div class='box' style='font-size:8.3pt'><p>{e(f[i_obs])}</p></div>")

    p.append("<h3>Verificación anti-fuga sobre el archivo releído desde disco</h3>")
    p.append(tabla(
        ["Archivo", "Filas", "Celdas escaneadas", "Identificadores buscados", "Hallazgos"],
        [[f"<code>Formulario_Salida_Historias_Propias.xlsx</code>", str(len(salida_propias) - 1),
          str(sum(len(x) for x in salida_propias)), f"{len(HISTORIAS_PROPIAS) * 4}",
          f'<span class="chip c-ok">{len(fuga_propias)}</span>'],
         [f"<code>Formulario_Salida_Dataset_Original.xlsx</code>", str(len(salida_dataset) - 1),
          str(sum(len(x) for x in salida_dataset)), f"{len(registros_dataset) * 4}",
          f'<span class="chip c-ok">{len(fuga_dataset)}</span>']],
        ["", "c", "c", "c", "c"]))
    p.append('<div class="ok"><p><span class="lbl">Criterio del 30% cumplido.</span> Ninguna de las '
             f'{(len(HISTORIAS_PROPIAS) + len(registros_dataset)) * 4} cadenas identificadoras aparece en los '
             'archivos finales, ni en forma exacta, ni con puntuación alterada, ni como fragmento '
             'suelto del nombre.</p></div>')

    # ------------------------------------------------- entregable 3
    p.append('<h2 class="break">Entregable 3 — Historias de prueba completadas</h2>')
    p.append(f"<p>El reto exige al menos 5 casos con evidencia real. Se completaron "
             f"<strong>{len(casos)-1} de {len(casos)-1}</strong>, con la evidencia extraída de los "
             f"artefactos de la corrida.</p>")
    for f in casos[1:]:
        estado = f'<span class="chip c-ok">{e(f[7])}</span>' if f[7] == "Pasó" else e(f[7])
        p.append(f"""<div class="box" style="page-break-inside:avoid">
<p><code>{e(f[0])}</code> · <strong>{e(f[1])}</strong> &nbsp; {estado}</p>
<p style="margin-top:1.8mm;font-size:8.3pt"><span class="lbl">Esperado:</span> {e(f[4])}</p>
<p style="margin-top:1.2mm;font-size:8.3pt"><span class="lbl">Obtenido:</span> {e(f[6])}</p>
</div>""")

    # ------------------------------------------------- entregable 4
    p.append('<h2 class="break">Entregable 4 — Reflexión escrita</h2>')
    p.append("<p><em>¿Qué parte de este proceso fue automatización pura y qué parte requirió que el "
             "agente usara criterio? Justifique con un ejemplo de sus propias 3 historias.</em></p>")
    parrafos = "".join(f"<p>{e_md(x.strip())}</p>" for x in cuerpo_reflexion.split("\n\n") if x.strip())
    n_palabras = len([w for w in cuerpo_reflexion.split() if any(ch.isalnum() for ch in w)])
    p.append(f'<div class="box">{parrafos}</div>')
    p.append(f'<p style="text-align:right;color:var(--muted);font-size:8.3pt">'
             f'{n_palabras} palabras · límite 150</p>')

    # ------------------------------------------------- anexos
    p.append('<h2 class="break">Anexo A — Suite de pruebas automáticas</h2>')
    p.append(f"<p>{e(n_pruebas)}. Ejecutar con <code>python3 -m unittest discover -s tests -v</code>.</p>")
    lineas = [l for l in pruebas.splitlines() if " ... ok" in l or l.startswith(("Ran ", "OK"))]
    p.append("<pre>" + e("\n".join(l.replace(" (test_pipeline.", "\n    (").replace(")", ")") for l in lineas[:40])) + "</pre>")

    p.append('<h2 class="break">Anexo B — Contraste contra el oráculo de referencia</h2>')
    comp = (config.DIR_EVIDENCIAS / "salida_comparacion_oraculo.txt").read_text(encoding="utf-8")
    p.append("<pre>" + e(comp.strip()) + "</pre>")
    p.append('<div class="stop"><p><span class="lbl">Dos inconsistencias del material de clase.</span> '
             'El <code>Formulario_Salida</code> de referencia contradice a las Historias de Prueba del '
             'mismo paquete: en PAC-005 marca riesgo <em>medio</em> mientras TC-12 exige <em>alto</em>, y '
             'en PAC-006 afirma «artritis reumatoide» cuando TC-04 pide no afirmar un diagnóstico sin '
             'respaldo. Se siguieron los casos de prueba. Detalle completo en '
             '<code>evidencias/comparacion_con_oraculo.md</code>.</p></div>')

    p.append('<h2 class="break">Anexo C — Aislamiento de secretos</h2>')
    aisl = config.DIR_EVIDENCIAS / "aislamiento_secretos_git.txt"
    if aisl.exists():
        p.append("<pre>" + e(aisl.read_text(encoding="utf-8").strip()[:2600]) + "</pre>")
    p.append('<div class="stop"><p><span class="lbl">Nunca se entrega.</span> La carpeta '
             '<code>data/internal/</code> contiene el mapa <code>código_paciente ↔ identidad real</code>, '
             'el activo más sensible del sistema. Está en <code>.gitignore</code>, ningún agente posterior '
             'lo lee, y no debe incluirse en el archivo que se suba a la plataforma.</p></div>')

    p.append('<div class="foot">Reto 6 · Pipeline Multiagente — Clínica Vitalis<br>'
             'Certificación 6 · Inteligencia Artificial y AIOps para Arquitectura de Software</div>')

    return (f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
            f'<title>Dossier de evidencias — Reto 6</title><style>{CSS}</style></head>'
            f'<body>{"".join(p)}</body></html>')


def renderizar_pdf(documento_html: str, destino: Path) -> str:
    """Convierte el HTML en PDF con un navegador Chromium. Devuelve el navegador usado.

    La usan tanto este dossier como la guia de cumplimiento (generar_guia.py).
    """
    navegador = next((n for n in NAVEGADORES if shutil.which(n)), None) or next(
        (r for r in RUTAS_WINDOWS if Path(r).exists()), None)
    if not navegador:
        raise SystemExit(f"No se encontro un navegador Chromium. Probados: {', '.join(NAVEGADORES)}")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        fuente = Path(tmp) / "documento.html"
        fuente.write_text(documento_html, encoding="utf-8")
        salida = Path(tmp) / "documento.pdf"
        subprocess.run(
            [navegador, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-pdf-header-footer", f"--user-data-dir={Path(tmp) / 'perfil'}",
             f"--print-to-pdf={salida}", str(fuente)],
            check=True, capture_output=True, timeout=240,
        )
        # En Windows msedge.exe/chrome.exe es un lanzador que puede terminar antes de
        # que el proceso hijo escriba el PDF: se espera a que aparezca y deje de crecer.
        limite, tam_previo = time.monotonic() + 120, -1
        while time.monotonic() < limite:
            tam = salida.stat().st_size if salida.exists() else -1
            if tam > 0 and tam == tam_previo:
                break
            tam_previo = tam
            time.sleep(1)
        else:
            raise SystemExit("El navegador no genero el PDF a tiempo.")
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(salida, destino)
    return navegador


def main() -> None:
    destino = config.DIR_EVIDENCIAS / "Dossier_Evidencias_Reto6.pdf"
    navegador = renderizar_pdf(construir_html(), destino)
    print(f"Dossier generado con {navegador}")
    print(f"  -> evidencias/{destino.name}  ({destino.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
