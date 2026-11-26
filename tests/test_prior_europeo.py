"""Tests de prior_europeo (Laboratorio 26/11/2026): encogimiento de la X hacia el prior,
no-op con veredicto NO_DESPLEGAR, cierre a 100, backtest leave-one-out y criterios."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import prior_europeo as pe


def _escribir(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


def _partido(p1, px, p2, real, mercado=(50.0, 25.0, 25.0)):
    return {"motor": {"1": p1, "X": px, "2": p2},
            "mercado": dict(zip("1X2", (m / 100.0 for m in mercado))) if mercado else None,
            "y": real, "extranjero": True}


def _por_jornada():
    """6 jornadas sinteticas donde el motor pone mucha X y salen pocas."""
    out = {}
    for j in (5, 13, 15, 19, 22, 24):
        partidos = []
        for i in range(12):
            real = "X" if i == 0 else ("1" if i % 2 else "2")
            partidos.append(_partido(0.45, 0.30, 0.25, real))
        out[j] = partidos
    return out


class EncogerTests(unittest.TestCase):
    def test_formula_y_reparto_proporcional(self):
        out = pe.encoger_x({"1": 0.6, "X": 0.3, "2": 0.1}, x_prior=0.16, w=0.5)
        self.assertAlmostEqual(out["X"], 0.23)
        self.assertAlmostEqual(sum(out.values()), 1.0)
        self.assertAlmostEqual(out["1"] / out["2"], 6.0)

    def test_sube_la_x_si_esta_por_debajo_del_prior(self):
        out = pe.encoger_x({"1": 0.8, "X": 0.1, "2": 0.1}, x_prior=0.16, w=0.5)
        self.assertAlmostEqual(out["X"], 0.13)


class AjustarTests(unittest.TestCase):
    PROBS = {"1": 60.0, "X": 25.0, "2": 15.0}

    def test_no_op_por_defecto_si_no_desplegar(self):
        out, traza = pe.ajustar_por_competicion_europea(self.PROBS, veredicto="NO_DESPLEGAR", x_prior=0.16, w=0.5)
        self.assertEqual(out, self.PROBS)
        self.assertFalse(traza["activo"])
        self.assertEqual(traza["x_antes"], traza["x_despues"])
        self.assertIn("no-op", traza["motivo"])

    def test_forzar_y_desplegar_actuan_y_cierran_a_100(self):
        out, traza = pe.ajustar_por_competicion_europea(self.PROBS, mercado={"1": 55, "X": 22, "2": 23},
                                                        veredicto="NO_DESPLEGAR", x_prior=0.16, w=0.5, forzar=True)
        self.assertTrue(traza["activo"])
        self.assertAlmostEqual(out["X"], 20.5, places=2)
        self.assertAlmostEqual(sum(out.values()), 100.0, places=2)
        self.assertAlmostEqual(out["1"] / out["2"], 4.0, places=2)
        self.assertEqual(traza["x_antes"], 25.0)
        self.assertEqual(traza["x_despues"], 20.5)
        self.assertEqual(traza["x_mercado"], 22.0)
        self.assertIn("forzado", traza["motivo"])
        out2, traza2 = pe.ajustar_por_competicion_europea(self.PROBS, veredicto="DESPLEGAR", x_prior=0.16, w=0.5)
        self.assertTrue(traza2["activo"])
        self.assertEqual(out2, out)

    def test_domestico_no_se_toca_ni_forzado(self):
        out, traza = pe.ajustar_por_competicion_europea(self.PROBS, es_extranjero=False, veredicto="DESPLEGAR",
                                                        x_prior=0.16, w=0.5, forzar=True)
        self.assertEqual(out, self.PROBS)
        self.assertFalse(traza["activo"])

    def test_escala_fraccion(self):
        out, _ = pe.ajustar_por_competicion_europea({"1": 0.6, "X": 0.25, "2": 0.15}, veredicto="DESPLEGAR",
                                                    x_prior=0.16, w=1.0)
        self.assertAlmostEqual(out["X"], 0.16)
        self.assertAlmostEqual(sum(out.values()), 1.0)

    def test_lee_veredicto_del_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "bt.json"
            _escribir(ruta, {"veredicto": "NO_DESPLEGAR", "parametros_recomendados": {"x_prior": 0.14, "w": 0.75}})
            pe._CACHE["datos"] = None
            out, traza = pe.ajustar_por_competicion_europea(self.PROBS, ruta=ruta)
            self.assertFalse(traza["activo"])
            self.assertEqual(traza["x_prior"], 0.14)
            self.assertEqual(traza["w"], 0.75)
            self.assertEqual(out, self.PROBS)
            pe._CACHE["datos"] = None


class BacktestTests(unittest.TestCase):
    def test_leave_one_out_y_criterios(self):
        bt = pe.backtest(_por_jornada())
        self.assertEqual(bt["n_partidos"], 72)
        self.assertEqual(len(bt["rejilla_in_sample"]), 9)
        self.assertEqual(len(bt["ajustado_leave_one_out"]["por_jornada"]), 6)
        # el motor pone 30% de X y sale 1/12: encoger la X siempre gana en las 6 jornadas
        self.assertEqual(bt["jornadas_ganadas_al_motor"], 6)
        self.assertLess(bt["ajustado_leave_one_out"]["log_loss"], bt["motor_actual"]["log_loss"])
        self.assertLess(bt["ajustado_leave_one_out"]["x_predichas"], bt["motor_actual"]["x_predichas"])
        self.assertEqual(bt["mercado_losilla"]["n"], 72)
        veredicto, motivos = pe.evaluar_criterios(bt)
        self.assertIn(veredicto, ("DESPLEGAR", "NO_DESPLEGAR"))
        self.assertEqual(len(motivos), 2)
        self.assertIn("6/6", motivos[0])

    def test_criterio_rps_mercado(self):
        bt = {"jornadas_ganadas_al_motor": 5, "jornadas": list(range(6)),
              "ajustado_leave_one_out": {"rps": 0.190}, "mercado_losilla": {"rps": 0.180}}
        self.assertEqual(pe.evaluar_criterios(bt)[0], "NO_DESPLEGAR")
        bt["mercado_losilla"] = {"rps": 0.1885}
        self.assertEqual(pe.evaluar_criterios(bt)[0], "DESPLEGAR")
        bt["jornadas_ganadas_al_motor"] = 4
        self.assertEqual(pe.evaluar_criterios(bt)[0], "NO_DESPLEGAR")
        bt["jornadas_ganadas_al_motor"] = 5
        bt["mercado_losilla"] = {"n": 0}
        self.assertEqual(pe.evaluar_criterios(bt)[0], "DESPLEGAR")

    def test_ejecutar_con_fixture_en_disco(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            snaps, jor = base / "pre_cierre", base / "jornadas"
            for num, creado in ((5, "2026-09-07"), (13, "2026-10-12")):
                pred = {"jornada": num, "partidos": [
                    {"num": 1, "local": "Arsenal", "visitante": "Dortmund", "probabilidades": {"1": 60, "X": 25, "2": 15},
                     "mercado_losilla": {"1": 62, "X": 21, "2": 17}},
                    {"num": 2, "local": "PSG", "visitante": "Inter", "probabilidades": {"1": 45, "X": 30, "2": 25}},
                    {"num": 3, "local": "Ajax", "visitante": "Benfica", "probabilidades": {"1": 40, "X": 30, "2": 30}}]}
                _escribir(snaps / f"jornada_{num}.json", {"jornada": num, "creado_en": creado, "prediccion": pred})
                _escribir(jor / f"jornada_{num}.json", {"partidos": [{"num": 1, "signo_oficial": "1"},
                                                                       {"num": 2, "signo_oficial": "2"},
                                                                       {"num": 3, "signo_oficial": "Pendiente"}]})
            ruta = base / "out" / "bt.json"
            _escribir(ruta, {"criterios_prerregistrados": {"descripcion": "ORIGINAL"}})
            salida = pe.ejecutar(ruta, snaps, jor, jornadas=(5, 13))
            self.assertEqual(salida["criterios_prerregistrados"]["descripcion"], "ORIGINAL")
            self.assertEqual(salida["backtest"]["n_partidos"], 4)
            self.assertEqual(salida["backtest"]["mercado_losilla"]["n"], 2)
            self.assertIn(salida["veredicto"], ("DESPLEGAR", "NO_DESPLEGAR"))
            en_disco = json.loads(ruta.read_text(encoding="utf-8"))
            self.assertEqual(en_disco["estado"], "con_resultados")
            self.assertIn("parametros_recomendados", en_disco)
            pe._CACHE["datos"] = None


if __name__ == "__main__":
    unittest.main()
