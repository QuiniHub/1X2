import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_todo as at


def escribir_jornada1(carpeta, partidos):
    (carpeta / "data" / "jornadas").mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "data" / "jornadas" / "jornada_1.json"
    ruta.write_text(json.dumps({"partidos": partidos}), encoding="utf-8")
    return ruta


class TemporadaYaIniciadaTests(unittest.TestCase):
    """Bug real de arranque de temporada 26/27 (16/08/2026): el pipeline
    solo miraba el mes (julio/agosto = pretemporada) para decidir si
    relanzar preparar_temporada_2026_2027.py, que reinicia la clasificacion
    a 0. Como LaLiga empieza DENTRO de agosto, eso resucitaba la
    clasificacion en blanco en cada ciclo aunque ya hubiera partidos reales
    jugados y cerrados (Alaves 3-0 Getafe, 15/08)."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._original_root = at.ROOT
        at.ROOT = Path(self._tmpdir.name)

    def tearDown(self):
        at.ROOT = self._original_root

    def test_falso_si_no_existe_jornada_1(self):
        self.assertFalse(at.temporada_ya_iniciada())

    def test_falso_si_todos_los_partidos_pendientes(self):
        escribir_jornada1(at.ROOT, [
            {"resultado": "Pendiente"},
            {"resultado": "Pendiente"},
        ])
        self.assertFalse(at.temporada_ya_iniciada())

    def test_verdadero_si_algun_partido_ya_cerrado(self):
        escribir_jornada1(at.ROOT, [
            {"resultado": "3-0"},
            {"resultado": "Pendiente"},
        ])
        self.assertTrue(at.temporada_ya_iniciada())

    def test_json_corrupto_no_rompe_y_devuelve_falso(self):
        (at.ROOT / "data" / "jornadas").mkdir(parents=True, exist_ok=True)
        ruta = at.ROOT / "data" / "jornadas" / "jornada_1.json"
        ruta.write_text("{esto no es json valido", encoding="utf-8")
        self.assertFalse(at.temporada_ya_iniciada())


if __name__ == "__main__":
    unittest.main()
