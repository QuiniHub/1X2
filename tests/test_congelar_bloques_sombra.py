"""Tests de congelar_bloques_sombra (26/11/2026): los bloques en sombra de una
jornada en juego vuelven a ser los del snapshot pre-cierre."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import congelar_bloques_sombra as cb


def _montar(tmp):
    tmp = Path(tmp)
    (tmp / "pred").mkdir()
    (tmp / "snap").mkdir()
    bueno = {"estado": "ok", "columna": ["1", "X", "1"], "modo": "sombra"}
    snapshot = {"primer_partido_utc": "2026-11-24T20:00:00+00:00", "refrescado_en": "2026-11-24T15:03:09+00:00",
                "prediccion": {"jornada": 24, "columna_valiente": bueno, "sorpresa_nombrada": {"estado": "ok", "num": 5}}}
    (tmp / "snap" / "jornada_24.json").write_text(json.dumps(snapshot), encoding="utf-8")
    malo = {"jornada": 24, "columna_valiente": {"estado": "ok", "columna": ["2", "2", "2"]},
            "sorpresa_nombrada": {"estado": "ok", "num": 9}, "favoritos_en_riesgo": {"estado": "ok"}, "otro": 1}
    (tmp / "pred" / "jornada_24.json").write_text(json.dumps(malo), encoding="utf-8")
    (tmp / "ultima.json").write_text(json.dumps(malo), encoding="utf-8")
    return tmp


class CongelarTests(unittest.TestCase):
    def test_restaura_desde_snapshot_y_retira_lo_que_no_existia(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = _montar(tmp)
            ahora = datetime(2026, 11, 26, 8, 0, tzinfo=timezone.utc)
            r = cb.congelar(24, ahora=ahora, dir_predicciones=tmp / "pred", dir_snapshots=tmp / "snap", ruta_ultima=tmp / "ultima.json")
            self.assertEqual(r["estado"], "congelado")
            self.assertEqual(sorted(r["restaurados"]), ["columna_valiente", "sorpresa_nombrada"])
            self.assertEqual(r["retirados"], ["favoritos_en_riesgo"])
            for ruta in (tmp / "pred" / "jornada_24.json", tmp / "ultima.json"):
                d = json.loads(ruta.read_text(encoding="utf-8"))
                self.assertEqual(d["columna_valiente"]["columna"], ["1", "X", "1"])
                self.assertEqual(d["sorpresa_nombrada"]["num"], 5)
                self.assertNotIn("favoritos_en_riesgo", d)
                self.assertEqual(d["otro"], 1)
                self.assertIn("bloques_sombra_congelados", d)
            r2 = cb.congelar(24, ahora=ahora, dir_predicciones=tmp / "pred", dir_snapshots=tmp / "snap", ruta_ultima=tmp / "ultima.json")
            self.assertEqual(r2["estado"], "ya_congelado")

    def test_no_toca_una_jornada_sin_empezar(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = _montar(tmp)
            antes = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
            r = cb.congelar(24, ahora=antes, dir_predicciones=tmp / "pred", dir_snapshots=tmp / "snap", ruta_ultima=tmp / "ultima.json")
            self.assertEqual(r["estado"], "jornada_sin_empezar")
            d = json.loads((tmp / "pred" / "jornada_24.json").read_text(encoding="utf-8"))
            self.assertEqual(d["columna_valiente"]["columna"], ["2", "2", "2"])

    def test_sin_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = _montar(tmp)
            r = cb.congelar(25, dir_predicciones=tmp / "pred", dir_snapshots=tmp / "snap", ruta_ultima=tmp / "ultima.json")
            self.assertEqual(r["estado"], "sin_snapshot")


if __name__ == "__main__":
    unittest.main()
