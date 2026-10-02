import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generar_artefactos_compuerta_aprendizaje import construir_bloque_rps_calibracion, rps_partido


class RpsPartidoTests(unittest.TestCase):
    def test_prediccion_perfecta_da_cero(self):
        self.assertAlmostEqual(rps_partido({"1": 100, "X": 0, "2": 0}, "1"), 0.0)

    def test_fallo_cercano_castiga_menos_que_fallo_lejano(self):
        # decir "1" y que salga X debe doler menos que decir "1" y que salga 2
        probs = {"1": 70, "X": 20, "2": 10}
        self.assertLess(rps_partido(probs, "X"), rps_partido(probs, "2"))

    def test_normaliza_probabilidades_que_no_suman_100(self):
        a = rps_partido({"1": 50, "X": 30, "2": 20}, "1")
        b = rps_partido({"1": 5, "X": 3, "2": 2}, "1")
        self.assertAlmostEqual(a, b, places=9)

    def test_datos_invalidos_devuelven_none(self):
        self.assertIsNone(rps_partido({}, "1"))
        self.assertIsNone(rps_partido({"1": 50, "X": 30, "2": 20}, "M"))
        self.assertIsNone(rps_partido({"1": 0, "X": 0, "2": 0}, "X"))


class BloqueCalibracionTests(unittest.TestCase):
    def _item(self, jornada, probs, real):
        return {"jornada": jornada, "probabilidades_usadas": probs, "signo_real": real}

    def test_bloque_completo_con_items_reales(self):
        items = [
            self._item(1, {"1": 60, "X": 25, "2": 15}, "1"),
            self._item(1, {"1": 20, "X": 30, "2": 50}, "2"),
            self._item(2, {"1": 45, "X": 35, "2": 20}, "X"),
            {"jornada": 2, "probabilidades_usadas": {}, "signo_real": "1"},  # sin probs
        ]
        bloque = construir_bloque_rps_calibracion(items)
        self.assertEqual(bloque["partidos_con_probabilidades"], 3)
        self.assertEqual(bloque["sin_probabilidades"], 1)
        self.assertIn("1", bloque["rps_por_jornadas"] if "rps_por_jornadas" in bloque else bloque["rps_por_jornada"])
        # calibracion: el 1 sale 1 de 3 veces (33.3%) y se pronostico de media (60+20+45)/3
        cal1 = bloque["calibracion_por_signo"]["1"]
        self.assertAlmostEqual(cal1["prob_media_pronosticada"], (60 + 20 + 45) / 3, places=1)
        self.assertAlmostEqual(cal1["frecuencia_real_pct"], 33.3, places=1)
        # favorito: 60 (acierta), 50 (acierta), 45 (falla, salio X? no: favorito=1 con 45, salio X -> falla)
        bandas = bloque["calibracion_favorito"]
        self.assertEqual(sum(v["n"] for v in bandas.values()), 3)

    def test_sin_items_no_explota(self):
        bloque = construir_bloque_rps_calibracion([])
        self.assertEqual(bloque["partidos_con_probabilidades"], 0)


if __name__ == "__main__":
    unittest.main()
