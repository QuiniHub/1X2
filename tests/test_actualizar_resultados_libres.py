import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_resultados_libres as arl


def evento(local, visitante, hg=None, ag=None, status="Match Finished", fecha="2026-08-16"):
    return {
        "strHomeTeam": local,
        "strAwayTeam": visitante,
        "intHomeScore": hg,
        "intAwayScore": ag,
        "strStatus": status,
        "dateEvent": fecha,
    }


def respuesta_ok(payload):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = payload
    return resp


class ParsearEventosThesportsdbTests(unittest.TestCase):
    def test_partido_terminado_calcula_resultado_y_ganador(self):
        eventos = [evento("Real Sociedad B", "Castellon", 0, 1)]
        salida = arl._parsear_eventos_thesportsdb("Segunda División", eventos)
        self.assertEqual(salida[0]["resultado"], "0-1")
        self.assertEqual(salida[0]["ganador"], "Castellon")

    def test_partido_sin_jugar_no_tiene_resultado(self):
        eventos = [evento("Elche", "Deportivo", None, None, status="Not Started")]
        salida = arl._parsear_eventos_thesportsdb("La Liga", eventos)
        self.assertIsNone(salida[0]["resultado"])
        self.assertIsNone(salida[0]["ganador"])

    def test_empate_no_tiene_ganador(self):
        eventos = [evento("Cadiz", "Celta Fortuna", 0, 0)]
        salida = arl._parsear_eventos_thesportsdb("Segunda División", eventos)
        self.assertEqual(salida[0]["resultado"], "0-0")
        self.assertIsNone(salida[0]["ganador"])


class ObtenerThesportsdbPorRondasTests(unittest.TestCase):
    """Bug real (17/08/2026): eventspastleague.php solo da el ULTIMO
    partido de la liga -el calendario oficial necesita la jornada
    completa (ej. Real Sociedad B 0-1 Castellon, que la Quiniela no
    habia elegido esa semana y por tanto no aparecia en ningun sitio).
    eventsround.php si trae la jornada entera, pero exige recorrer
    varias rondas y el id de Segunda en THESPORTSDB_LIGAS estaba mal
    (4336 es una liga griega, el correcto es 4400)."""

    def test_segunda_usa_el_id_correcto_no_el_de_la_liga_griega(self):
        self.assertEqual(arl.THESPORTSDB_LIGAS["Segunda División"], "4400")

    def test_pide_una_ronda_por_cada_numero_configurado(self):
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.return_value = respuesta_ok({"events": [evento("A", "B", 1, 0)]})
            resultados = arl.obtener_thesportsdb_por_rondas("La Liga", "4335", (1, 2))
        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(len(resultados), 2)

    def test_combina_los_partidos_de_todas_las_rondas_pedidas(self):
        respuestas = [
            respuesta_ok({"events": [evento("Real Sociedad B", "Castellon", 0, 1)]}),
            respuesta_ok({"events": [evento("Real Oviedo", "Granada", 0, 0)]}),
        ]
        with patch("actualizar_resultados_libres.requests.get", side_effect=respuestas):
            resultados = arl.obtener_thesportsdb_por_rondas("Segunda División", "4400", (1, 2))
        equipos = {(r["local"], r["visitante"]) for r in resultados}
        self.assertIn(("Real Sociedad B", "Castellon"), equipos)
        self.assertIn(("Real Oviedo", "Granada"), equipos)

    def test_error_de_red_en_una_ronda_no_rompe_las_demas(self):
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.side_effect = [
                Exception("timeout"),
                respuesta_ok({"events": [evento("A", "B", 2, 1)]}),
            ]
            resultados = arl.obtener_thesportsdb_por_rondas("La Liga", "4335", (1, 2))
        self.assertEqual(len(resultados), 1)


class ParesEsperadosCalendarioTests(unittest.TestCase):
    """pares_esperados_calendario() lee de calendario_primera.json/segunda.json
    ya sembrados (ver actualizar_ligas_football_data.py) para saber que
    partidos DEBERIAN existir en cada ronda -sin esto, obtener_thesportsdb_
    backfill() no tendria forma de saber que le falta algo a eventsround.php."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self._orig = dict(arl.CALENDARIO_SEMBRADO)
        arl.CALENDARIO_SEMBRADO = {"La Liga": base / "calendario_primera.json"}
        (base / "calendario_primera.json").write_text(json.dumps({
            "jornadas": [
                {"jornada": 1, "partidos": [
                    {"local": "Deportivo Alaves", "visitante": "Getafe CF"},
                    {"local": "Club Atletico de Madrid", "visitante": "Malaga CF"},
                ]},
                {"jornada": 2, "partidos": [
                    {"local": "Athletic Club", "visitante": "Sevilla FC"},
                ]},
            ]
        }), encoding="utf-8")

    def tearDown(self):
        arl.CALENDARIO_SEMBRADO = self._orig
        self._tmp.cleanup()

    def test_devuelve_los_pares_de_las_rondas_pedidas(self):
        pares = arl.pares_esperados_calendario("La Liga", (1,))
        self.assertEqual(pares, [("Deportivo Alaves", "Getafe CF"), ("Club Atletico de Madrid", "Malaga CF")])

    def test_combina_varias_rondas(self):
        pares = arl.pares_esperados_calendario("La Liga", (1, 2))
        self.assertEqual(len(pares), 3)

    def test_liga_sin_calendario_sembrado_devuelve_vacio(self):
        self.assertEqual(arl.pares_esperados_calendario("Segunda División", (1,)), [])


class ObtenerThesportsdbBackfillTests(unittest.TestCase):
    """Bug real (22/08/2026): 6 de los 11 partidos de la Jornada 1 de
    Segunda faltaban en eventsround.php sin haberse aplazado nunca -el
    mismo problema que ya se vio con Atletico-Malaga (19/08) pero sin
    ningun aplazamiento real detras, asi que la lista fija de "aplazados
    conocidos" del fix anterior no lo cubria. obtener_thesportsdb_backfill()
    generaliza eso: compara contra el calendario oficial ya sembrado y solo
    pregunta por lo que eventsround.php no trajo en absoluto."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self._orig = dict(arl.CALENDARIO_SEMBRADO)
        arl.CALENDARIO_SEMBRADO = {"La Liga": base / "calendario_primera.json"}
        (base / "calendario_primera.json").write_text(json.dumps({
            "jornadas": [{"jornada": 1, "partidos": [
                {"local": "Deportivo Alaves", "visitante": "Getafe CF"},
                {"local": "Club Atletico de Madrid", "visitante": "Malaga CF"},
            ]}]
        }), encoding="utf-8")

    def tearDown(self):
        arl.CALENDARIO_SEMBRADO = self._orig
        self._tmp.cleanup()

    def test_solo_busca_los_pares_que_eventsround_no_trajo(self):
        ya_obtenidos = [{"local": "Deportivo Alaves", "visitante": "Getafe CF", "resultado": "3-0"}]
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.return_value = respuesta_ok({"event": [evento("Atletico Madrid", "Malaga", 2, 0)]})
            resultados = arl.obtener_thesportsdb_backfill("La Liga", (1,), ya_obtenidos)
        mock_get.assert_called_once()
        self.assertEqual(resultados[0]["resultado"], "2-0")

    def test_no_repite_llamada_para_un_partido_que_eventsround_ya_trajo_aunque_este_pendiente(self):
        # Si eventsround.php SI menciono el partido (aunque siga sin
        # resultado, un partido futuro de verdad), no hace falta gastar
        # una llamada extra en buscarlo -solo se rellenan huecos reales.
        ya_obtenidos = [
            {"local": "Deportivo Alaves", "visitante": "Getafe CF", "resultado": "3-0"},
            {"local": "Club Atletico de Madrid", "visitante": "Malaga CF", "resultado": None},
        ]
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            resultados = arl.obtener_thesportsdb_backfill("La Liga", (1,), ya_obtenidos)
        mock_get.assert_not_called()
        self.assertEqual(resultados, [])

    def test_par_sin_evento_encontrado_no_rompe_los_demas(self):
        arl.CALENDARIO_SEMBRADO["La Liga"].write_text(json.dumps({
            "jornadas": [{"jornada": 1, "partidos": [
                {"local": "X", "visitante": "Y"},
                {"local": "A", "visitante": "B"},
            ]}]
        }), encoding="utf-8")
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.side_effect = [
                respuesta_ok({"event": None}),
                respuesta_ok({"event": [evento("A", "B", 1, 0)]}),
            ]
            resultados = arl.obtener_thesportsdb_backfill("La Liga", (1,), [])
        self.assertEqual(len(resultados), 1)

    def test_error_de_red_en_un_par_no_rompe_los_demas(self):
        arl.CALENDARIO_SEMBRADO["La Liga"].write_text(json.dumps({
            "jornadas": [{"jornada": 1, "partidos": [
                {"local": "X", "visitante": "Y"},
                {"local": "A", "visitante": "B"},
            ]}]
        }), encoding="utf-8")
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.side_effect = [Exception("timeout"), respuesta_ok({"event": [evento("A", "B", 1, 0)]})]
            resultados = arl.obtener_thesportsdb_backfill("La Liga", (1,), [])
        self.assertEqual(len(resultados), 1)


if __name__ == "__main__":
    unittest.main()
