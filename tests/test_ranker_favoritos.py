"""Tests del ranker de favoritos en riesgo (26/11/2026): features y limites,
logistica minima, metricas, guardia anti-fuga del walk-forward, bloque en
vivo con un solo nombrado y marcador idempotente que salta jornadas abiertas."""
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ranker_favoritos as rf

ESP = {"real madrid cf", "fc barcelona", "rc celta de vigo", "getafe cf", "sevilla fc"}
FUENTES_VACIAS = {"ceses": [], "estudio_x": {}, "calendario": [], "senales_suspendidas": set()}


def _p(num, local, visitante, motor, losilla=None, signo_final="1"):
    p = {"num": num, "local": local, "visitante": visitante, "probabilidades": dict(zip("1X2", motor)),
         "signo_final": signo_final}
    if losilla:
        p["mercado_losilla"] = dict(zip("1X2", losilla))
    return p


def _fila(jornada, fecha, num, p_fav, cayo, **extra):
    base = {"jornada": jornada, "temporada": "2026_2027", "fecha": fecha, "num": num, "local": f"L{num}", "visitante": f"V{num}",
            "favorito": "1", "p_fav": p_fav, "baseline": round(1 - p_fav, 4), "cayo": cayo, "fuente_masa": "test",
            "gap_market": 0.0, "gap_motor_losilla": 0.0, "motor_fav_distinto_mercado": 0, "n_senales": 0,
            "es_europeo": 0, "favorito_local": 1, "prob_x_mix": 0.2}
    base.update(extra)
    return base


class FeaturesTests(unittest.TestCase):
    def test_favorito_bajo_umbral_no_entra(self):
        p = _p(1, "Getafe CF", "Sevilla FC", (55, 25, 20))
        self.assertIsNone(rf.features_partido(p, {}, None, None, ESP))

    def test_features_y_limites(self):
        p = _p(2, "Real Madrid CF", "RC Celta de Vigo", (80, 12, 8), (74, 16, 10))
        masa = {2: {"1": 92, "X": 5, "2": 3}}
        f = rf.features_partido(p, masa, None, None, ESP)
        self.assertEqual(f["favorito"], "1")
        self.assertAlmostEqual(f["p_fav"], 0.77, places=3)
        self.assertAlmostEqual(f["gap_market"], 0.77 - 0.92, places=3)   # masa sobrejuega -> negativo
        self.assertAlmostEqual(f["gap_motor_losilla"], 0.06, places=3)
        self.assertEqual(f["motor_fav_distinto_mercado"], 0)
        self.assertEqual(f["es_europeo"], 0)
        self.assertEqual(f["favorito_local"], 1)
        self.assertEqual(f["signo_si_cae"], "X")
        self.assertEqual(f["fuente_masa"], "porcentajes_lae")
        self.assertEqual(f["n_senales"], 0)
        for k in ("gap_market", "gap_motor_losilla"):
            self.assertTrue(-1 <= f[k] <= 1)
        self.assertTrue(0 <= f["prob_x_mix"] <= 1)
        self.assertAlmostEqual(f["baseline"], 1 - f["p_fav"], places=3)

    def test_europeo_visitante_y_motor_distinto_del_mercado(self):
        p = _p(3, "Sabah FA", "FC Barcelona", (20, 20, 60), (10, 15, 75))
        f = rf.features_partido(p, {}, None, None, ESP)
        self.assertEqual(f["es_europeo"], 1)
        self.assertEqual(f["favorito"], "2")
        self.assertEqual(f["favorito_local"], 0)
        self.assertEqual(f["fuente_masa"], "mercado_losilla")  # sin LAE cae a Losilla
        p2 = _p(4, "Arsenal", "Dortmund", (45, 20, 35), (30, 20, 50))
        f2 = rf.features_partido(p2, {}, None, None, ESP, umbral=0.40)
        self.assertEqual(f2["motor_fav_distinto_mercado"], 1)

    def test_senales_cuentan_con_fuentes(self):
        cal = [{"local": "Rayo", "visitante": "Valencia CF", "fecha": date(2026, 10, 11), "kl": "rayo", "kv": "valencia cf",
                "gl": 0, "gv": 1, "signo": "2"}]
        p = _p(5, "Rayo", "Valencia CF", (65, 20, 15))
        fuentes = {**FUENTES_VACIAS, "calendario": []}
        f = rf.features_partido(p, {}, date(2026, 11, 21), fuentes, ESP)
        self.assertEqual(f["n_senales"], 0)
        # con mercado Losilla >= 4 pts por encima del motor en el 2 -> señal mercado_mas_alto
        p2 = _p(6, "Rayo", "Valencia CF", (65, 20, 15), (55, 20, 25))
        f2 = rf.features_partido(p2, {}, date(2026, 11, 21), fuentes, ESP)
        self.assertGreaterEqual(f2["n_senales"], 1)
        del cal


class ModeloTests(unittest.TestCase):
    def test_logistica_separa_datos_sinteticos(self):
        import numpy as np
        rng = np.random.default_rng(1)
        X = rng.normal(size=(200, len(rf.FEATURES)))
        y = (X[:, 0] + 0.5 * X[:, 6] + rng.normal(scale=0.3, size=200) > 0).astype(float)
        modelo = rf.ajustar_logistica(X, y)
        self.assertGreater(modelo["coef"][0], 0.5)
        filas = [dict(zip(rf.FEATURES, fila), baseline=0.3) for fila in X.tolist()]
        scores = rf.predecir(modelo, filas)
        self.assertTrue(all(0 <= s <= 1 for s in scores))
        self.assertGreater(rf.auc(scores, y.tolist()), 0.9)

    def test_metricas(self):
        self.assertEqual(rf.auc([0.9, 0.8, 0.1, 0.2], [1, 1, 0, 0]), 1.0)
        self.assertEqual(rf.auc([0.5, 0.5, 0.5], [1, 0, 0]), 0.5)
        self.assertIsNone(rf.auc([0.5, 0.6], [1, 1]))
        self.assertAlmostEqual(rf.spearman([1, 2, 3, 4], [1, 2, 3, 4]), 1.0)
        self.assertAlmostEqual(rf.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertEqual(rf.percentil_caidos([0.9, 0.5, 0.1], [1, 0, 0]), 0.0)
        self.assertEqual(rf.percentil_caidos([0.9, 0.5, 0.1], [0, 0, 1]), 1.0)

    def test_predecir_sin_modelo_devuelve_baseline(self):
        filas = [_fila(1, "2026-08-16", 1, 0.7, 0)]
        self.assertEqual(rf.predecir(None, filas), [0.3])


class WalkForwardTests(unittest.TestCase):
    def _dataset(self):
        dataset = []
        for k in range(12):
            fecha = f"2026-09-{1 + k:02d}"
            for num in range(1, 7):
                dataset.append(_fila(k + 1, fecha, num, 0.65 + 0.02 * (num % 3), int((num + k) % 4 == 0),
                                     gap_market=0.1 * ((num + k) % 4 == 0) - 0.05))
        return dataset

    def test_guardia_anti_fuga(self):
        dataset = self._dataset()
        train = rf.filas_entrenamiento(dataset, "2026-09-05")
        self.assertTrue(train)
        self.assertTrue(all(f["fecha"] < "2026-09-05" for f in train))
        self.assertFalse(any(f["fecha"] >= "2026-09-05" for f in train))

    def test_walk_forward_solo_entrena_con_el_pasado(self):
        dataset = self._dataset()
        evaluadas = rf.walk_forward(dataset, min_entrenamiento=20)
        self.assertTrue(evaluadas)
        por_fecha = {}
        for e in evaluadas:
            por_fecha.setdefault(e["fecha"], set()).add(e["n_entrenamiento"])
        for fecha, ns in por_fecha.items():
            esperado = len(rf.filas_entrenamiento(dataset, fecha))
            self.assertEqual(ns, {esperado})
        # las primeras jornadas (sin 20 filas previas) no se evaluan
        self.assertNotIn("2026-09-01", por_fecha)
        resumen = rf.resumen_walk_forward(evaluadas)
        self.assertIn(resumen["veredicto"], ("SEPARA", "NO_SEPARA"))
        self.assertEqual(resumen["veredicto"], "NO_SEPARA")  # n < 120 por prerregistro
        self.assertIn("muestra insuficiente", resumen["motivo"])

    def test_resumen_vacio(self):
        self.assertEqual(rf.resumen_walk_forward([])["veredicto"], "SIN_DATOS")

    def test_backtest_sintetico_no_escribe(self):
        r = rf.backtest(dataset=self._dataset(), escribir=False)
        self.assertEqual(r["criterio"], rf.CRITERIO)
        self.assertIn("walk_forward", r)
        self.assertIn("modelo_final", r)
        self.assertIn("caidas_por_tramo", r)


class BloqueTests(unittest.TestCase):
    def _prediccion(self):
        partidos = [
            _p(1, "Real Madrid CF", "RC Celta de Vigo", (82, 10, 8), (78, 14, 8)),
            _p(2, "Sabah FA", "FC Barcelona", (18, 20, 62), (12, 18, 70), "2"),
            _p(3, "Getafe CF", "Sevilla FC", (40, 30, 30), (38, 30, 32), "1X"),
        ] + [_p(n, f"L{n}", f"V{n}", (45, 30, 25)) for n in range(4, 15)]
        masa = {1: {"1": 93, "X": 4, "2": 3}, 2: {"1": 10, "X": 15, "2": 75}}
        return {"jornada": 50, "partidos": partidos}, masa

    def test_bloque_rankea_y_nombra_uno(self):
        pred, masa = self._prediccion()
        bloque = rf.construir_bloque_ranker(pred, masa, fechas={}, fuentes=FUENTES_VACIAS, modelo=None, espanoles=ESP)
        self.assertEqual(bloque["estado"], "ok")
        self.assertEqual(bloque["modo"], "sombra")
        self.assertEqual(bloque["n_favoritos"], 2)
        self.assertEqual([f["puesto"] for f in bloque["ranking"]], [1, 2])
        self.assertEqual(bloque["origen_score"], "baseline_1_menos_p")
        # con baseline, el favorito menos probable (Barcelona 66%) va primero
        self.assertEqual(bloque["nombrado"]["num"], 2)
        self.assertEqual(bloque["nombrado"]["signo_si_cae"], "X")
        self.assertIn("nombrado", bloque["lectura"].lower())

    def test_bloque_con_modelo_usa_el_score(self):
        pred, masa = self._prediccion()
        modelo = {"media": [0.0] * len(rf.FEATURES), "desvio": [1.0] * len(rf.FEATURES), "intercepto": 0.0,
                  "coef": [0.0] * len(rf.FEATURES)}
        modelo["coef"][rf.FEATURES.index("favorito_local")] = 3.0  # el local es "mas arriesgado"
        bloque = rf.construir_bloque_ranker(pred, masa, fechas={}, fuentes=FUENTES_VACIAS, modelo=modelo, espanoles=ESP)
        self.assertEqual(bloque["origen_score"], "ranker_logistico")
        self.assertEqual(bloque["nombrado"]["num"], 1)

    def test_sin_favoritos_y_prediccion_incompleta(self):
        pred = {"jornada": 51, "partidos": [_p(n, f"L{n}", f"V{n}", (40, 30, 30)) for n in range(1, 15)]}
        b = rf.construir_bloque_ranker(pred, {}, fechas={}, fuentes=FUENTES_VACIAS, modelo=None, espanoles=ESP)
        self.assertEqual(b["estado"], "sin_favoritos")
        b2 = rf.construir_bloque_ranker({"jornada": 52, "partidos": []}, {}, fechas={}, fuentes=FUENTES_VACIAS, modelo=None)
        self.assertEqual(b2["estado"], "no_disponible")


class MarcadorTests(unittest.TestCase):
    def _escribir(self, tmp, jornada, resultados, estado_bloque="ok"):
        tmp = Path(tmp)
        (tmp / "pred").mkdir(exist_ok=True)
        (tmp / "jor").mkdir(exist_ok=True)
        ranking = [
            {"num": 1, "puesto": 1, "favorito": "1", "p_fav": 0.66, "signo_si_cae": "X"},
            {"num": 2, "puesto": 2, "favorito": "2", "p_fav": 0.75, "signo_si_cae": "X"},
            {"num": 3, "puesto": 3, "favorito": "1", "p_fav": 0.80, "signo_si_cae": "X"},
        ]
        bloque = {"estado": estado_bloque, "jornada": jornada, "ranking": ranking,
                  "nombrado": {**ranking[0]}}
        (tmp / "pred" / f"jornada_{jornada}.json").write_text(
            json.dumps({"jornada": jornada, "favoritos_en_riesgo": bloque}), encoding="utf-8")
        partidos = [{"num": n, "signo_oficial": resultados.get(n, "1")} for n in range(1, 15)]
        (tmp / "jor" / f"jornada_{jornada}.json").write_text(json.dumps({"jornada": jornada, "partidos": partidos}),
                                                             encoding="utf-8")

    def test_registra_evalua_y_es_idempotente(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._escribir(tmp, 7, {1: "X", 2: "2", 3: "2"})  # cae el nombrado (P1) y P3 (puesto 3)
            ahora = datetime(2026, 11, 26, tzinfo=timezone.utc)
            tmp = Path(tmp)
            r = rf.actualizar_marcador(tmp / "pred", tmp / "jor", tmp / "m.json", etiqueta="2026_2027", ahora=ahora)
            self.assertEqual(r["nuevas"], 1)
            reg = json.loads((tmp / "m.json").read_text(encoding="utf-8"))["registros"][0]
            self.assertTrue(reg["nombrado_cayo"])
            self.assertTrue(reg["nombrado_signo_si_cae_acierta"])
            self.assertEqual(reg["caidos"], 2)
            self.assertEqual([c["puesto"] for c in reg["caidos_detalle"]], [1, 3])
            self.assertEqual(reg["percentil_caidos"], 0.5)  # puestos 1 y 3 de 3 -> (0 + 1) / 2
            self.assertAlmostEqual(reg["nombrado_esperado"], 0.34, places=3)
            r2 = rf.actualizar_marcador(tmp / "pred", tmp / "jor", tmp / "m.json", etiqueta="2026_2027", ahora=ahora)
            self.assertEqual(r2["nuevas"], 0)
            self.assertEqual(len(json.loads((tmp / "m.json").read_text(encoding="utf-8"))["registros"]), 1)
            self.assertEqual(r2["resumen"]["veredicto"], "en_prueba")

    def test_jornada_abierta_no_se_registra(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._escribir(tmp, 8, {1: "Pendiente"})
            tmp = Path(tmp)
            r = rf.actualizar_marcador(tmp / "pred", tmp / "jor", tmp / "m.json", etiqueta="2026_2027")
            self.assertEqual(r["nuevas"], 0)
            self.assertEqual(json.loads((tmp / "m.json").read_text(encoding="utf-8"))["registros"], [])

    def test_bloque_no_ok_se_salta(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._escribir(tmp, 9, {}, estado_bloque="sin_favoritos")
            tmp = Path(tmp)
            r = rf.actualizar_marcador(tmp / "pred", tmp / "jor", tmp / "m.json", etiqueta="2026_2027")
            self.assertEqual(r["nuevas"], 0)

    def test_veredicto_prerregistrado(self):
        registros = [{"nombrado_cayo": True, "nombrado_esperado": 0.3, "n_favoritos": 3, "caidos": 1, "percentil_caidos": 0.0}
                     for _ in range(10)]
        self.assertEqual(rf.resumen_marcador(registros)["veredicto"], "candidata")
        registros = [{"nombrado_cayo": False, "nombrado_esperado": 0.3, "n_favoritos": 3, "caidos": 0, "percentil_caidos": None}
                     for _ in range(10)]
        self.assertEqual(rf.resumen_marcador(registros)["veredicto"], "despido")
        self.assertEqual(rf.resumen_marcador([])["veredicto"], "sin_datos")


if __name__ == "__main__":
    unittest.main()
