import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import preparar_temporada_2026_2027 as prep


def calendario_con_partidos(temporada, jugado=True):
    return {
        "temporada": temporada,
        "jornadas": [
            {
                "jornada": 1,
                "partidos": [
                    {"local": "A", "visitante": "B", "estado": "Jugado" if jugado else "Pendiente", "resultado": "1-0" if jugado else ""},
                ],
            }
        ],
    }


class TieneParticosJugadosTests(unittest.TestCase):
    def test_detecta_partidos_jugados(self):
        self.assertTrue(prep.tiene_partidos_jugados(calendario_con_partidos("2025/2026", jugado=True)))

    def test_calendario_sin_jugar_no_cuenta(self):
        self.assertFalse(prep.tiene_partidos_jugados(calendario_con_partidos("2026/2027", jugado=False)))

    def test_calendario_vacio_no_falla(self):
        self.assertFalse(prep.tiene_partidos_jugados({}))


class ArchivarCalendarioSalienteTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._original_data = prep.DATA
        prep.DATA = Path(self._tmpdir.name)

    def tearDown(self):
        prep.DATA = self._original_data

    def test_archiva_temporada_saliente_con_partidos_reales(self):
        existente = calendario_con_partidos("2025/2026", jugado=True)
        prep.archivar_calendario_saliente("primera", existente)
        destino = prep.DATA / "historico" / "calendario_primera_2025_2026.json"
        self.assertTrue(destino.exists())
        self.assertEqual(json.loads(destino.read_text(encoding="utf-8"))["temporada"], "2025/2026")

    def test_no_archiva_si_no_hay_partidos_jugados(self):
        existente = calendario_con_partidos("2025/2026", jugado=False)
        prep.archivar_calendario_saliente("primera", existente)
        destino = prep.DATA / "historico" / "calendario_primera_2025_2026.json"
        self.assertFalse(destino.exists())

    def test_no_archiva_si_ya_es_la_temporada_actual(self):
        existente = calendario_con_partidos(prep.TEMPORADA, jugado=True)
        prep.archivar_calendario_saliente("primera", existente)
        destino = prep.DATA / "historico" / f"calendario_primera_{prep.TEMPORADA.replace('/', '_')}.json"
        self.assertFalse(destino.exists())

    def test_no_sobrescribe_un_archivo_ya_guardado(self):
        destino = prep.DATA / "historico" / "calendario_primera_2025_2026.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps({"marcador": "no tocar"}), encoding="utf-8")
        prep.archivar_calendario_saliente("primera", calendario_con_partidos("2025/2026", jugado=True))
        self.assertEqual(json.loads(destino.read_text(encoding="utf-8"))["marcador"], "no tocar")


if __name__ == "__main__":
    unittest.main()
