import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cargar_historico_quinielas_lae as chq


def jornada_local(num_jornada, con_pleno15=True, pleno15_resuelto=True):
    partidos = [
        {"num": i, "local": f"Local{i}", "visitante": f"Visitante{i}", "resultado": "1-0", "signo_oficial": "1", "fecha": "2026-07-01"}
        for i in range(1, 15)
    ]
    data = {"jornada": num_jornada, "partidos": partidos, "fuente": "test"}
    if con_pleno15:
        data["pleno15"] = {
            "num": 15,
            "local": "España",
            "visitante": "Argentina",
            "fecha": "2026-07-19",
            "resultado": "1-1" if pleno15_resuelto else "Pendiente",
            "signo_oficial": "1-1" if pleno15_resuelto else "Pendiente",
        }
    return data


class CargarJornadasLocalesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._original_jornadas_dir = chq.JORNADAS_DIR
        chq.JORNADAS_DIR = Path(self._tmp.name)

    def tearDown(self):
        chq.JORNADAS_DIR = self._original_jornadas_dir
        self._tmp.cleanup()

    def _escribir(self, num_jornada, data):
        path = chq.JORNADAS_DIR / f"jornada_{num_jornada}.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_incluye_el_pleno_al_15_resuelto_como_partido_num_15(self):
        self._escribir(73, jornada_local(73, con_pleno15=True, pleno15_resuelto=True))

        jornadas = chq.cargar_jornadas_locales()

        self.assertEqual(len(jornadas), 1)
        p15 = next((p for p in jornadas[0]["partidos"] if p["num"] == 15), None)
        self.assertIsNotNone(p15)
        self.assertEqual(p15["local"], "España")
        self.assertEqual(p15["visitante"], "Argentina")
        self.assertEqual(p15["resultado"], "1-1")
        self.assertEqual(p15["signo_oficial"], "1-1")

    def test_pleno_al_15_pendiente_no_lleva_signo_oficial(self):
        self._escribir(74, jornada_local(74, con_pleno15=True, pleno15_resuelto=False))

        jornadas = chq.cargar_jornadas_locales()

        p15 = next((p for p in jornadas[0]["partidos"] if p["num"] == 15), None)
        self.assertIsNotNone(p15)
        self.assertEqual(p15["resultado"], "Pendiente")
        self.assertNotIn("signo_oficial", p15)

    def test_sin_pleno15_no_anade_partido_num_15(self):
        self._escribir(75, jornada_local(75, con_pleno15=False))

        jornadas = chq.cargar_jornadas_locales()

        nums = [p["num"] for p in jornadas[0]["partidos"]]
        self.assertNotIn(15, nums)
        self.assertEqual(len(nums), 14)

    def test_signos_14_no_incluye_el_pleno15(self):
        self._escribir(76, jornada_local(76, con_pleno15=True, pleno15_resuelto=True))

        jornadas = chq.cargar_jornadas_locales()

        self.assertEqual(len(jornadas[0]["signos_14"]), 14)


if __name__ == "__main__":
    unittest.main()
