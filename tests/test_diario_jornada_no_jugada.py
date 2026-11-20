import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import construir_memoria_ia as memoria


class JugadasDesdeSnapshotsTests(unittest.TestCase):
    """Caso real 20/11/2026: la J22 (paron) no se jugo; el diario quedaba vacio y
    la compuerta bloqueaba la J23. El motor se examina con su snapshot pre-cierre."""

    def _montar(self, base, cerrada=True, mismo_equipo=True):
        snaps = base / "pre_cierre"; snaps.mkdir()
        jornadas = base / "jornadas"; jornadas.mkdir()
        (snaps / "jornada_22.json").write_text(json.dumps({"jornada": 22, "congelado_en": "2026-11-17T10:39:00+00:00", "prediccion": {
            "pleno15": {"pronostico_marcador": "1-2"},
            "partidos": [{"num": i + 1, "local": "Bosnia" if i == 0 else "L", "visitante": "V", "signo_final": "1X" if i % 5 == 0 else "1", "elige8": i in (1, 3)} for i in range(14)]}}), encoding="utf-8")
        (jornadas / "jornada_22.json").write_text(json.dumps({"jornada": 22, "partidos": [
            {"num": i + 1, "local": (("Bosnia" if i == 0 else "L") if mismo_equipo else f"Otro{i}"), "visitante": "V",
             "signo_oficial": "1" if (cerrada or i < 13) else "Pendiente"} for i in range(14)]}), encoding="utf-8")
        return snaps, jornadas

    def test_sintetiza_la_jugada_del_motor_para_una_jornada_cerrada_sin_jugada(self):
        with tempfile.TemporaryDirectory() as tmp:
            snaps, jornadas = self._montar(Path(tmp))
            out = memoria.jugadas_desde_snapshots_pre_cierre({21: {}}, snaps, jornadas)
            self.assertIn(22, out)
            self.assertEqual(out[22]["origen"], "prediccion_motor_pre_cierre")
            self.assertFalse(out[22]["jugada_real"])
            self.assertEqual(out[22]["signos"][0], "1X")
            self.assertEqual(out[22]["elige8"], [2, 4])
            self.assertEqual(out[22]["pleno15"], "1-2")

    def test_no_sintetiza_si_ya_hay_jugada_real_ni_si_no_esta_cerrada_ni_si_es_otra_temporada(self):
        with tempfile.TemporaryDirectory() as tmp:
            snaps, jornadas = self._montar(Path(tmp))
            self.assertEqual(memoria.jugadas_desde_snapshots_pre_cierre({22: {"signos": ["1"] * 14}}, snaps, jornadas), {})
        with tempfile.TemporaryDirectory() as tmp:
            snaps, jornadas = self._montar(Path(tmp), cerrada=False)
            self.assertEqual(memoria.jugadas_desde_snapshots_pre_cierre({}, snaps, jornadas), {})
        with tempfile.TemporaryDirectory() as tmp:
            snaps, jornadas = self._montar(Path(tmp), mismo_equipo=False)
            self.assertEqual(memoria.jugadas_desde_snapshots_pre_cierre({}, snaps, jornadas), {})


if __name__ == "__main__":
    unittest.main()
