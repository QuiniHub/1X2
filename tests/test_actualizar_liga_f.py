import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import actualizar_liga_f as liga_f  # noqa: E402


HTML_CLASIFICACION = """
<html><body>
<table class="wikitable">
<tr><th>Pos</th><th>Team<span>v t e</span></th><th>Pld</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th><th>Pts</th><th>Qualification or relegation</th></tr>
<tr><td>1</td><th scope="row"><a href="#">Barcelona</a></th><td>9</td><td>8</td><td>1</td><td>0</td><td>35</td><td>4</td><td>+31</td><td>25</td><td rowspan="2">Champions League</td></tr>
<tr><td>2</td><th scope="row"><a href="#">Real Madrid</a></th><td>9</td><td>6</td><td>2</td><td>1</td><td>20</td><td>14</td><td>+6</td><td>20</td></tr>
<tr><td>3</td><th scope="row"><a href="#">Atlético Madrid</a></th><td>9</td><td>6</td><td>1</td><td>2</td><td>19</td><td>10</td><td>+9</td><td>19</td><td></td></tr>
<tr><td>4</td><th scope="row"><a href="#">Logroño United</a></th><td>9</td><td>4</td><td>1</td><td>4</td><td>12</td><td>13</td><td>&minus;1</td><td>13</td><td></td></tr>
<tr><td>5</td><th scope="row"><a href="#">Deportivo Abanca</a></th><td>9</td><td>3</td><td>3</td><td>3</td><td>10</td><td>11</td><td>&minus; 1</td><td>12</td><td></td></tr>
<tr><td>6</td><th scope="row"><a href="#">Tenerife</a></th><td>8</td><td>3</td><td>2</td><td>3</td><td>11</td><td>12</td><td>&minus;1</td><td>11</td><td></td></tr>
<tr><td>7</td><th scope="row"><a href="#">Badalona Women</a></th><td>9</td><td>2</td><td>3</td><td>4</td><td>10</td><td>18</td><td>&minus;8</td><td>9</td><td></td></tr>
<tr><td>8</td><th scope="row"><a href="#">Eibar</a></th><td>9</td><td>2</td><td>3</td><td>4</td><td>9</td><td>13</td><td>&minus;4</td><td>9</td><td></td></tr>
<tr><td>9</td><th scope="row"><a href="#">Sevilla</a></th><td>9</td><td>2</td><td>2</td><td>5</td><td>10</td><td>16</td><td>&minus;6</td><td>8</td><td></td></tr>
<tr><td>10</td><th scope="row"><a href="#">Valencia</a></th><td>9</td><td>1</td><td>1</td><td>7</td><td>6</td><td>17</td><td>&minus;11</td><td>4</td><td rowspan="1">Relegation</td></tr>
</table>
</body></html>
"""

HTML_JORNADAS = """
<html><body>
<table class="wikitable">
<tr><th colspan="8">Game day 1</th></tr>
<tr><th>Home team</th><th>Results</th><th>Away team</th><th>Stadium</th><th>Date</th><th>Time</th><th>Attendance</th><th>Referee</th></tr>
<tr><td>Real Madrid</td><td>3 – 2</td><td>Atlético Madrid</td><td>Di Stéfano</td><td rowspan="2">29 August 2026</td><td>12:00</td><td>1,815</td><td>A</td></tr>
<tr><td>Barcelona</td><td>5 – 0</td><td>Tenerife</td><td>Johan Cruyff</td><td>19:00</td><td>2,458</td><td>B</td></tr>
<tr><td>Eibar</td><td>1 – 1</td><td>Logroño United</td><td>Ipurua</td><td>30 August 2026</td><td>17:00</td><td>271</td><td>C</td></tr>
</table>
<table class="wikitable">
<tr><th colspan="8">Game day 2</th></tr>
<tr><th>Home team</th><th>Results</th><th>Away team</th><th>Stadium</th><th>Date</th><th>Time</th><th>Attendance</th><th>Referee</th></tr>
<tr><td>Tenerife</td><td>2 – 1</td><td>Real Madrid</td><td>Heliodoro</td><td>5 September 2026</td><td>12:00</td><td>900</td><td>D</td></tr>
<tr><td>Barcelona</td><td></td><td>Eibar</td><td>Johan Cruyff</td><td>6 September 2026</td><td>12:00</td><td></td><td></td></tr>
<tr><td>Valencia</td><td>[ b ]</td><td>Alavés</td><td>Paterna</td><td></td><td></td><td></td><td></td></tr>
</table>
</body></html>
"""

HTML_CRUZADA = """
<html><body>
<table class="wikitable">
<tr><th>Home \\ Away</th><th>ATM</th><th>BAR</th><th>EIB</th><th>LOG</th><th>RMA</th><th>TEN</th></tr>
<tr><th scope="row"><a href="#">Atlético</a></th><td></td><td></td><td>1–0</td><td></td><td></td><td></td></tr>
<tr><th scope="row"><a href="#">Barcelona</a></th><td>4–2</td><td></td><td></td><td></td><td></td><td>5–0</td></tr>
<tr><th scope="row"><a href="#">Eibar</a></th><td></td><td></td><td></td><td>1–1</td><td></td><td></td></tr>
<tr><th scope="row"><a href="#">Logroño United</a></th><td></td><td>0–2</td><td></td><td></td><td></td><td></td></tr>
<tr><th scope="row"><a href="#">Real Madrid</a></th><td>3–2</td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><th scope="row"><a href="#">Tenerife</a></th><td></td><td></td><td></td><td></td><td>2–1</td><td></td></tr>
</table>
</body></html>
"""


class TestClaveYAlias(unittest.TestCase):
    def test_clave_quita_sufijo_acentos_y_palabras_vacias(self):
        self.assertEqual(liga_f.clave_liga_f("Alavés (F)"), "alaves")
        self.assertEqual(liga_f.clave_liga_f("Athletic Club (F)"), "athletic")
        self.assertEqual(liga_f.clave_liga_f("Logroño United"), "logrono")
        self.assertEqual(liga_f.clave_liga_f("Badalona Women"), "badalona")
        self.assertEqual(liga_f.clave_liga_f("Real Sociedad de Fútbol Femenino"), "real sociedad")
        self.assertEqual(liga_f.clave_liga_f("ATH.CLUB (F)"), "ath")
        self.assertEqual(liga_f.clave_liga_f(""), "")

    def test_alias_wikipedia_a_nombre_quiniela(self):
        casos = {
            "Logroño United": "Logroño (F)",
            "DUX Logroño": "Logroño (F)",
            "Costa Adeje Tenerife": "Tenerife (F)",
            "GRANADILLA (F)": "Tenerife (F)",
            "Deportivo Abanca": "Deportivo (F)",
            "Deportivo Alavés": "Alavés (F)",
            "Badalona Women": "Badalona (F)",
            "LAS PLANAS (F)": "Badalona (F)",
            "Atlético Madrid": "At. Madrid (F)",
            "Atlético de Madrid (F)": "At. Madrid (F)",
            "AT.MADRID (F)": "At. Madrid (F)",
            "R.MADRID (F)": "Real Madrid (F)",
            "Madrid CFF": "Madrid CFF (F)",
            "ATH.CLUB (F)": "Athletic Club (F)",
            "R. Sociedad (F)": "Real Sociedad (F)",
            "Sevilla FC": "Sevilla (F)",
            "Valencia": "Valencia (F)",
            "Barcelona (F)": "Barcelona (F)",
            "Espanyol (F)": "Espanyol (F)",
            "Granada CF": "Granada (F)",
            "Eibar": "Eibar (F)",
            "Levante UD": "Levante (F)",
        }
        for entrada, esperado in casos.items():
            with self.subTest(entrada=entrada):
                self.assertEqual(liga_f.nombre_canonico_liga_f(entrada), esperado)

    def test_los_18_canonicos_se_reconocen_a_si_mismos(self):
        for canonico in liga_f.CANONICOS_LIGA_F:
            self.assertEqual(liga_f.nombre_canonico_liga_f(canonico), canonico)

    def test_nombre_desconocido_conserva_sufijo(self):
        self.assertIsNone(liga_f.nombre_canonico_liga_f("Club Inventado"))
        self.assertEqual(liga_f.normalizar_equipo("Club Inventado"), "Club Inventado (F)")
        self.assertEqual(liga_f.normalizar_equipo("Club Inventado (F)"), "Club Inventado (F)")

    def test_real_madrid_y_madrid_cff_no_se_confunden(self):
        self.assertNotEqual(liga_f.nombre_canonico_liga_f("Madrid CFF"), liga_f.nombre_canonico_liga_f("Real Madrid"))
        self.assertNotEqual(liga_f.nombre_canonico_liga_f("Atlético Madrid"), liga_f.nombre_canonico_liga_f("Real Madrid"))


class TestParseoClasificacion(unittest.TestCase):
    def test_parsea_tabla_en_ingles(self):
        filas = liga_f.parsear_clasificacion(HTML_CLASIFICACION)
        self.assertEqual(len(filas), 10)
        barcelona = filas[0]
        self.assertEqual(barcelona["equipo"], "Barcelona (F)")
        self.assertEqual((barcelona["posicion"], barcelona["pj"], barcelona["g"], barcelona["e"], barcelona["p"]),
                         (1, 9, 8, 1, 0))
        self.assertEqual((barcelona["gf"], barcelona["gc"], barcelona["dg"], barcelona["pts"]), (35, 4, 31, 25))
        self.assertEqual(filas[3]["equipo"], "Logroño (F)")
        self.assertEqual(filas[3]["dg"], -1)
        self.assertEqual(filas[4]["equipo"], "Deportivo (F)")
        self.assertEqual(filas[6]["equipo"], "Badalona (F)")
        self.assertEqual(filas[-1]["equipo"], "Valencia (F)")
        self.assertEqual(filas[-1]["pts"], 4)

    def test_sin_tabla_devuelve_vacio(self):
        self.assertEqual(liga_f.parsear_clasificacion("<html><table><tr><th>a</th></tr></table></html>"), [])

    def test_estadisticas_derivadas(self):
        equipos = liga_f.calcular_estadisticas(liga_f.parsear_clasificacion(HTML_CLASIFICACION), [])
        barcelona = equipos[0]
        self.assertAlmostEqual(barcelona["ppg"], 25 / 9, places=3)
        self.assertAlmostEqual(barcelona["empates_pct"], 11.1, places=1)
        self.assertEqual(barcelona["puntos"], 25)
        self.assertEqual(barcelona["casa"], {"pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0})
        self.assertIsNone(barcelona["forma_5"])
        self.assertIn("Barcelona", barcelona["alias"])


class TestParseoResultados(unittest.TestCase):
    def test_tablas_por_jornada_con_rowspan_en_fecha(self):
        partidos = liga_f.parsear_resultados_jornadas(HTML_JORNADAS)
        self.assertEqual(len(partidos), 4)  # dos sin marcador se ignoran
        primero = partidos[0]
        self.assertEqual(primero["local"], "Real Madrid (F)")
        self.assertEqual(primero["visitante"], "At. Madrid (F)")
        self.assertEqual((primero["goles_local"], primero["goles_visitante"], primero["signo"]), (3, 2, "1"))
        self.assertEqual(primero["jornada"], 1)
        self.assertEqual(primero["fecha"], "2026-08-29")
        # la segunda fila hereda la fecha por rowspan
        self.assertEqual(partidos[1]["fecha"], "2026-08-29")
        self.assertEqual(partidos[1]["local"], "Barcelona (F)")
        self.assertEqual(partidos[2]["fecha"], "2026-08-30")
        self.assertEqual(partidos[2]["signo"], "X")
        self.assertEqual(partidos[3]["jornada"], 2)
        self.assertEqual(partidos[3]["signo"], "1")

    def test_tabla_cruzada(self):
        partidos = liga_f.parsear_resultados_cruzados(HTML_CRUZADA)
        self.assertEqual(len(partidos), 7)
        indice = {(p["local"], p["visitante"]): (p["goles_local"], p["goles_visitante"]) for p in partidos}
        self.assertEqual(indice[("Barcelona (F)", "At. Madrid (F)")], (4, 2))
        self.assertEqual(indice[("Barcelona (F)", "Tenerife (F)")], (5, 0))
        self.assertEqual(indice[("Logroño (F)", "Barcelona (F)")], (0, 2))
        self.assertEqual(indice[("Tenerife (F)", "Real Madrid (F)")], (2, 1))
        self.assertEqual(indice[("Eibar (F)", "Logroño (F)")], (1, 1))
        self.assertTrue(all(p["fecha"] is None and p["fuente"] == "cruzada" for p in partidos))

    def test_cruzada_sin_abreviaturas_conocidas_usa_el_orden(self):
        html = HTML_CRUZADA.replace("ATM", "A1").replace("BAR", "B1").replace("EIB", "E1") \
            .replace("LOG", "L1").replace("RMA", "R1").replace("TEN", "T1")
        partidos = liga_f.parsear_resultados_cruzados(html)
        indice = {(p["local"], p["visitante"]): (p["goles_local"], p["goles_visitante"]) for p in partidos}
        self.assertEqual(indice[("Real Madrid (F)", "At. Madrid (F)")], (3, 2))

    def test_union_prefiere_jornadas_y_completa_con_cruzada(self):
        html = HTML_JORNADAS.replace("</body></html>", "") + HTML_CRUZADA.replace("<html><body>", "")
        partidos = liga_f.parsear_resultados(html)
        fuentes = {(p["local"], p["visitante"]): p["fuente"] for p in partidos}
        self.assertEqual(fuentes[("Real Madrid (F)", "At. Madrid (F)")], "jornadas")
        self.assertEqual(fuentes[("Barcelona (F)", "At. Madrid (F)")], "cruzada")
        self.assertEqual(len(partidos), 7)  # 4 de jornadas + 3 que solo estan en la cruzada

    def test_casa_fuera_y_forma(self):
        clasificacion = liga_f.parsear_clasificacion(HTML_CLASIFICACION)
        partidos = liga_f.parsear_resultados_jornadas(HTML_JORNADAS)
        equipos = {e["equipo"]: e for e in liga_f.calcular_estadisticas(clasificacion, partidos)}
        rm = equipos["Real Madrid (F)"]
        self.assertEqual(rm["casa"], {"pj": 1, "g": 1, "e": 0, "p": 0, "gf": 3, "gc": 2})
        self.assertEqual(rm["fuera"], {"pj": 1, "g": 0, "e": 0, "p": 1, "gf": 1, "gc": 2})
        self.assertEqual(rm["forma_5"], "VD")
        self.assertEqual(rm["forma_5_puntos"], 3)
        self.assertEqual(equipos["Eibar (F)"]["forma_5"], "E")
        self.assertEqual(equipos["Tenerife (F)"]["forma_5"], "DV")

    def test_forma_omitida_si_no_hay_orden_fiable(self):
        clasificacion = liga_f.parsear_clasificacion(HTML_CLASIFICACION)
        partidos = liga_f.parsear_resultados_cruzados(HTML_CRUZADA)
        equipos = {e["equipo"]: e for e in liga_f.calcular_estadisticas(clasificacion, partidos)}
        self.assertIsNone(equipos["Barcelona (F)"]["forma_5"])
        self.assertEqual(equipos["Barcelona (F)"]["casa"]["pj"], 2)


class TestEscrituraYConservacion(unittest.TestCase):
    def test_escribe_estructura_esperada(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp)
            clasificacion = liga_f.parsear_clasificacion(HTML_CLASIFICACION)
            partidos = liga_f.parsear_resultados_jornadas(HTML_JORNADAS)
            equipos = liga_f.calcular_estadisticas(clasificacion, partidos)
            liga_f.escribir_salidas(equipos, partidos, "http://fuente", ["aviso x"], dir_salida=destino)
            datos = json.loads((destino / "clasificacion.json").read_text(encoding="utf-8"))
            self.assertEqual(datos["version"], 1)
            self.assertEqual(datos["temporada"], "2026/2027")
            self.assertEqual(datos["fuente"], "http://fuente")
            self.assertEqual(datos["avisos"], ["aviso x"])
            self.assertEqual(datos["jornadas_jugadas"], 2)
            self.assertTrue(datos["actualizado_en"])
            self.assertEqual(len(datos["equipos"]), 10)
            self.assertEqual(datos["equipos"][0]["equipo"], "Barcelona (F)")
            resultados = json.loads((destino / "resultados.json").read_text(encoding="utf-8"))
            self.assertEqual(resultados["total"], 4)
            self.assertEqual(resultados["partidos"][0]["local"], "Real Madrid (F)")

    def test_descarga_fallida_conserva_ficheros_previos(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp)
            previo = {"version": 1, "temporada": "2026/2027", "fuente": "http://antes", "actualizado_en": "2026-11-01T00:00:00+00:00",
                      "avisos": [], "equipos": [{"equipo": "Barcelona (F)", "puntos": 25}]}
            previo_res = {"version": 1, "temporada": "2026/2027", "fuente": "http://antes", "actualizado_en": "2026-11-01T00:00:00+00:00",
                          "avisos": [], "total": 1, "partidos": [{"local": "Barcelona (F)", "visitante": "Tenerife (F)"}]}
            (destino / "clasificacion.json").write_text(json.dumps(previo), encoding="utf-8")
            (destino / "resultados.json").write_text(json.dumps(previo_res), encoding="utf-8")

            with mock.patch.object(liga_f, "motivo_para_no_descargar", return_value=None), \
                 mock.patch.object(liga_f, "descargar", side_effect=liga_f.requests.ConnectionError("sin red")), \
                 mock.patch.object(liga_f, "conservar_previo_con_aviso",
                                   side_effect=lambda aviso, dir_salida=None: _conservar(aviso, destino)):
                codigo = liga_f.main([])
            self.assertEqual(codigo, 1)
            datos = json.loads((destino / "clasificacion.json").read_text(encoding="utf-8"))
            self.assertEqual(datos["equipos"], [{"equipo": "Barcelona (F)", "puntos": 25}])
            self.assertEqual(datos["fuente"], "http://antes")
            self.assertEqual(datos["actualizado_en"], "2026-11-01T00:00:00+00:00")
            self.assertEqual(len(datos["avisos"]), 1)
            self.assertIn("Descarga fallida", datos["avisos"][0])
            self.assertIn("sin red", datos["avisos"][0])
            resultados = json.loads((destino / "resultados.json").read_text(encoding="utf-8"))
            self.assertEqual(resultados["partidos"], [{"local": "Barcelona (F)", "visitante": "Tenerife (F)"}])
            self.assertIn("Descarga fallida", resultados["avisos"][0])

    def test_aviso_de_fallo_no_se_acumula(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp)
            liga_f.conservar_previo_con_aviso("error 1", dir_salida=destino)
            liga_f.conservar_previo_con_aviso("error 2", dir_salida=destino)
            datos = json.loads((destino / "clasificacion.json").read_text(encoding="utf-8"))
            self.assertEqual(len(datos["avisos"]), 1)
            self.assertIn("error 2", datos["avisos"][0])
            self.assertEqual(datos["equipos"], [])

    def test_clasificacion_incompleta_cuenta_como_fallo(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp)
            with mock.patch.object(liga_f, "motivo_para_no_descargar", return_value=None), \
                 mock.patch.object(liga_f, "descargar", return_value="<html><p>vacio</p></html>"), \
                 mock.patch.object(liga_f, "conservar_previo_con_aviso",
                                   side_effect=lambda aviso, dir_salida=None: _conservar(aviso, destino)):
                codigo = liga_f.main([])
            self.assertEqual(codigo, 1)
            datos = json.loads((destino / "clasificacion.json").read_text(encoding="utf-8"))
            self.assertIn("clasificacion incompleta", datos["avisos"][0])


_conservar_original = liga_f.conservar_previo_con_aviso


def _conservar(aviso, destino):
    return _conservar_original(aviso, dir_salida=destino)


if __name__ == "__main__":
    unittest.main()
