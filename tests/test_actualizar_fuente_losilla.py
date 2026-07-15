import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_fuente_losilla as afl


def _entidades(texto):
    """Aplica el escapado minimo propio que usa eduardolosilla.es dentro del
    <script id="eduardo-losilla-state">: " -> &q;, < -> &l;, > -> &g;,
    & -> &a; (no son entidades HTML estandar)."""
    return texto.replace("&", "&a;").replace('"', "&q;").replace("<", "&l;").replace(">", "&g;")


def _html_con_estado(estado_json, jornada_texto_extra=""):
    bloque = _entidades(estado_json)
    return (
        "<html><body>"
        f"<div>JORNADA 76 (selector de temporada, no la actual){jornada_texto_extra}</div>"
        f'<script id="eduardo-losilla-state" type="application/json">{bloque}</script>'
        "</body></html>"
    )


ESTADO_JSON = """{
  "datosGeneralesQuiniela": {"jornada": 73, "temporada": 2026},
  "jornada_73_2026": {
    "partidos": [
      {"num": 1, "local": "BODOGLIMT", "visitante": "FREDRIKSTAD"},
      {"num": 2, "local": "HAMKAN", "visitante": "TROMSO"},
      {"num": 15, "local": "GANADOR SF1", "visitante": "GANADOR SF2"}
    ]
  },
  "probabilidades_73_2026": {
    "partidos": {
      "quinielista": [
        {"numero": 1, "porc_1": 92, "porc_X": 6, "porc_2": 2},
        {"numero": 2, "porc_1": 0, "porc_X": 28, "porc_2": 72},
        {"numero": 15, "porc_15L_0": 10, "porc_15L_1": 48, "porc_15L_2": 30, "porc_15L_M": 12,
         "porc_15V_0": 22, "porc_15V_1": 53, "porc_15V_2": 20, "porc_15V_M": 5}
      ]
    }
  }
}"""


class ExtraerEstadoEmbebidoTests(unittest.TestCase):
    def test_decodifica_el_escapado_propio_y_parsea_json(self):
        html = _html_con_estado(ESTADO_JSON)
        estado = afl.extraer_estado_embebido(html)
        self.assertIsInstance(estado, dict)
        self.assertEqual(estado["datosGeneralesQuiniela"]["jornada"], 73)

    def test_ninguna_etiqueta_devuelve_none(self):
        self.assertIsNone(afl.extraer_estado_embebido("<html><body>sin estado</body></html>"))

    def test_json_invalido_devuelve_none(self):
        html = '<script id="eduardo-losilla-state" type="application/json">esto no es json&q;</script>'
        self.assertIsNone(afl.extraer_estado_embebido(html))


class JornadaYEquiposEmbebidosTests(unittest.TestCase):
    def setUp(self):
        self.estado = afl.extraer_estado_embebido(_html_con_estado(ESTADO_JSON))

    def test_jornada_activa_no_se_confunde_con_el_selector_de_temporada(self):
        """Antes, extraer_jornada() hacia max() sobre todo el texto de la
        pagina y devolvia 76 (el total de jornadas de la temporada, que
        aparece en el selector) en vez de la 73 real -aunque el HTML
        tambien contenga el texto "JORNADA 76" en otro sitio."""
        jornada, temporada = afl.jornada_y_temporada_activas(self.estado)
        self.assertEqual(jornada, 73)
        self.assertEqual(temporada, 2026)

    def test_equipos_por_numero_de_partido(self):
        equipos = afl.partidos_de_jornada_embebida(self.estado, 73, 2026)
        self.assertEqual(equipos[1], ("BODOGLIMT", "FREDRIKSTAD"))
        self.assertEqual(equipos[2], ("HAMKAN", "TROMSO"))
        self.assertEqual(equipos[15], ("GANADOR SF1", "GANADOR SF2"))


class ExtraerProbabilidadesDesdeEstadoTests(unittest.TestCase):
    def test_construye_partidos_1x2_y_pleno_al_15(self):
        estado = afl.extraer_estado_embebido(_html_con_estado(ESTADO_JSON))
        resultado = afl.extraer_probabilidades_desde_estado(estado)

        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["jornada"], 73)
        self.assertEqual(len(resultado["partidos_1x2"]), 2)

        p1 = resultado["partidos_1x2"][0]
        self.assertEqual(p1["local"], "BODOGLIMT")
        self.assertEqual(p1["probabilidades_signo"], {"1": 92.0, "X": 6.0, "2": 2.0})

        pleno = resultado["pleno_al_15"]
        self.assertEqual(pleno["local"], "GANADOR SF1")
        self.assertEqual(pleno["probabilidades_goles_visitante"]["M"], 5.0)

    def test_un_porcentaje_real_de_cero_no_se_pierde(self):
        """numero() trata un 0 de tipo str(0 or "") como vacio y lo
        convierte en None -por eso los valores nativos del JSON se
        convierten con float() directo, no con numero()."""
        estado = afl.extraer_estado_embebido(_html_con_estado(ESTADO_JSON))
        resultado = afl.extraer_probabilidades_desde_estado(estado)
        p2 = resultado["partidos_1x2"][1]
        self.assertEqual(p2["probabilidades_signo"]["1"], 0.0)
        self.assertIsNotNone(p2["probabilidades_signo"]["1"])

    def test_sin_estado_devuelve_none(self):
        self.assertIsNone(afl.extraer_probabilidades_desde_estado(None))
        self.assertIsNone(afl.extraer_probabilidades_desde_estado({}))


class ExtraerProbabilidadesConMockTests(unittest.TestCase):
    def setUp(self):
        self._original_descargar = afl.descargar

    def tearDown(self):
        afl.descargar = self._original_descargar

    def test_usa_el_estado_embebido_cuando_esta_disponible(self):
        afl.descargar = lambda url: _html_con_estado(ESTADO_JSON)
        resultado = afl.extraer_probabilidades()
        self.assertEqual(resultado["jornada"], 73)
        self.assertEqual(len(resultado["partidos_1x2"]), 2)

    def test_cae_al_scraping_de_html_si_no_hay_estado(self):
        afl.descargar = lambda url: "<html><body>sin estado embebido, sin tablas</body></html>"
        resultado = afl.extraer_probabilidades()
        self.assertIsNone(resultado)


class FusionarCuotasTests(unittest.TestCase):
    def test_conserva_cuotas_previas_si_el_scrape_nuevo_no_trae_valores(self):
        anterior = {
            "cuotas": {
                "partidos": [
                    {"numero": 1, "local": "A", "visitante": "B", "cuota_media_1": 1.5, "cuota_media_X": 3.2, "cuota_media_2": 5.0},
                ]
            }
        }
        nuevo = {
            "partidos": [
                {"numero": 1, "local": "A", "visitante": "B", "cuota_media_1": None, "cuota_media_X": None, "cuota_media_2": None},
            ]
        }

        fusionado = afl.fusionar_cuotas(anterior, nuevo)

        self.assertEqual(fusionado["partidos"][0]["cuota_media_1"], 1.5)

    def test_usa_las_cuotas_nuevas_si_traen_datos_reales(self):
        anterior = {"cuotas": {"partidos": [{"numero": 1, "cuota_media_1": 1.5, "cuota_media_X": 3.2, "cuota_media_2": 5.0}]}}
        nuevo = {"partidos": [{"numero": 1, "cuota_media_1": 1.8, "cuota_media_X": 3.1, "cuota_media_2": 4.2}]}

        fusionado = afl.fusionar_cuotas(anterior, nuevo)

        self.assertEqual(fusionado["partidos"][0]["cuota_media_1"], 1.8)

    def test_sin_scrape_nuevo_conserva_todo_lo_anterior(self):
        anterior = {"cuotas": {"partidos": [{"numero": 1, "cuota_media_1": 1.5}]}}
        self.assertEqual(afl.fusionar_cuotas(anterior, None), anterior["cuotas"])


class ExtraerCuotasJornadaTests(unittest.TestCase):
    def setUp(self):
        self._original_descargar = afl.descargar

    def tearDown(self):
        afl.descargar = self._original_descargar

    def test_usa_la_jornada_del_estado_embebido_no_el_max_del_texto(self):
        afl.descargar = lambda url: _html_con_estado(ESTADO_JSON)
        resultado = afl.extraer_cuotas()
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado["jornada"], 73)


if __name__ == "__main__":
    unittest.main()
