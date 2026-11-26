"""Tests de calibracion_x (Laboratorio 26/11/2026): franjas, desvigado, reparto a 100,
encogimiento, guardia walk-forward sin fuga de futuro y no-op con veredicto NO_DESPLEGAR."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import calibracion_x as cx

ESP = {"real madrid", "fc barcelona", "sevilla", "betis", "valencia", "getafe", "osasuna", "alaves"}


def _escribir(ruta, datos):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")


def _fixture_snapshots(base, jornadas):
    """jornadas: [(num, creado_en, [(local, visitante, (p1,px,p2), signo_real)])]."""
    snaps = base / "pre_cierre"
    jor = base / "jornadas"
    for num, creado, partidos in jornadas:
        pred = {"jornada": num, "partidos": []}
        reales = {"jornada": num, "partidos": []}
        for i, (local, visitante, probs, real) in enumerate(partidos, start=1):
            pred["partidos"].append({"num": i, "local": local, "visitante": visitante,
                                     "probabilidades": dict(zip("1X2", probs)),
                                     "mercado_losilla": {"1": 50.0, "X": 25.0, "2": 25.0}, "calidad_datos": "baja",
                                     "ajuste_mercado_losilla": {"lecturas": ["consenso integrado con peso 0.65 (calidad_datos=baja)"]}})
            reales["partidos"].append({"num": i, "signo_oficial": real})
        _escribir(snaps / f"jornada_{num}.json", {"jornada": num, "creado_en": creado, "prediccion": pred})
        _escribir(jor / f"jornada_{num}.json", reales)
    return snaps, jor


def _historico(n_por_signo=3):
    partidos = []
    for signo in "1X2":
        for _ in range(n_por_signo):
            partidos.append({"fecha": "2024-01-01", "local": "A", "visitante": "B", "signo": signo,
                             "cuota_1": 2.1, "cuota_x": 3.3, "cuota_2": 3.6})
    partidos.append({"fecha": "2024-01-01", "local": "A", "visitante": "B", "signo": "1", "cuota_1": None})
    return {"ligas": {"primera": {"temporadas": {"2023/2024": {"partidos": partidos}}},
                      "segunda": {"temporadas": {"2023/2024": partidos[:3]}}}}


class FranjasTests(unittest.TestCase):
    def test_limites_de_franja(self):
        self.assertEqual(cx.franja_de(39.9), "<40")
        self.assertEqual(cx.franja_de(40.0), "40-50")
        self.assertEqual(cx.franja_de(59.99), "50-60")
        self.assertEqual(cx.franja_de(60.0), "60-65")
        self.assertEqual(cx.franja_de(65.0), "65-80")
        self.assertEqual(cx.franja_de(79.99), "65-80")
        self.assertEqual(cx.franja_de(80.0), ">=80")
        self.assertEqual(cx.franja_de(100.0), ">=80")

    def test_acepta_fraccion_y_etiqueta(self):
        self.assertEqual(cx.franja_de(0.7), "65-80")
        self.assertEqual(cx.franja_de("40-50"), "40-50")
        self.assertIsNone(cx.franja_de("rara"))
        self.assertIsNone(cx.franja_de(None))

    def test_favorito_es_el_maximo_de_1_y_2(self):
        self.assertAlmostEqual(cx.prob_favorito_pct({"1": 20, "X": 20, "2": 60}), 60.0)
        self.assertAlmostEqual(cx.prob_favorito_pct({"1": 0.7, "X": 0.2, "2": 0.1}), 70.0)


class DevigTests(unittest.TestCase):
    CUOTAS = (2.10, 3.30, 3.60)

    def test_los_tres_conversores_suman_1(self):
        for nombre, fn in cx.METODOS_DEVIG.items():
            p = fn(self.CUOTAS)
            self.assertAlmostEqual(sum(p.values()), 1.0, places=9, msg=nombre)

    def test_power_recorta_mas_la_x_que_el_multiplicativo(self):
        mult = cx.devig_multiplicativo(self.CUOTAS)
        power = cx.devig_power(self.CUOTAS)
        self.assertLess(power["X"], mult["X"])
        self.assertGreater(power["1"], mult["1"])

    def test_cuotas_invalidas(self):
        self.assertIsNone(cx.devig_multiplicativo((0, 3.3, 3.6)))
        self.assertIsNone(cx.devig_power(("a", 3.3, 3.6)))
        self.assertIsNone(cx.devig_power((0.9, 3.3, 3.6)))


class MetricasTests(unittest.TestCase):
    def test_rps_y_logloss_perfectos_y_uniformes(self):
        perfecto = [{"probs": {"1": 1.0, "X": 0.0, "2": 0.0}, "y": "1"}]
        self.assertAlmostEqual(cx.rps(perfecto), 0.0)
        uniforme = [{"probs": {"1": 1 / 3, "X": 1 / 3, "2": 1 / 3}, "y": "X"}]
        self.assertAlmostEqual(cx.log_loss(uniforme), 1.0986, places=3)
        self.assertAlmostEqual(cx.rps(uniforme), ((1 / 3) ** 2 + (1 / 3) ** 2) / 2)
        self.assertIsNone(cx.rps([]))

    def test_intervalo_poisson_binomial(self):
        iv = cx.intervalo_x([0.5] * 100, 50)
        self.assertEqual(iv["esperadas"], 50.0)
        self.assertTrue(38 <= iv["lo"] <= 41)
        self.assertTrue(59 <= iv["hi"] <= 62)
        self.assertTrue(iv["dentro"])
        fuera = cx.intervalo_x([0.5] * 100, 80)
        self.assertFalse(fuera["dentro"])
        self.assertLess(fuera["p_valor"], 0.001)
        self.assertTrue(cx.intervalo_x([], 0)["dentro"])


class AplicarFactorTests(unittest.TestCase):
    def test_reparte_proporcional_y_cierra_a_100(self):
        out = cx.aplicar_factor({"1": 60.0, "X": 20.0, "2": 20.0}, 1.5)
        self.assertAlmostEqual(out["X"], 30.0, places=2)
        self.assertAlmostEqual(sum(out.values()), 100.0, places=2)
        # el 1 y el 2 siguen en la proporcion 3:1
        self.assertAlmostEqual(out["1"] / out["2"], 3.0, places=2)

    def test_factor_1_no_cambia_y_escala_fraccion(self):
        out = cx.aplicar_factor({"1": 0.6, "X": 0.2, "2": 0.2}, 1.0)
        self.assertAlmostEqual(out["X"], 0.2)
        self.assertAlmostEqual(sum(out.values()), 1.0)

    def test_tope_de_x(self):
        out = cx.aplicar_factor({"1": 10.0, "X": 80.0, "2": 10.0}, 2.0)
        self.assertLessEqual(out["X"], 95.0)
        self.assertAlmostEqual(sum(out.values()), 100.0, places=2)


class TablaFactoresTests(unittest.TestCase):
    def _items(self, n, p_x, x_obs, comp="domestica", franja="65-80"):
        return [{"franja": franja, "competicion": comp, "p_x": p_x, "y": "X" if i < x_obs else "1"} for i in range(n)]

    def test_encoge_hacia_1_con_pocos_datos(self):
        # 10 partidos, 5 X observadas con p_x 0.25 -> bruto 2.0; con K=20 el factor queda en 1 + 1.0*10/30
        tabla = cx.tabla_factores(self._items(10, 0.25, 5))
        f = tabla["domestica"]["65-80"]
        self.assertEqual(f["n"], 10)
        self.assertAlmostEqual(f["factor_bruto"], 2.0)
        self.assertAlmostEqual(f["factor"], 1.3333, places=3)
        self.assertEqual(tabla["no_domestica"]["65-80"]["factor"], 1.0)
        self.assertEqual(tabla["domestica"]["<40"], {"n": 0, "x_obs": 0, "x_pred": 0.0, "factor_bruto": 1.0, "factor": 1.0})

    def test_mucha_muestra_se_acerca_al_bruto_y_recorta(self):
        tabla = cx.tabla_factores(self._items(2000, 0.10, 1000))
        self.assertEqual(tabla["domestica"]["65-80"]["factor"], cx.FACTOR_MAX)
        tabla = cx.tabla_factores(self._items(2000, 0.5, 0))
        self.assertEqual(tabla["domestica"]["65-80"]["factor"], cx.FACTOR_MIN)


class WalkForwardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        # la jornada 70 se creo ANTES que la 69: el orden debe ser cronologico, no por numero
        self.snaps, self.jor = _fixture_snapshots(base, [
            (69, "2026-06-20T00:00:00", [("Arsenal", "Dortmund", (70, 20, 10), "X"), ("Sevilla", "Betis", (45, 30, 25), "1")]),
            (70, "2026-06-16T00:00:00", [("PSG", "Inter", (50, 25, 25), "X"), ("Valencia", "Getafe", (38, 32, 30), "X")]),
            (1, "2026-08-11T00:00:00", [("Real Madrid", "Osasuna", (75, 15, 10), "1"), ("Alaves", "Sevilla", (40, 30, 30), "Pendiente")]),
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def test_orden_cronologico_y_partidos_pendientes_fuera(self):
        jornadas = cx.cargar_snapshots(self.snaps, self.jor, espanoles=ESP)
        self.assertEqual([j["jornada"] for j in jornadas], [70, 69, 1])
        self.assertEqual(len(jornadas[2]["partidos"]), 1)  # el Pendiente no cuenta
        p = jornadas[1]["partidos"][0]
        self.assertTrue(p["extranjero"])
        self.assertEqual(p["competicion"], "no_domestica")
        self.assertFalse(jornadas[1]["partidos"][1]["extranjero"])
        self.assertEqual(p["peso_mercado"], 0.65)
        self.assertEqual(p["franja"], "65-80")

    def test_guardia_sin_fuga_de_futuro(self):
        jornadas = cx.cargar_snapshots(self.snaps, self.jor, espanoles=ESP)
        # para la primera jornada (70) no hay historia: todo factor 1
        t0 = cx.tabla_factores_hasta(jornadas, jornadas[0]["orden"])
        self.assertTrue(all(f["n"] == 0 for comp in t0.values() for f in comp.values()))
        # para la 69 solo entra la 70 (2 partidos), nunca la propia 69 ni la 1
        t1 = cx.tabla_factores_hasta(jornadas, jornadas[1]["orden"])
        self.assertEqual(sum(f["n"] for comp in t1.values() for f in comp.values()), 2)
        self.assertEqual(t1["no_domestica"]["50-60"]["n"], 1)
        self.assertEqual(t1["domestica"]["<40"]["n"], 1)
        wf = cx.backtest_walk_forward(jornadas)
        self.assertEqual([d["n_historia"] for d in wf["por_jornada"]], [0, 2, 4])
        self.assertEqual(wf["por_jornada"][0]["log_loss_sin"], wf["por_jornada"][0]["log_loss_con"])
        self.assertEqual(wf["n"], 5)

    def test_ejecutar_prerregistra_y_conserva_criterios(self):
        base = Path(self.tmp.name)
        hist = base / "historico.json"
        _escribir(hist, _historico())
        salida_ruta = base / "out" / "backtest_calibracion_x.json"
        # criterios ya existentes en disco: deben conservarse tal cual
        _escribir(salida_ruta, {"criterios_prerregistrados": {"descripcion": "CRITERIO ORIGINAL", "fecha": "2026-11-26"}})
        salida = cx.ejecutar(salida_ruta, self.snaps, self.jor, hist)
        self.assertEqual(salida["criterios_prerregistrados"]["descripcion"], "CRITERIO ORIGINAL")
        en_disco = json.loads(salida_ruta.read_text(encoding="utf-8"))
        self.assertIn(en_disco["veredicto"], ("DESPLEGAR", "NO_DESPLEGAR"))
        self.assertEqual(en_disco["historico_cuotas"]["n"], 12)
        self.assertEqual(set(en_disco["historico_cuotas"]["metodos"]), {"multiplicativo", "shin", "power"})
        self.assertEqual(en_disco["snapshots"]["n_partidos"], 5)
        self.assertIn("tabla_factores", en_disco)
        self.assertEqual(en_disco["estado"], "con_resultados")


class CalibrarXTests(unittest.TestCase):
    TABLA = {"domestica": {"65-80": {"factor": 1.25}}, "no_domestica": {"65-80": {"factor": 0.8}}}
    PROBS = {"1": 70.0, "X": 20.0, "2": 10.0}

    def test_no_op_si_no_desplegar(self):
        out, traza = cx.calibrar_x_con_traza(self.PROBS, tabla=self.TABLA, veredicto="NO_DESPLEGAR")
        self.assertEqual(out, self.PROBS)
        self.assertFalse(traza["activo"])
        self.assertIn("no-op", traza["motivo"])
        self.assertEqual(cx.calibrar_x(self.PROBS, tabla=self.TABLA, veredicto="NO_DESPLEGAR"), self.PROBS)

    def test_activo_si_desplegar_y_franja_deducida(self):
        out, traza = cx.calibrar_x_con_traza(self.PROBS, tabla=self.TABLA, veredicto="DESPLEGAR")
        self.assertTrue(traza["activo"])
        self.assertEqual(traza["franja"], "65-80")
        self.assertAlmostEqual(out["X"], 25.0, places=2)
        self.assertAlmostEqual(sum(out.values()), 100.0, places=2)
        self.assertAlmostEqual(out["1"] / out["2"], 7.0, places=2)

    def test_competicion_europea_y_forzar(self):
        out = cx.calibrar_x(self.PROBS, competicion="europea", tabla=self.TABLA, veredicto="DESPLEGAR")
        self.assertAlmostEqual(out["X"], 16.0, places=2)
        out2, traza = cx.calibrar_x_con_traza(self.PROBS, prob_favorito_bin="65-80", tabla=self.TABLA,
                                              veredicto="NO_DESPLEGAR", forzar=True)
        self.assertTrue(traza["activo"])
        self.assertIn("forzado", traza["motivo"])
        self.assertAlmostEqual(out2["X"], 25.0, places=2)

    def test_franja_sin_factor_es_no_op(self):
        out, traza = cx.calibrar_x_con_traza({"1": 40, "X": 30, "2": 30}, tabla=self.TABLA, veredicto="DESPLEGAR")
        self.assertFalse(traza["activo"])
        self.assertEqual(out["X"], 30.0)


if __name__ == "__main__":
    unittest.main()
