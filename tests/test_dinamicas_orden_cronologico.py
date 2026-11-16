import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import recalcular_dinamicas_calendario as din


class HistorialOrdenCronologicoTests(unittest.TestCase):
    """Caso real (auditoria 16/11/2026): el Levante-Athletic de la J5 se jugo el
    21/10 (aplazado), despues de la J9. Ordenando por numero de jornada la
    derrota quedaba al principio y el Athletic salia con 6 sin perder cuando
    llevaba 3. La racha se ordena por fecha real."""

    def test_el_aplazado_se_ordena_por_su_fecha_real(self):
        calendario = {"jornadas": [
            {"jornada": 5, "partidos": [
                {"local": "Levante UD", "visitante": "Athletic Club", "fecha": "2026-10-21", "resultado": "3-1", "estado": "Jugado"}]},
            {"jornada": 8, "partidos": [
                {"local": "Valencia CF", "visitante": "Athletic Club", "fecha": "2026-10-18", "resultado": "0-0", "estado": "Jugado"}]},
            {"jornada": 10, "partidos": [
                {"local": "Athletic Club", "visitante": "Getafe CF", "fecha": "2026-10-25", "resultado": "4-0", "estado": "Jugado"}]},
            {"jornada": 9, "partidos": [
                {"local": "Rayo Vallecano de Madrid", "visitante": "Athletic Club", "fecha": "2026-10-11", "resultado": "", "estado": "Suspendido"}]},
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "cal.json"
            ruta.write_text(json.dumps(calendario), encoding="utf-8")
            original = din.CALENDARIOS["primera"]
            din.CALENDARIOS["primera"] = ruta
            try:
                tabla = [{"equipo": "Athletic Club"}, {"equipo": "Levante UD"}, {"equipo": "Valencia CF"},
                         {"equipo": "Getafe CF"}, {"equipo": "Rayo Vallecano de Madrid"}]
                historial = din.historial_liga("primera", tabla)
            finally:
                din.CALENDARIOS["primera"] = original
        athletic = historial[din.clave_equipo("Athletic Club")]
        self.assertEqual([x["fecha"] for x in athletic], ["2026-10-18", "2026-10-21", "2026-10-25"])
        self.assertEqual([x["pts"] for x in athletic], [1, 0, 3])
        # el suspendido (sin resultado) no cuenta
        self.assertEqual(len(athletic), 3)




class ClasificacionFootballDataOrdenCronologicoTests(unittest.TestCase):
    def test_la_racha_sigue_la_fecha_real_no_el_numero_de_jornada(self):
        import actualizar_ligas_football_data as fd
        calendario = {"jornadas": [
            {"jornada": 5, "partidos": [
                {"local": "Levante UD", "visitante": "Athletic Club", "fecha": "2026-10-21", "resultado": "3-1", "estado": "Jugado"}]},
            {"jornada": 8, "partidos": [
                {"local": "Valencia CF", "visitante": "Athletic Club", "fecha": "2026-10-18", "resultado": "0-0", "estado": "Jugado"}]},
            {"jornada": 10, "partidos": [
                {"local": "Athletic Club", "visitante": "Getafe CF", "fecha": "2026-10-25", "resultado": "4-0", "estado": "Jugado"}]},
        ]}
        equipos, jugados = fd.construir_clasificacion(calendario)
        athletic = next(e for e in equipos if e["equipo"] == "Athletic Club")
        self.assertEqual(jugados, 3)
        # orden real: X (18/10), P (21/10), G (25/10) -> 1 sin perder, 1 victoria seguida
        self.assertEqual(athletic["racha_actual"]["sin_perder"], 1)
        self.assertEqual(athletic["racha_actual"]["victorias"], 1)
        self.assertEqual(athletic["racha_actual"]["derrotas"], 0)


if __name__ == "__main__":
    unittest.main()
