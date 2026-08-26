import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_ligas_football_data as alfd


class CanonicoTests(unittest.TestCase):
    """Bug real (21/08/2026): varios codigos de equipo que usa football-data.co.uk
    en su CSV no resolvian a ningun nombre canonico (ni por alias exacto ni por
    el fallback de substring), asi que sus resultados nunca se emparejaban con
    el calendario -sin importar si el calendario tenia el partido o no."""

    def test_atl_madrid_resuelve_a_atletico(self):
        self.assertEqual(alfd.canonico("Atl. Madrid"), "Club Atletico de Madrid")

    def test_dep_a_coruna_resuelve_a_deportivo(self):
        self.assertEqual(alfd.canonico("Dep. A Coruna"), "RC Deportivo de La Coruna")

    def test_eldense_sabadell_tenerife_resuelven_con_prefijo_oficial(self):
        self.assertEqual(alfd.canonico("Eldense"), "CD Eldense")
        self.assertEqual(alfd.canonico("Sabadell"), "CE Sabadell")
        self.assertEqual(alfd.canonico("Tenerife"), "CD Tenerife")

    def test_celta_de_vigo_en_segunda_es_el_filial_no_el_primer_equipo(self):
        # football-data.co.uk usa el nombre largo del primer equipo para el
        # filial recien ascendido (Celta Fortuna) en su CSV de Segunda -sin
        # el contexto de liga, "RC Celta de Vigo" apuntaria mal al primer
        # equipo (que juega en Primera, no en Segunda).
        self.assertEqual(alfd.canonico("RC Celta de Vigo", "segunda"), "RC Celta Fortuna")

    def test_celta_de_vigo_en_primera_sigue_siendo_el_primer_equipo(self):
        self.assertEqual(alfd.canonico("RC Celta de Vigo", "primera"), "RC Celta de Vigo")
        self.assertEqual(alfd.canonico("RC Celta de Vigo"), "RC Celta de Vigo")


class CodigoTemporadaDesdeUrlTests(unittest.TestCase):
    def test_extrae_el_codigo_de_una_url_football_data(self):
        url = "https://www.football-data.co.uk/mmz4281/2526/SP1.csv"
        self.assertEqual(alfd.codigo_temporada_desde_url(url), "2526")

    def test_devuelve_none_si_no_hay_codigo(self):
        self.assertIsNone(alfd.codigo_temporada_desde_url("https://example.com/otra-cosa.csv"))
        self.assertIsNone(alfd.codigo_temporada_desde_url(None))


class EsRetrocesoDeTemporadaTests(unittest.TestCase):
    def test_no_pisa_el_roster_2026_2027_con_fallback_a_temporada_anterior(self):
        data = {"temporada_detectada": "2026/2027"}
        fuentes = {"primera": {"url": "https://www.football-data.co.uk/mmz4281/2526/SP1.csv"}}
        self.assertTrue(alfd.es_retroceso_de_temporada(data, "primera", fuentes))

    def test_permite_escribir_si_football_data_ya_tiene_2627(self):
        data = {"temporada_detectada": "2026/2027"}
        fuentes = {"primera": {"url": "https://www.football-data.co.uk/mmz4281/2627/SP1.csv"}}
        self.assertFalse(alfd.es_retroceso_de_temporada(data, "primera", fuentes))

    def test_permite_escribir_si_todavia_no_se_ha_detectado_2026_2027(self):
        data = {"temporada_detectada": "2025/2026"}
        fuentes = {"primera": {"url": "https://www.football-data.co.uk/mmz4281/2526/SP1.csv"}}
        self.assertFalse(alfd.es_retroceso_de_temporada(data, "primera", fuentes))


class SembrarJornadasDesdeOficialTests(unittest.TestCase):
    """Bug real (21/08/2026): calendario_primera.json/segunda.json se quedaban
    con la lista de equipos pero CERO partidos dentro de cada jornada -sin
    ningun partido "hueco" contra el que emparejar los resultados del CSV de
    football-data.co.uk, actualizar_calendario() los descartaba todos en
    silencio como "sin emparejar". Consecuencia real: forma reciente y
    rendimiento casa/fuera se quedaban a 0 para los 42 equipos toda la
    temporada, aunque los partidos ya estuvieran jugados."""

    def _con_directorio_temporal(self, prueba):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            original_ligas = alfd.LIGAS
            try:
                alfd.LIGAS = {
                    "primera": dict(
                        original_ligas["primera"],
                        calendario=tmp / "calendario_primera.json",
                        calendario_oficial=tmp / "calendario_1a_2627.json",
                    ),
                }
                prueba(tmp)
            finally:
                alfd.LIGAS = original_ligas

    def test_siembra_partidos_desde_calendario_oficial_vacio_al_principio(self):
        def prueba(tmp):
            (tmp / "calendario_1a_2627.json").write_text(json.dumps({
                "jornadas": [
                    {"num": 1, "fecha": "2026-08-16", "partidos": [
                        {"local": "Alavés", "visitante": "Getafe"},
                        {"local": "Atlético de Madrid", "visitante": "Málaga CF"},
                    ]},
                ]
            }, ensure_ascii=False), encoding="utf-8")
            (tmp / "calendario_primera.json").write_text(json.dumps({
                "competicion": "primera",
                "jornadas": [{"jornada": 1, "partidos": [], "estado": "pendiente_calendario_oficial"}],
            }, ensure_ascii=False), encoding="utf-8")

            cambios = alfd.sembrar_jornadas_desde_oficial("primera")
            self.assertEqual(cambios, 2)

            calendario = json.loads((tmp / "calendario_primera.json").read_text(encoding="utf-8"))
            jornada1 = calendario["jornadas"][0]
            self.assertNotIn("estado", jornada1)
            nombres = {(p["local"], p["visitante"]) for p in jornada1["partidos"]}
            self.assertIn(("Deportivo Alaves", "Getafe CF"), nombres)
            self.assertIn(("Club Atletico de Madrid", "Malaga CF"), nombres)

        self._con_directorio_temporal(prueba)

    def test_no_duplica_partidos_ya_sembrados(self):
        def prueba(tmp):
            (tmp / "calendario_1a_2627.json").write_text(json.dumps({
                "jornadas": [{"num": 1, "fecha": "2026-08-16", "partidos": [
                    {"local": "Alavés", "visitante": "Getafe"},
                ]}]
            }, ensure_ascii=False), encoding="utf-8")
            (tmp / "calendario_primera.json").write_text(json.dumps({
                "competicion": "primera", "jornadas": [{"jornada": 1, "partidos": []}],
            }, ensure_ascii=False), encoding="utf-8")

            alfd.sembrar_jornadas_desde_oficial("primera")
            segunda_pasada = alfd.sembrar_jornadas_desde_oficial("primera")
            self.assertEqual(segunda_pasada, 0)

            calendario = json.loads((tmp / "calendario_primera.json").read_text(encoding="utf-8"))
            self.assertEqual(len(calendario["jornadas"][0]["partidos"]), 1)

        self._con_directorio_temporal(prueba)

    def test_no_pisa_un_resultado_ya_guardado(self):
        def prueba(tmp):
            (tmp / "calendario_1a_2627.json").write_text(json.dumps({
                "jornadas": [{"num": 1, "fecha": "2026-08-16", "partidos": [
                    {"local": "Alavés", "visitante": "Getafe"},
                ]}]
            }, ensure_ascii=False), encoding="utf-8")
            (tmp / "calendario_primera.json").write_text(json.dumps({
                "competicion": "primera",
                "jornadas": [{"jornada": 1, "partidos": [
                    {"local": "Deportivo Alaves", "visitante": "Getafe CF", "resultado": "3-0", "estado": "Jugado"},
                ]}],
            }, ensure_ascii=False), encoding="utf-8")

            cambios = alfd.sembrar_jornadas_desde_oficial("primera")
            self.assertEqual(cambios, 0)

            calendario = json.loads((tmp / "calendario_primera.json").read_text(encoding="utf-8"))
            self.assertEqual(calendario["jornadas"][0]["partidos"][0]["resultado"], "3-0")

        self._con_directorio_temporal(prueba)

    def test_permite_que_actualizar_calendario_encuentre_el_resultado_despues(self):
        # El caso real que motivo el fix: sin sembrar, un resultado real del
        # CSV se quedaba en "sin_emparejar" para siempre.
        def prueba(tmp):
            (tmp / "calendario_1a_2627.json").write_text(json.dumps({
                "jornadas": [{"num": 1, "fecha": "2026-08-16", "partidos": [
                    {"local": "Atlético de Madrid", "visitante": "Málaga CF"},
                ]}]
            }, ensure_ascii=False), encoding="utf-8")
            (tmp / "calendario_primera.json").write_text(json.dumps({
                "competicion": "primera", "jornadas": [{"jornada": 1, "partidos": []}],
            }, ensure_ascii=False), encoding="utf-8")

            alfd.sembrar_jornadas_desde_oficial("primera")
            _, cambios, sin_emparejar, ignorados_fecha_futura = alfd.actualizar_calendario("primera", [{
                "local": "Club Atletico de Madrid", "visitante": "Malaga CF",
                "resultado": "2-0", "fecha": "2026-08-19",
            }])
            self.assertEqual(cambios, 1)
            self.assertEqual(sin_emparejar, [])
            self.assertEqual(ignorados_fecha_futura, [])

        self._con_directorio_temporal(prueba)

    def test_no_marca_jugado_un_partido_con_fecha_futura(self):
        # Bug real (25/08/2026): "Sevilla FC - Club Atletico de Madrid"
        # (Jornada 3, fecha 2026-08-30) quedo marcado "Jugado" con marcador
        # 2-1 CINCO DIAS antes de jugarse -football-data.co.uk trajo (de
        # forma transitoria) un resultado con la fecha del partido todavia
        # sin llegar, y actualizar_calendario() lo escribio sin comprobar la
        # fecha contra "hoy". Usa un año muy lejano para que el test no
        # dependa de cuando se ejecute de verdad.
        def prueba(tmp):
            (tmp / "calendario_primera.json").write_text(json.dumps({
                "competicion": "primera", "jornadas": [{"jornada": 3, "partidos": [
                    {"local": "Sevilla FC", "visitante": "Club Atletico de Madrid",
                     "fecha": "2099-08-30", "resultado": "", "estado": "Pendiente"},
                ]}]
            }, ensure_ascii=False), encoding="utf-8")

            calendario, cambios, sin_emparejar, ignorados_fecha_futura = alfd.actualizar_calendario("primera", [{
                "local": "Sevilla FC", "visitante": "Club Atletico de Madrid",
                "resultado": "2-1", "fecha": "2099-08-30",
            }])
            self.assertEqual(cambios, 0)
            self.assertEqual(len(ignorados_fecha_futura), 1)
            partido = calendario["jornadas"][0]["partidos"][0]
            self.assertEqual(partido["estado"], "Pendiente")
            self.assertEqual(partido["resultado"], "")

        self._con_directorio_temporal(prueba)


if __name__ == "__main__":
    unittest.main()
