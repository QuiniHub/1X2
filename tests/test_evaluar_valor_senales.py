import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import evaluar_valor_senales as evs


def evaluacion(acierto, brier=0.5):
    return {"jornada": 1, "num": 1, "acierto_top": acierto, "brier": brier, "senales": {}}


class EvaluarSenalTests(unittest.TestCase):
    """Prueba solo la logica de decision (evaluar_senal), sin tocar disco."""

    def _con_sin(self, n_con, aciertos_con, n_sin, aciertos_sin, nombre="x"):
        evaluaciones = []
        for i in range(n_con):
            ev = evaluacion(i < aciertos_con)
            ev["senales"] = {nombre: True}
            evaluaciones.append(ev)
        for i in range(n_sin):
            ev = evaluacion(i < aciertos_sin)
            ev["senales"] = {nombre: False}
            evaluaciones.append(ev)
        return evaluaciones

    def test_senal_con_muestra_insuficiente_no_concluye_nada(self):
        evaluaciones = self._con_sin(n_con=40, aciertos_con=40, n_sin=200, aciertos_sin=0)
        resultado = evs.evaluar_senal(evaluaciones, "x")
        self.assertEqual(resultado["veredicto"], "sin_muestra_suficiente")
        self.assertIsNone(resultado["diferencia_precision"])

    def test_senal_que_ayuda_con_diferencia_grande(self):
        evaluaciones = self._con_sin(n_con=110, aciertos_con=110, n_sin=110, aciertos_sin=0)
        resultado = evs.evaluar_senal(evaluaciones, "x")
        self.assertEqual(resultado["veredicto"], "ayuda")
        self.assertEqual(resultado["con_senal"]["precision"], 100.0)
        self.assertEqual(resultado["sin_senal"]["precision"], 0.0)
        self.assertEqual(resultado["diferencia_precision"], 100.0)

    def test_senal_que_perjudica(self):
        evaluaciones = self._con_sin(n_con=110, aciertos_con=0, n_sin=110, aciertos_sin=110)
        resultado = evs.evaluar_senal(evaluaciones, "x")
        self.assertEqual(resultado["veredicto"], "perjudica")
        self.assertLess(resultado["diferencia_precision"], 0)

    def test_senal_sin_diferencia_relevante(self):
        evaluaciones = self._con_sin(n_con=110, aciertos_con=55, n_sin=110, aciertos_sin=56)
        resultado = evs.evaluar_senal(evaluaciones, "x")
        self.assertEqual(resultado["veredicto"], "sin_diferencia_relevante")


class EvaluacionesSnapshotsTests(unittest.TestCase):
    """Prueba la lectura real de snapshot + jornada oficial y la deteccion de cada senal."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self._snapshots_orig = evs.SNAPSHOTS
        self._jornadas_orig = evs.JORNADAS
        evs.SNAPSHOTS = base / "snapshots"
        evs.JORNADAS = base / "jornadas"
        evs.SNAPSHOTS.mkdir(parents=True)
        evs.JORNADAS.mkdir(parents=True)

    def tearDown(self):
        evs.SNAPSHOTS = self._snapshots_orig
        evs.JORNADAS = self._jornadas_orig
        self._tmp.cleanup()

    def test_extrae_las_tres_senales_desde_el_json_real(self):
        import json

        snapshot = {
            "jornada": 9001,
            "prediccion": {
                "jornada": 9001,
                "partidos": [
                    {
                        "num": 1,
                        "probabilidades": {"1": 70, "X": 20, "2": 10},
                        "alertas_motivacion": ["presion_descenso"],
                        "trazabilidad_datos": {"datos_profesionales": {"cuotas": True}},
                        "ajuste_motivacion": {"refuerzo_memoria_sorpresas_mercado": {"activo": True}},
                    },
                    {
                        "num": 2,
                        "probabilidades": {"1": 20, "X": 20, "2": 60},
                        "alertas_motivacion": [],
                        "trazabilidad_datos": {"datos_profesionales": {"cuotas": False}},
                        "ajuste_motivacion": {},
                    },
                ],
            },
        }
        (evs.SNAPSHOTS / "jornada_9001.json").write_text(json.dumps(snapshot), encoding="utf-8")

        jornada_oficial = {
            "jornada": 9001,
            "partidos": [
                {"num": 1, "signo_oficial": "1"},
                {"num": 2, "signo_oficial": "2"},
            ],
        }
        (evs.JORNADAS / "jornada_9001.json").write_text(json.dumps(jornada_oficial), encoding="utf-8")

        evaluaciones = evs.evaluaciones_snapshots()
        self.assertEqual(len(evaluaciones), 2)

        ev1 = next(e for e in evaluaciones if e["num"] == 1)
        ev2 = next(e for e in evaluaciones if e["num"] == 2)

        self.assertTrue(ev1["acierto_top"])
        self.assertTrue(ev1["senales"]["contexto_competitivo_motivacion"])
        self.assertTrue(ev1["senales"]["datos_profesionales_cuotas"])
        self.assertTrue(ev1["senales"]["refuerzo_sorpresas_mercado"])

        self.assertTrue(ev2["acierto_top"])
        self.assertFalse(ev2["senales"]["contexto_competitivo_motivacion"])
        self.assertFalse(ev2["senales"]["datos_profesionales_cuotas"])
        self.assertFalse(ev2["senales"]["refuerzo_sorpresas_mercado"])

    def test_partido_sin_resultado_oficial_se_ignora(self):
        import json

        snapshot = {
            "jornada": 9002,
            "prediccion": {
                "jornada": 9002,
                "partidos": [{"num": 1, "probabilidades": {"1": 50, "X": 30, "2": 20}}],
            },
        }
        (evs.SNAPSHOTS / "jornada_9002.json").write_text(json.dumps(snapshot), encoding="utf-8")
        (evs.JORNADAS / "jornada_9002.json").write_text(
            json.dumps({"jornada": 9002, "partidos": [{"num": 1, "signo_oficial": "Pendiente"}]}),
            encoding="utf-8",
        )

        evaluaciones = evs.evaluaciones_snapshots()
        self.assertEqual(evaluaciones, [])


if __name__ == "__main__":
    unittest.main()
