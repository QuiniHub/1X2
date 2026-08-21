import sys
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


class ObtenerThesportsdbAplazadosTests(unittest.TestCase):
    """Bug real (19/08/2026): Atletico Madrid-Malaga (aplazado de la J1 por
    el Mundial 2026, jugado en fecha suelta) tenia resultado real 2-0 en
    TheSportsDB, pero eventsround.php?r=1 no lo devolvia -el calendario
    oficial se quedaba mostrando "vs" sin marcador para siempre en un
    partido ya jugado y cerrado. searchevents.php si lo encuentra buscando
    directamente por el par de equipos."""

    def test_busca_cada_par_de_equipos_por_separado(self):
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.return_value = respuesta_ok({"event": [evento("Atletico Madrid", "Malaga", 2, 0)]})
            resultados = arl.obtener_thesportsdb_aplazados("La Liga", [("Atletico Madrid", "Malaga")])
        mock_get.assert_called_once()
        self.assertEqual(resultados[0]["resultado"], "2-0")
        self.assertEqual(resultados[0]["ganador"], "Club Atletico de Madrid")

    def test_consulta_todos_los_pares_configurados(self):
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.return_value = respuesta_ok({"event": [evento("A", "B", 1, 0)]})
            resultados = arl.obtener_thesportsdb_aplazados("La Liga", arl.APLAZADOS_JORNADA1_PRIMERA)
        self.assertEqual(mock_get.call_count, len(arl.APLAZADOS_JORNADA1_PRIMERA))
        self.assertEqual(len(resultados), len(arl.APLAZADOS_JORNADA1_PRIMERA))

    def test_par_sin_evento_encontrado_no_rompe_los_demas(self):
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.side_effect = [
                respuesta_ok({"event": None}),
                respuesta_ok({"event": [evento("A", "B", 1, 0)]}),
            ]
            resultados = arl.obtener_thesportsdb_aplazados("La Liga", [("X", "Y"), ("A", "B")])
        self.assertEqual(len(resultados), 1)

    def test_error_de_red_en_un_par_no_rompe_los_demas(self):
        with patch("actualizar_resultados_libres.requests.get") as mock_get:
            mock_get.side_effect = [Exception("timeout"), respuesta_ok({"event": [evento("A", "B", 1, 0)]})]
            resultados = arl.obtener_thesportsdb_aplazados("La Liga", [("X", "Y"), ("A", "B")])
        self.assertEqual(len(resultados), 1)


if __name__ == "__main__":
    unittest.main()
