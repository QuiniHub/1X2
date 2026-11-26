import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modelo_metricas_1x2 import (
    construir_regla_de_potencia,
    enriquecer_metricas_probabilisticas,
    log_score_por_clase,
    tamano_muestral_para_delta,
)


FIXTURE = [
    {"jornada": 1, "y": "1", "probs": {"1": 50, "X": 30, "2": 20}},
    {"jornada": 1, "y": "X", "probs": {"1": 50, "X": 25, "2": 25}},
    {"jornada": 2, "y": "2", "probs": {"1": 20, "X": 30, "2": 50}},
    {"jornada": 2, "y": "1", "probs": {"1": 80, "X": 10, "2": 10}},
    {"jornada": 3, "y": "X", "probs": {"1": 40, "X": 20, "2": 40}},
    {"jornada": 3, "y": "M", "probs": {"1": 40, "X": 20, "2": 40}},   # signo invalido -> sin_datos
]


class LogScorePorClaseTests(unittest.TestCase):
    def test_valores_en_fixture_pequeno(self):
        out = log_score_por_clase(FIXTURE, repeticiones=200)
        self.assertEqual(out["partidos"], 5)
        self.assertEqual(out["sin_datos"], 1)
        esperado_1 = (-math.log(0.5) - math.log(0.8)) / 2
        self.assertAlmostEqual(out["por_clase"]["1"]["log_score"], esperado_1, places=4)
        self.assertEqual(out["por_clase"]["1"]["n"], 2)
        esperado_x = (-math.log(0.25) - math.log(0.2)) / 2
        self.assertAlmostEqual(out["por_clase"]["X"]["log_score"], esperado_x, places=4)
        self.assertAlmostEqual(out["por_clase"]["2"]["log_score"], -math.log(0.5), places=4)
        total = (-math.log(0.5) - math.log(0.25) - math.log(0.5) - math.log(0.8) - math.log(0.2)) / 5
        self.assertAlmostEqual(out["global"]["log_score"], total, places=4)
        # con jornada presente hay IC bootstrap por jornada en el global
        ic = out["global"]["ic95_bootstrap_jornada"]
        self.assertEqual(len(ic), 2)
        self.assertLessEqual(ic[0], out["global"]["log_score"])
        self.assertGreaterEqual(ic[1], out["global"]["log_score"])

    def test_sin_jornada_no_hay_bootstrap_y_sin_items_devuelve_vacio(self):
        out = log_score_por_clase([{"y": "1", "probs": {"1": 60, "X": 25, "2": 15}}])
        self.assertNotIn("ic95_bootstrap_jornada", out["global"])
        vacio = log_score_por_clase([])
        self.assertIsNone(vacio["global"])
        self.assertEqual(vacio["partidos"], 0)

    def test_prediccion_mejor_da_log_score_menor(self):
        bueno = log_score_por_clase([{"y": "1", "probs": {"1": 80, "X": 10, "2": 10}}])
        malo = log_score_por_clase([{"y": "1", "probs": {"1": 40, "X": 30, "2": 30}}])
        self.assertLess(bueno["global"]["log_score"], malo["global"]["log_score"])


class TamanoMuestralTests(unittest.TestCase):
    def test_monotono_decreciente_en_delta(self):
        ns = [tamano_muestral_para_delta(d, sd_diferencia=0.08)["n_partidos"] for d in (0.001, 0.002, 0.005, 0.01)]
        self.assertEqual(ns, sorted(ns, reverse=True))
        self.assertTrue(all(a > b for a, b in zip(ns, ns[1:])))

    def test_formula_coincide_con_las_notas(self):
        # notas: delta 0,002 con sd 0,061-0,093 -> 7.200-17.000 partidos
        self.assertEqual(tamano_muestral_para_delta(0.002, 0.061)["n_partidos"], math.ceil(((1.96 + 0.8416) * 0.061 / 0.002) ** 2))
        rango = tamano_muestral_para_delta(0.002)["n_partidos_rango"]
        self.assertGreater(rango[0], 6000)
        self.assertLess(rango[1], 18000)
        self.assertLess(rango[0], rango[1])

    def test_delta_invalido(self):
        self.assertIsNone(tamano_muestral_para_delta(0)["n_partidos"])

    def test_regla_de_potencia_frase(self):
        bloque = construir_regla_de_potencia(300, sd_diferencia=0.08)
        self.assertIn("0.002", bloque["por_delta"])
        self.assertIn("esta temporada lleva 300", bloque["por_delta"]["0.002"]["frase"])
        self.assertGreater(bloque["por_delta"]["0.002"]["partidos_necesarios"], bloque["por_delta"]["0.005"]["partidos_necesarios"])


class EnriquecerMetricasTests(unittest.TestCase):
    def test_anade_bloques_sin_tocar_claves_existentes(self):
        with tempfile.TemporaryDirectory() as tmp:
            metricas = Path(tmp) / "metricas_probabilisticas.json"
            revisiones = Path(tmp) / "revisiones_prediccion_resultado.json"
            previo = {"version": "1.0", "partidos_evaluados": 2, "rps_calibracion": {"rps_medio_global": 0.2}}
            metricas.write_text(json.dumps(previo), encoding="utf-8")
            revisiones.write_text(json.dumps({"revisiones": [
                {"jornada": 1, "signo_real": "1", "probabilidades_usadas": {"1": 60, "X": 25, "2": 15}},
                {"jornada": 2, "signo_real": "X", "probabilidades_usadas": {"1": 40, "X": 30, "2": 30}},
            ]}), encoding="utf-8")
            vacio = Path(tmp) / "vacio"
            vacio.mkdir()
            out = enriquecer_metricas_probabilisticas(metricas, revisiones, dir_pre_cierre=vacio, dir_jornadas=vacio)
            for k, v in previo.items():
                self.assertEqual(out[k], v)
            self.assertEqual(out["log_score_por_clase"]["partidos"], 2)
            self.assertEqual(out["regla_de_potencia"]["partidos_esta_temporada"], 2)
            # sin snapshots: cae al rango simulado de las notas
            self.assertIn("rango simulado", out["regla_de_potencia"]["fuente_sd"])
            guardado = json.loads(metricas.read_text(encoding="utf-8"))
            self.assertIn("log_score_por_clase", guardado)
            self.assertEqual(guardado["rps_calibracion"], previo["rps_calibracion"])


if __name__ == "__main__":
    unittest.main()
