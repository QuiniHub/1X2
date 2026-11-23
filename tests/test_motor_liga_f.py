import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import motor_prediccion_quiniela as motor


def equipo(nombre, pj, puntos, casa, fuera, forma):
    return {"equipo": nombre, "pj": pj, "puntos": puntos, "ppg": round(puntos / pj, 3),
            "casa": casa, "fuera": fuera, "forma_5_puntos": forma, "forma_5": "VVVVV"}


EQUIPOS = {
    "Barcelona (F)": equipo("Barcelona (F)", 11, 28, {"pj": 5, "g": 5, "e": 0, "p": 0, "gf": 24, "gc": 3}, {"pj": 6, "g": 4, "e": 1, "p": 1, "gf": 18, "gc": 3}, 10),
    "Valencia (F)": equipo("Valencia (F)", 11, 7, {"pj": 6, "g": 1, "e": 2, "p": 3, "gf": 5, "gc": 12}, {"pj": 5, "g": 1, "e": 0, "p": 4, "gf": 3, "gc": 14}, 4),
    "Eibar (F)": equipo("Eibar (F)", 11, 13, {"pj": 6, "g": 3, "e": 1, "p": 2, "gf": 8, "gc": 9}, {"pj": 5, "g": 1, "e": 2, "p": 2, "gf": 5, "gc": 7}, 5),
}
PRIOR = {"1": 44.0, "X": 28.0, "2": 28.0}


class AjustePorLigaFTests(unittest.TestCase):
    def test_solo_actua_en_partidos_de_liga_f_con_datos(self):
        p, t = motor.ajustar_por_liga_f(PRIOR, {"local": "Girona FC", "visitante": "UD Almeria"}, EQUIPOS)
        self.assertFalse(t["activo"]); self.assertEqual(p, PRIOR)
        p, t = motor.ajustar_por_liga_f(PRIOR, {"local": "Eibar (F)", "visitante": "Arsenal (F)"}, EQUIPOS)
        self.assertFalse(t["activo"]); self.assertEqual(p, PRIOR)

    def test_el_colista_en_casa_contra_el_lider_deja_de_ser_favorito(self):
        p, t = motor.ajustar_por_liga_f(PRIOR, {"local": "Valencia (F)", "visitante": "Barcelona (F)"}, EQUIPOS)
        self.assertTrue(t["activo"])
        self.assertGreater(p["2"], 55)
        self.assertLess(p["1"], 25)
        self.assertAlmostEqual(sum(p.values()), 100.0, delta=0.3)

    def test_el_lider_en_casa_es_favorito_claro_y_el_equilibrado_queda_abierto(self):
        p, _ = motor.ajustar_por_liga_f(PRIOR, {"local": "Barcelona (F)", "visitante": "Eibar (F)"}, EQUIPOS)
        self.assertGreater(p["1"], 65)
        p2, t2 = motor.ajustar_por_liga_f(PRIOR, {"local": "Eibar (F)", "visitante": "Eibar (F)"}, EQUIPOS)
        self.assertTrue(t2["activo"])
        self.assertLess(max(p2.values()), 55)

    def test_madrid_cff_es_liga_f_sin_sufijo(self):
        self.assertTrue(motor.es_equipo_liga_f("Madrid CFF"))
        self.assertTrue(motor.es_equipo_liga_f("Tenerife (F)"))
        self.assertFalse(motor.es_equipo_liga_f("Real Madrid CF"))
        equipos = dict(EQUIPOS)
        equipos["Madrid CFF (F)"] = equipo("Madrid CFF (F)", 11, 17, {"pj": 6, "g": 4, "e": 1, "p": 1, "gf": 11, "gc": 7}, {"pj": 5, "g": 1, "e": 1, "p": 3, "gf": 7, "gc": 17}, 4)
        p, t = motor.ajustar_por_liga_f(PRIOR, {"local": "Eibar (F)", "visitante": "Madrid CFF"}, equipos)
        self.assertTrue(t["activo"])

    def test_alias_de_la_quiniela_casan_con_el_canonico(self):
        p, t = motor.ajustar_por_liga_f(PRIOR, {"local": "FC Barcelona (F)", "visitante": "Valencia CF (F)"}, EQUIPOS)
        self.assertTrue(t["activo"])
        self.assertEqual(t["local"]["equipo"], "Barcelona (F)")


if __name__ == "__main__":
    unittest.main()
