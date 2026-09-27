"""Suite de pruebas obligatorias — seccion 10.2 del documento de arquitectura.

Se usa `unittest` (libreria estandar) en lugar de `pytest` por la misma razon
documentada en core/xlsx_io.py: en este equipo no hay `pip` disponible.

Ejecutar desde la raiz del proyecto:
    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import config  # noqa: E402
from agents.agente1_anonimizador import anonimizar_lote, anonimizar_registro  # noqa: E402
from agents.agente2_clasificador import clasificar_via_track_b  # noqa: E402
from core.contratos import (  # noqa: E402
    COLUMNAS_IDENTIFICADORAS,
    ENCABEZADOS_SALIDA,
    PaqueteAnonimizado,
    RegistroClasificado,
    ViolacionDeContrato,
    validar_payload_agente2,
)
from core.verificacion_antifuga import buscar_residuos, escanear_archivo_final  # noqa: E402
from core.xlsx_io import leer_hojas, leer_tabla  # noqa: E402
from data.historias_propias import HISTORIAS_PROPIAS  # noqa: E402


def _registros_dataset() -> list[dict[str, str]]:
    return leer_tabla(str(config.ARCHIVO_REFERENCIA), config.HOJA_ENTRADA)


class TestAntifugaAgente1(unittest.TestCase):
    """Ninguna de las cadenas identificadoras sobrevive al Agente 1."""

    def test_dataset_original_48_cadenas(self):
        registros = _registros_dataset()
        exitosos, fallidos = anonimizar_lote(registros)
        self.assertEqual(fallidos, [], "ningun registro deberia fallar la anonimizacion")
        self.assertEqual(len(exitosos), 12)

        comprobadas = 0
        for resultado in exitosos:
            residuos = buscar_residuos(
                resultado.paquete.texto_anonimizado, resultado.registro_original
            )
            self.assertEqual(
                residuos, [],
                f"{resultado.paquete.codigo_paciente} dejo residuos: {residuos}",
            )
            comprobadas += sum(
                1 for c in COLUMNAS_IDENTIFICADORAS if (resultado.registro_original.get(c) or "").strip()
            )
        self.assertEqual(comprobadas, 48, "deben verificarse 12 registros x 4 identificadores")

    def test_historias_propias(self):
        exitosos, fallidos = anonimizar_lote(HISTORIAS_PROPIAS)
        self.assertEqual(fallidos, [])
        self.assertEqual(len(exitosos), 3)
        for resultado in exitosos:
            self.assertEqual(
                buscar_residuos(resultado.paquete.texto_anonimizado, resultado.registro_original),
                [],
            )

    def test_los_4_identificadores_estan_presentes_en_la_entrada(self):
        """Criterio de la rubrica: las 3 historias traen los 4 identificadores."""
        for historia in HISTORIAS_PROPIAS:
            for columna in COLUMNAS_IDENTIFICADORAS:
                self.assertTrue(
                    (historia.get(columna) or "").strip(),
                    f"{historia['ID_Registro']} no tiene {columna}",
                )
                self.assertIn(
                    historia[columna], historia["Nota clínica (texto libre)"],
                    f"{historia['ID_Registro']}: {columna} debe estar mezclado en el texto libre",
                )


class TestContratoAgente2(unittest.TestCase):
    """El payload hacia el LLM lleva exactamente 2 claves."""

    def test_payload_tiene_exactamente_dos_claves(self):
        exitosos, _ = anonimizar_lote(_registros_dataset())
        for resultado in exitosos:
            payload = resultado.paquete.como_payload()
            self.assertEqual(set(payload), {"codigo_paciente", "texto_anonimizado"})
            validar_payload_agente2(payload)

    def test_rechaza_clave_extra(self):
        payload = {"codigo_paciente": "PAC-001", "texto_anonimizado": "x", "Cédula": "52.884.117"}
        with self.assertRaises(ViolacionDeContrato):
            validar_payload_agente2(payload)

    def test_rechaza_clave_faltante(self):
        with self.assertRaises(ViolacionDeContrato):
            validar_payload_agente2({"codigo_paciente": "PAC-001"})


class TestReglaIndeterminado(unittest.TestCase):
    """enfermedad_probable='indeterminado' exige confianza='baja'."""

    def test_el_contrato_rechaza_indeterminado_con_confianza_alta(self):
        with self.assertRaises(ViolacionDeContrato):
            RegistroClasificado(
                codigo_paciente="PAC-001", enfermedad_probable="indeterminado",
                nivel_riesgo="bajo", comportamiento_observado="x", confianza="alta",
                antecedentes="ninguno registrado", fuma="No", consumo_sustancias="No",
            )

    def test_corridas_reales_cumplen_la_regla(self):
        for etiqueta in ("Historias_Propias", "Dataset_Original"):
            ruta = config.DIR_SALIDA / f"Formulario_Salida_{etiqueta}.xlsx"
            self.assertTrue(ruta.exists(), f"falta la salida de {etiqueta}; corra el orquestador")
            filas = leer_hojas(str(ruta))["Formulario_Salida"]
            encabezados = filas[0]
            i_enf = encabezados.index("enfermedad_probable")
            i_conf = encabezados.index("confianza")
            for fila in filas[1:]:
                if fila[i_enf].strip().lower() == "indeterminado":
                    self.assertEqual(
                        fila[i_conf], "baja",
                        f"{fila[0]} es indeterminado pero confianza={fila[i_conf]}",
                    )

    def test_el_pipeline_produce_al_menos_un_indeterminado(self):
        """Criterio de aceptacion: no debe inventar certeza donde no la hay."""
        filas = leer_hojas(str(config.DIR_SALIDA / "Formulario_Salida_Dataset_Original.xlsx"))["Formulario_Salida"]
        i_enf = filas[0].index("enfermedad_probable")
        indeterminados = [f[0] for f in filas[1:] if f[i_enf].strip().lower() == "indeterminado"]
        self.assertGreaterEqual(len(indeterminados), 1, "el pipeline nunca declaro indeterminado")


class TestAntifugaArchivoFinal(unittest.TestCase):
    """El .xlsx entregable, releido desde disco, no contiene identificadores."""

    def _verificar(self, etiqueta: str, registros: list[dict[str, str]]):
        ruta = config.DIR_SALIDA / f"Formulario_Salida_{etiqueta}.xlsx"
        self.assertTrue(ruta.exists(), f"falta {ruta}")
        celdas = leer_hojas(str(ruta))["Formulario_Salida"]
        hallazgos = escanear_archivo_final(celdas, registros)
        self.assertEqual(hallazgos, [], f"{etiqueta}: {hallazgos}")

    def test_dataset_original(self):
        self._verificar("Dataset_Original", _registros_dataset())

    def test_historias_propias(self):
        self._verificar("Historias_Propias", HISTORIAS_PROPIAS)

    def test_encabezados_y_orden_exactos(self):
        for etiqueta in ("Historias_Propias", "Dataset_Original"):
            filas = leer_hojas(str(config.DIR_SALIDA / f"Formulario_Salida_{etiqueta}.xlsx"))["Formulario_Salida"]
            self.assertEqual(tuple(filas[0]), ENCABEZADOS_SALIDA)

    def test_la_salida_no_incluye_la_hoja_de_entrada(self):
        for etiqueta in ("Historias_Propias", "Dataset_Original"):
            hojas = leer_hojas(str(config.DIR_SALIDA / f"Formulario_Salida_{etiqueta}.xlsx"))
            self.assertEqual(list(hojas), ["Formulario_Salida"])


class TestAislamientoMapaAuditoria(unittest.TestCase):
    """Ni el Agente 2 ni el Agente 3 tocan el mapa codigo <-> identidad."""

    def _importa(self, archivo: Path) -> set[str]:
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        modulos: set[str] = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                modulos.update(a.name for a in nodo.names)
            elif isinstance(nodo, ast.ImportFrom):
                if nodo.module:
                    modulos.add(nodo.module)
                modulos.update(a.name for a in nodo.names)
        return modulos

    def test_agente2_no_importa_auditoria(self):
        modulos = self._importa(RAIZ / "agents" / "agente2_clasificador.py")
        self.assertNotIn("auditoria", {m.split(".")[-1] for m in modulos})

    def test_agente3_no_importa_auditoria(self):
        modulos = self._importa(RAIZ / "agents" / "agente3_generador_salida.py")
        self.assertNotIn("auditoria", {m.split(".")[-1] for m in modulos})

    def test_el_mapa_vive_fuera_de_output(self):
        for archivo in config.DIR_INTERNO.glob("mapa_auditoria_*.xlsx"):
            self.assertNotIn("output", archivo.parts)
        self.assertEqual(list(config.DIR_SALIDA.glob("mapa_auditoria_*")), [])

    def test_gitignore_excluye_data_internal(self):
        contenido = (RAIZ / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("data/internal/", contenido)


class TestSeguridadCredenciales(unittest.TestCase):
    """TC-13: la API key no aparece en texto plano en ningun archivo."""

    def test_no_hay_api_key_hardcodeada(self):
        # El prefijo se arma en tiempo de ejecucion para que la cadena literal
        # no exista en este archivo: si estuviera escrita entera, este mismo
        # test se detectaria a si mismo como un hallazgo.
        prefijo = "sk-" + "or-" + "v1-"
        propio = Path(__file__).resolve()

        sospechosos: list[str] = []
        for archivo in RAIZ.rglob("*.py"):
            if archivo.resolve() == propio or "data/internal" in str(archivo):
                continue
            texto = archivo.read_text(encoding="utf-8", errors="ignore")
            if prefijo in texto:
                sospechosos.append(str(archivo.relative_to(RAIZ)))
        self.assertEqual(sospechosos, [], f"API key en texto plano en: {sospechosos}")

    def test_no_hay_api_key_en_configuracion_ni_datos(self):
        """El barrido cubre tambien .json, .md, .txt y .env del proyecto."""
        prefijo = "sk-" + "or-" + "v1-"
        sospechosos: list[str] = []
        for patron in ("*.json", "*.md", "*.txt", "*.env", "*.yaml", "*.yml"):
            for archivo in RAIZ.rglob(patron):
                texto = archivo.read_text(encoding="utf-8", errors="ignore")
                if prefijo in texto:
                    sospechosos.append(str(archivo.relative_to(RAIZ)))
        self.assertEqual(sospechosos, [], f"API key en texto plano en: {sospechosos}")

    def test_la_key_se_lee_de_variable_de_entorno(self):
        fuente = (RAIZ / "config.py").read_text(encoding="utf-8")
        self.assertIn("os.environ", fuente)
        self.assertIn("OPENROUTER_API_KEY", fuente)


class TestCasosLimite(unittest.TestCase):
    """Robustez: nota vacia y fallo de clasificacion."""

    def test_nota_vacia_no_tumba_el_lote(self):
        registros = _registros_dataset()
        corrupto = dict(registros[0])
        corrupto["Nota clínica (texto libre)"] = "   "
        lote = [corrupto] + registros[1:]

        exitosos, fallidos = anonimizar_lote(lote)
        self.assertEqual(len(fallidos), 1, "la nota vacia debe quedar marcada")
        self.assertIn("registro_invalido", fallidos[0][1])
        self.assertEqual(len(exitosos), 11, "los demas registros deben continuar")

    def test_registro_sin_clasificacion_no_se_inventa(self):
        paquete = PaqueteAnonimizado(codigo_paciente="PAC-999", texto_anonimizado="Paciente [ANON].")
        ruta = config.RAIZ / "data" / "clasificaciones_track_b_Dataset_Original.json"
        with self.assertRaises(ViolacionDeContrato):
            clasificar_via_track_b(paquete, ruta)

    def test_valores_categoricos_invalidos_se_rechazan(self):
        with self.assertRaises(ViolacionDeContrato):
            RegistroClasificado(
                codigo_paciente="PAC-001", enfermedad_probable="x", nivel_riesgo="altisimo",
                comportamiento_observado="y", confianza="alta",
                antecedentes="z", fuma="No", consumo_sustancias="No",
            )


class TestCoberturaCompleta(unittest.TestCase):
    """TC-10 y TC-11: unicidad de codigos y cero historias omitidas."""

    def test_codigos_unicos_y_cobertura(self):
        casos = {"Historias_Propias": 3, "Dataset_Original": 12}
        for etiqueta, esperadas in casos.items():
            filas = leer_hojas(str(config.DIR_SALIDA / f"Formulario_Salida_{etiqueta}.xlsx"))["Formulario_Salida"]
            codigos = [f[0] for f in filas[1:]]
            self.assertEqual(len(codigos), esperadas, f"{etiqueta}: se esperaban {esperadas} filas")
            self.assertEqual(len(set(codigos)), esperadas, f"{etiqueta}: hay codigos duplicados")

    def test_trazabilidad_codigo_contra_mapa_de_auditoria(self):
        """TC-09: cada codigo de la salida existe en el mapa, sin mezclas."""
        for etiqueta in ("Historias_Propias", "Dataset_Original"):
            salida = leer_hojas(str(config.DIR_SALIDA / f"Formulario_Salida_{etiqueta}.xlsx"))["Formulario_Salida"]
            mapa = leer_hojas(str(config.DIR_INTERNO / f"mapa_auditoria_{etiqueta}.xlsx"))["Mapa_Auditoria"]
            codigos_salida = {f[0] for f in salida[1:]}
            codigos_mapa = {f[0] for f in mapa[1:]}
            self.assertEqual(codigos_salida, codigos_mapa, f"{etiqueta}: codigos desalineados")


class TestEntregablesDelReto(unittest.TestCase):
    """Los 4 entregables existen tras una reconstruccion desde cero.

    Esta prueba nace de un fallo real: la primera version generaba el
    entregable 1 con un script suelto, asi que al borrar data/output/ y
    reconstruir, ese archivo no volvia a aparecer. Ahora el orquestador lo
    produce y esta prueba lo verifica.
    """

    def test_los_cuatro_entregables_existen(self):
        esperados = {
            "1 · 3 historias propias": config.DIR_SALIDA / "Historias_Propias_Reto.xlsx",
            "2 · pipeline corrido": config.DIR_SALIDA / "Formulario_Salida_Historias_Propias.xlsx",
            "3 · historias de prueba": config.DIR_SALIDA / "Historias_de_Prueba_COMPLETADO.xlsx",
            "4 · reflexion escrita": config.DIR_EVIDENCIAS / "reflexion_escrita.md",
        }
        faltantes = [nombre for nombre, ruta in esperados.items() if not ruta.exists()]
        self.assertEqual(faltantes, [], f"faltan entregables: {faltantes}")

    def test_entregable_1_tiene_las_3_historias_con_4_identificadores(self):
        ruta = config.DIR_SALIDA / "Historias_Propias_Reto.xlsx"
        self.assertTrue(ruta.exists(), "falta el entregable 1; corra el orquestador con --fuente propias")
        filas = leer_hojas(str(ruta))[config.HOJA_ENTRADA]
        encabezados = filas[0]
        self.assertEqual(len(filas) - 1, 3, "deben ser exactamente 3 historias")
        for columna in COLUMNAS_IDENTIFICADORAS:
            self.assertIn(columna, encabezados, f"falta la columna {columna}")
            i = encabezados.index(columna)
            for fila in filas[1:]:
                self.assertTrue(fila[i].strip(), f"{fila[0]}: {columna} vacio")

    def test_la_reflexion_no_excede_150_palabras(self):
        texto = (config.DIR_EVIDENCIAS / "reflexion_escrita.md").read_text(encoding="utf-8")
        cuerpo = texto.split("---")[-1]
        palabras = [w for w in cuerpo.split() if any(c.isalnum() for c in w)]
        self.assertLessEqual(len(palabras), 150, f"la reflexion tiene {len(palabras)} palabras")
        self.assertGreater(len(palabras), 60, "la reflexion es sospechosamente corta")


if __name__ == "__main__":
    unittest.main(verbosity=2)
