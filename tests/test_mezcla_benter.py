import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

import mezcla_benter as mb


def _dirichlet(rng, alpha=(2.0, 1.4, 1.6)):
    g = [rng.gammavariate(a, 1.0) for a in alpha]
    t = sum(g)
    return [v / t for v in g]


def _sintetico(n, alpha_real, beta_real, semilla=3):
    """Generador conocido: la verdad es la mezcla de Benter de dos señales ruidosas."""
    rng = random.Random(semilla)
    P, Q, y = [], [], []
    for _ in range(n):
        q = _dirichlet(rng)
        # el motor es una version ruidosa del mercado
        p = [max(v * math.exp(rng.gauss(0, 0.5)), 1e-3) for v in q]
        s = sum(p)
        p = [v / s for v in p]
        verdad = mb.mezclar_benter({"1": p[0], "X": p[1], "2": p[2]}, {"1": q[0], "X": q[1], "2": q[2]}, alpha_real, beta_real)
        r = rng.random()
        acum = 0.0
        signo = "2"
        for sg in mb.SIGNOS:
            acum += verdad[sg]
            if r < acum:
                signo = sg
                break
        P.append(p)
        Q.append(q)
        y.append(mb.SIGNOS.index(signo))
    return np.array(P), np.array(Q), np.array(y)


class MezclaBenterTests(unittest.TestCase):
    def test_mezclar_benter_suma_uno_y_respeta_escala(self):
        out = mb.mezclar_benter({"1": 50.0, "X": 30.0, "2": 20.0}, {"1": 60.0, "X": 25.0, "2": 15.0}, 0.5, 0.5)
        self.assertAlmostEqual(sum(out.values()), 100.0, places=6)
        out_f = mb.mezclar_benter({"1": 0.5, "X": 0.3, "2": 0.2}, {"1": 0.6, "X": 0.25, "2": 0.15}, 0.5, 0.5)
        self.assertAlmostEqual(sum(out_f.values()), 1.0, places=9)
        # alpha=0, beta=1 devuelve el mercado; alpha=1, beta=0 devuelve el motor
        solo_q = mb.mezclar_benter({"1": 50, "X": 30, "2": 20}, {"1": 60, "X": 25, "2": 15}, 0.0, 1.0)
        self.assertAlmostEqual(solo_q["1"], 60.0, places=6)
        solo_p = mb.mezclar_benter({"1": 50, "X": 30, "2": 20}, {"1": 60, "X": 25, "2": 15}, 1.0, 0.0)
        self.assertAlmostEqual(solo_p["X"], 30.0, places=6)

    def test_temperatura_aplana_y_afila(self):
        p, q = {"1": 70, "X": 20, "2": 10}, {"1": 65, "X": 22, "2": 13}
        base = mb.mezclar_benter(p, q, 0.5, 0.5, T=1.0)
        plano = mb.mezclar_benter(p, q, 0.5, 0.5, T=2.0)
        afilado = mb.mezclar_benter(p, q, 0.5, 0.5, T=0.5)
        self.assertLess(plano["1"], base["1"])
        self.assertGreater(afilado["1"], base["1"])

    def test_inversion_mezcla_lineal_ida_y_vuelta(self):
        p_pre = {"1": 48.0, "X": 27.0, "2": 25.0}
        q = {"1": 62.0, "X": 23.0, "2": 15.0}
        for peso in (0.20, 0.45, 0.65):
            post = mb.mezclar_lineal(p_pre, q, peso)
            rec = mb.invertir_mezcla_lineal(post, q, peso)
            for s in mb.SIGNOS:
                self.assertAlmostEqual(rec[s], p_pre[s] / 100.0, places=6, msg=f"peso {peso} signo {s}")

    def test_inversion_recorta_cuando_sale_del_simplex(self):
        # p_post muy cerca del mercado con peso alto => p_pre bruto puede salir negativo
        rec = mb.invertir_mezcla_lineal({"1": 10.0, "X": 20.0, "2": 70.0}, {"1": 70.0, "X": 20.0, "2": 10.0}, 0.65)
        self.assertAlmostEqual(sum(rec.values()), 1.0, places=9)
        self.assertTrue(all(v >= mb.P_MIN / 3 for v in rec.values()))

    def test_recupera_alpha_beta_en_datos_sinteticos(self):
        alpha_real, beta_real = 0.6, 0.5
        P, Q, y = _sintetico(6000, alpha_real, beta_real)
        alpha, beta = mb.ajustar_alpha_beta(P, Q, y)
        self.assertAlmostEqual(alpha, alpha_real, delta=0.12)
        self.assertAlmostEqual(beta, beta_real, delta=0.12)

    def test_detecta_alpha_cero_cuando_el_motor_no_aporta(self):
        P, Q, y = _sintetico(6000, 0.0, 1.0, semilla=11)
        alpha, beta = mb.ajustar_alpha_beta(P, Q, y)
        self.assertAlmostEqual(alpha, 0.0, delta=0.12)
        self.assertAlmostEqual(beta, 1.0, delta=0.15)

    def test_temperatura_ajustada_cerca_de_uno_para_benter(self):
        P, Q, y = _sintetico(3000, 0.4, 0.7, semilla=5)
        alpha, beta = mb.ajustar_alpha_beta(P, Q, y)
        T = mb.ajustar_temperatura(mb.benter_matriz(P, Q, alpha, beta), y)
        self.assertAlmostEqual(T, 1.0, delta=0.1)

    def test_peso_mercado_usado_lee_lectura_o_calidad(self):
        peso, origen = mb.peso_mercado_usado({"ajuste_mercado_losilla": {"lecturas": ["consenso publico integrado con peso 0.45 (x)"]}})
        self.assertEqual((peso, origen), (0.45, "lectura"))
        peso, origen = mb.peso_mercado_usado({"calidad_datos": "baja"}, {"baja": 0.65}, 0.18)
        self.assertEqual((peso, origen), (0.65, "calidad_datos"))

    def test_parsear_fecha_y_temporada(self):
        f = mb.parsear_fecha_jornada("Domingo, 16 de agosto de 2026")
        self.assertEqual((f.year, f.month, f.day), (2026, 8, 16))
        self.assertEqual(mb.temporada_de(f, "2025/2026"), "2026/2027")  # la fecha manda sobre lo declarado
        self.assertEqual(mb.temporada_de(mb.parsear_fecha_jornada("2026-08-09")), "2025/2026")
        self.assertEqual(mb.temporada_de(None, "2025/2026"), "2025/2026")
        self.assertIsNone(mb.parsear_fecha_jornada("None"))

    def test_bootstrap_por_jornada_detecta_diferencia_clara(self):
        difs = [0.05] * 28 + [0.04] * 28
        jornadas = ["a"] * 14 + ["b"] * 14 + ["c"] * 14 + ["d"] * 14
        out = mb.bootstrap_por_jornada(difs, jornadas, repeticiones=300)
        self.assertGreater(out["ic95"][0], 0)
        self.assertTrue(out["significativa_95"])

    def test_cargar_parametros_es_noop_si_no_desplegar(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "mezcla_benter.json"
            ruta.write_text(json.dumps({"veredicto": "NO_DESPLEGAR", "parametros_finales_todo_el_dataset": {"alpha": 0.4, "beta": 0.9, "T": 1.0}}), encoding="utf-8")
            self.assertIsNone(mb.cargar_parametros(ruta))
            self.assertIsNone(mb.cargar_parametros(Path(tmp) / "no_existe.json"))
            ruta.write_text(json.dumps({"veredicto": "CANDIDATA", "parametros_finales_todo_el_dataset": {"alpha": 0.4, "beta": 0.9, "T": 1.0}}), encoding="utf-8")
            self.assertEqual(mb.cargar_parametros(ruta), {"alpha": 0.4, "beta": 0.9, "T": 1.0})

    def test_veredicto_aplica_criterio_prerregistrado(self):
        est = {"alpha_positivo_fraccion": 1.0, "alpha_media": 0.3, "alpha_sd": 0.05}
        ok = {"benter": {"log_loss": 0.90}, "mercado": {"log_loss": 0.92}, "motor_post": {"log_loss": 0.95}}
        self.assertEqual(mb.veredicto(est, ok)[0], "CANDIDATA")
        pierde_mercado = {"benter": {"log_loss": 0.93}, "mercado": {"log_loss": 0.92}, "motor_post": {"log_loss": 0.95}}
        self.assertEqual(mb.veredicto(est, pierde_mercado)[0], "NO_DESPLEGAR")
        alpha_cero = {"alpha_positivo_fraccion": 0.5, "alpha_media": 0.01, "alpha_sd": 0.1}
        v, lectura = mb.veredicto(alpha_cero, ok)
        self.assertEqual(v, "NO_DESPLEGAR")
        self.assertIn("generador de dobles", lectura)

    def test_analizar_con_snapshots_sinteticos_en_disco(self):
        """Dataset falso en disco: 8 jornadas x 14 partidos, el generador real es
        el mercado (alpha=0). El JSON debe traer el criterio prerregistrado y
        un veredicto valido, y el orden debe ser por fecha, no por numero."""
        rng = random.Random(1)
        with tempfile.TemporaryDirectory() as tmp:
            pre = Path(tmp) / "pre_cierre"
            jor = Path(tmp) / "jornadas"
            pre.mkdir()
            jor.mkdir()
            # numeros de jornada desordenados a proposito (75, 76 son de la temporada anterior)
            plan = [(75, "Domingo, 2 de agosto de 2026"), (76, "Domingo, 9 de agosto de 2026")] + [
                (k, f"Domingo, {16 + 7 * (k - 1)} de agosto de 2026" if k <= 3 else f"Domingo, {7 * (k - 3)} de septiembre de 2026")
                for k in range(1, 7)
            ]
            for j, fecha in plan:
                partidos_pred, partidos_fix = [], []
                for num in range(1, 15):
                    q = _dirichlet(rng)
                    p = [max(v * math.exp(rng.gauss(0, 0.5)), 1e-3) for v in q]
                    s = sum(p)
                    p = [v / s for v in p]
                    post = mb.mezclar_lineal({"1": p[0], "X": p[1], "2": p[2]}, {"1": q[0], "X": q[1], "2": q[2]}, 0.45)
                    r = rng.random()
                    signo = "1" if r < q[0] else ("X" if r < q[0] + q[1] else "2")
                    partidos_pred.append({
                        "num": num, "local": f"L{num}", "visitante": f"V{num}", "calidad_datos": "media_baja",
                        "probabilidades": {sg: round(post[sg] * 100, 1) for sg in mb.SIGNOS},
                        "mercado_losilla": {sg: round(q[i] * 100, 2) for i, sg in enumerate(mb.SIGNOS)},
                        "ajuste_mercado_losilla": {"lecturas": ["Mercado Losilla: consenso publico integrado con peso 0.45 (calidad_datos=media_baja)."]},
                    })
                    partidos_fix.append({"num": num, "signo_oficial": signo})
                (pre / f"jornada_{j}.json").write_text(json.dumps({"jornada": j, "prediccion": {"temporada_base": "x", "partidos": partidos_pred}}), encoding="utf-8")
                (jor / f"jornada_{j}.json").write_text(json.dumps({"jornada": j, "fecha": fecha, "partidos": partidos_fix}), encoding="utf-8")
            filas = mb.construir_dataset(pre, jor)
            self.assertEqual(len(filas), 8 * 14)
            self.assertEqual([f["jornada"] for f in filas[::14]], [75, 76, 1, 2, 3, 4, 5, 6])
            self.assertEqual(filas[0]["temporada"], "2025/2026")
            self.assertEqual(filas[-1]["temporada"], "2026/2027")
            salida = mb.analizar(pre, jor)
            self.assertEqual(list(salida.keys())[2], "criterio_prerregistrado")
            self.assertEqual(salida["estado"], "ok")
            self.assertIn(salida["veredicto"], ("CANDIDATA", "NO_DESPLEGAR"))
            wf = salida["walk_forward"]
            self.assertEqual(wf["partidos_oos"], 4 * 14)
            self.assertEqual(set(wf["metricas_oos"]), {"motor_pre", "mercado", "motor_post", "benter", "benter_T", "lineal_50", "lineal_50_T"})
            self.assertIn("benter_menos_mercado", wf["comparaciones_bootstrap_por_jornada"])
            self.assertEqual(salida["leave_one_season_out"]["estado"], "ok")
            self.assertIn("partidos_para_detectar_delta_log_loss_0.01", salida["potencia"])


if __name__ == "__main__":
    unittest.main()
