import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modelo_metricas_1x2 import build_dataset, build_prediction_state, feature_row_for_match
from motor_prediccion_quiniela import ajustar_por_modelo_entrenado


class ModeloMetricas1X2Tests(unittest.TestCase):
    def test_feature_row_futuro_usa_estado_historico_sin_resultado(self):
        rows = build_dataset(ROOT / "data" / "jornadas")
        self.assertGreater(len(rows), 0)

        states, priors = build_prediction_state(ROOT / "data" / "jornadas")
        row = feature_row_for_match(
            {"num": 1, "local": rows[-1]["local"], "visitante": rows[-1]["visitante"], "resultado": "Pendiente"},
            states,
            priors,
            ROOT / "data" / "jornadas",
        )

        self.assertEqual(set(row["prob_baseline"]), {"1", "X", "2"})
        self.assertAlmostEqual(sum(row["prob_baseline"].values()), 1.0, places=5)
        self.assertIn("elo_diff", row)
        self.assertIn("competicion", row)

    def test_motor_degrada_si_modelo_runtime_no_esta_activo(self):
        probs = {"1": 50.0, "X": 30.0, "2": 20.0}
        ajustadas, ajuste = ajustar_por_modelo_entrenado(probs, {"local": "A", "visitante": "B"}, {"activo": False, "motivo": "test"})

        self.assertEqual(ajustadas, probs)
        self.assertFalse(ajuste["activo"])
        self.assertEqual(ajuste["motivo"], "test")


if __name__ == "__main__":
    unittest.main()
