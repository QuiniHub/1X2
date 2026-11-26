"""Tests de la calculadora de EV del Elige 8 (26/11/2026): aritmetica P/coste/
break-even, tabla monotona, premio condicional, reglas de seleccion, bandera
de recomendacion y backtest prerregistrado sobre filas sinteticas."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import elige8_ev as ev


def _fijo(num, p, masa=None, signo="1"):
    """Partido con favorito `p` (fraccion) en el signo jugado; masa opcional."""
    resto = (1 - p) / 2
    probs = {s: resto * 100 for s in "1X2"}
    probs[signo] = p * 100
    partido = {"num": num, "local": f"L{num}", "visitante": f"V{num}", "probabilidades": probs, "signo_final": signo}
    m = None
    if masa is not None:
        m = {s: (1 - masa) / 2 * 100 for s in "1X2"}
        m[signo] = masa * 100
    return partido, m


def _prediccion(fijos, triples=(), dobles=()):
    partidos, masa = [], {}
    for num, p, m in fijos:
        pa, ma = _fijo(num, p, m)
        partidos.append(pa)
        if ma:
            masa[num] = ma
    for num in triples:
        partidos.append({"num": num, "local": f"L{num}", "visitante": f"V{num}",
                         "probabilidades": {"1": 40, "X": 30, "2": 30}, "signo_final": "1X2"})
        masa[num] = {"1": 40, "X": 30, "2": 30}
    for num in dobles:
        partidos.append({"num": num, "local": f"L{num}", "visitante": f"V{num}",
                         "probabilidades": {"1": 45, "X": 35, "2": 20}, "signo_final": "1X"})
        masa[num] = {"1": 50, "X": 30, "2": 20}
    return {"jornada": 99, "partidos": partidos}, masa


class AritmeticaTests(unittest.TestCase):
    def test_fixture_del_informe_dos_triples(self):
        fijos = [(i, p, p) for i, p in enumerate((0.80, 0.78, 0.77, 0.73, 0.73, 0.70), start=1)]
        pred, masa = _prediccion(fijos, triples=(7, 8), dobles=())
        for n in range(9, 15):
            pred["partidos"].append(_fijo(n, 0.5, 0.5)[0])
        prep = ev.preparar_partidos(pred, masa)
        r = ev.evaluar_seleccion(prep, range(1, 9))
        self.assertAlmostEqual(r["p_8de8"], 0.1792, places=3)
        self.assertEqual(r["apuestas"], 9)
        self.assertEqual(r["coste"], 4.50)
        self.assertEqual(r["break_even"], 25.11)

    def test_ocho_fijos_coste_minimo_y_doble(self):
        fijos = [(i, 0.7, 0.7) for i in range(1, 9)]
        pred, masa = _prediccion(fijos, dobles=(9,))
        prep = ev.preparar_partidos(pred, masa)
        r = ev.evaluar_seleccion(prep, range(1, 9))
        self.assertEqual(r["coste"], 0.50)
        self.assertAlmostEqual(r["p_8de8"], 0.7 ** 8, places=5)
        r2 = ev.evaluar_seleccion(prep, [1, 2, 3, 4, 5, 6, 7, 9])
        self.assertEqual(r2["coste"], 1.00)
        self.assertAlmostEqual(r2["p_8de8"], 0.7 ** 7 * 0.80, places=5)

    def test_mezcla_motor_losilla_y_edge(self):
        p = {"num": 1, "local": "A", "visitante": "B", "probabilidades": {"1": 70, "X": 20, "2": 10},
             "mercado_losilla": {"1": 60, "X": 25, "2": 15}, "signo_final": "1"}
        mix = ev.probs_mix(p)
        self.assertAlmostEqual(mix["1"], 0.65, places=6)
        prep = ev.preparar_partidos({"partidos": [p]}, {1: {"1": 80, "X": 12, "2": 8}})
        self.assertAlmostEqual(prep[0]["edge"], 0.65 / 0.80, places=2)
        self.assertEqual(prep[0]["fav_masa"], "1")
        self.assertEqual(prep[0]["fuente_masa"], "porcentajes_lae")


class TablaTests(unittest.TestCase):
    def test_pava_hace_monotona_la_tabla(self):
        tabla = ev.ajustar_monotono([(2, 1.8), (3, 50.0), (4, 5.0), (6, 800.0), (7, 20.0)])
        claves = sorted(tabla)
        valores = [tabla[k] for k in claves]
        self.assertEqual(valores, sorted(valores))
        self.assertLess(tabla[2], tabla[6])
        # 3 y 4 se funden (media geometrica), 6 y 7 tambien
        self.assertEqual(tabla[3], tabla[4])
        self.assertEqual(tabla[6], tabla[7])

    def test_consulta_fuera_de_rango_e_interpolacion(self):
        tabla = {2: 2.0, 4: 8.0}
        self.assertEqual(ev.premio_por_sorpresas(tabla, 0), 2.0)
        self.assertEqual(ev.premio_por_sorpresas(tabla, 9), 8.0)
        self.assertAlmostEqual(ev.premio_por_sorpresas(tabla, 3), 4.0, places=2)  # log-lineal
        self.assertIsNone(ev.premio_por_sorpresas({}, 3))

    def test_premio_condicional_muestrea_dentro_del_subconjunto(self):
        fijos = [(i, 0.9, 0.9) for i in range(1, 9)] + [(i, 0.5, 0.5) for i in range(9, 15)]
        pred, masa = _prediccion(fijos)
        prep = ev.preparar_partidos(pred, masa)
        tabla = {0: 1.0, 1: 10.0, 2: 100.0, 3: 1000.0}
        cond = ev.premio_condicional(prep, range(1, 9), tabla, muestras=500)
        # los 8 elegidos son fijos al favorito de la masa: condicionados aciertan siempre,
        # asi que las sorpresas solo pueden venir de los 6 libres (<= 6)
        self.assertTrue(all(int(k) <= 6 for k in cond["distribucion_sorpresas"]))
        self.assertGreater(cond["sorpresas_esperadas"], 2.0)
        self.assertLess(cond["sorpresas_esperadas"], 4.0)
        self.assertEqual(cond["muestras"], 500)
        # determinista con semilla
        self.assertEqual(cond, ev.premio_condicional(prep, range(1, 9), tabla, muestras=500))


class ReglasTests(unittest.TestCase):
    def _prep(self):
        # favoritos muy jugados (edge < 1) y partidos medios infrajugados (edge > 1)
        fijos = [(1, 0.75, 0.88), (2, 0.74, 0.86), (3, 0.72, 0.85), (4, 0.70, 0.80),
                 (5, 0.62, 0.55), (6, 0.60, 0.52), (7, 0.58, 0.50), (8, 0.57, 0.50),
                 (9, 0.55, 0.50), (10, 0.52, 0.50), (11, 0.50, 0.42), (12, 0.45, 0.35)]
        pred, masa = _prediccion(fijos, triples=(13,), dobles=(14,))
        return ev.preparar_partidos(pred, masa)

    def test_mas_probables_coincide_con_eficiencia(self):
        prep = self._prep()
        nums, _ = ev.seleccion_mas_probables(prep)
        self.assertEqual(nums, [1, 2, 3, 4, 5, 6, 7, 8])

    def test_edge_deja_fuera_a_los_favoritos_sobrejugados(self):
        prep = self._prep()
        nums, detalle = ev.seleccion_edge(prep)
        self.assertEqual(len(nums), 8)
        for n in (1, 2, 3, 4):
            self.assertNotIn(n, nums, f"P{n} tiene edge < 1 y hay 8 fijos con edge >= 1")
        self.assertNotIn(13, nums)  # el triple va en 'triples_dentro'
        self.assertNotIn(14, nums)  # solo fijos por defecto
        motivos = {d.get("motivo") for d in detalle if "motivo" in d}
        self.assertTrue(any(m.startswith("edge>=") for m in motivos))
        self.assertTrue(any(m.startswith("valor") for m in motivos))
        # orden por edge: el relleno solo aparece si faltan partidos con edge
        self.assertFalse(any("aviso" in d for d in detalle))

    def test_edge_rellena_y_avisa_si_no_hay_suficientes(self):
        fijos = [(i, 0.6, 0.8) for i in range(1, 15)]  # todos sobrejugados
        pred, masa = _prediccion(fijos)
        prep = ev.preparar_partidos(pred, masa)
        nums, detalle = ev.seleccion_edge(prep)
        self.assertEqual(len(nums), 8)
        self.assertTrue(any("aviso" in d for d in detalle))

    def test_triples_dentro_cubre_los_multiples(self):
        prep = self._prep()
        nums, _ = ev.seleccion_triples_dentro(prep)
        self.assertIn(13, nums)
        self.assertIn(14, nums)
        r = ev.evaluar_seleccion(prep, nums)
        self.assertEqual(r["apuestas"], 6)
        self.assertEqual(r["coste"], 3.00)


class BanderaTests(unittest.TestCase):
    def _prep(self):
        fijos = [(i, 0.8, 0.8) for i in range(1, 9)] + [(i, 0.5, 0.5) for i in range(9, 15)]
        pred, masa = _prediccion(fijos)
        return ev.preparar_partidos(pred, masa)

    def test_no_recomendado_si_premio_bajo_break_even(self):
        prep = self._prep()
        r = ev.evaluar_regla(prep, range(1, 9), {0: 1.8, 6: 2.5}, muestras=300)
        self.assertAlmostEqual(r["p_8de8"], 0.8 ** 8, places=4)
        self.assertFalse(r["recomendado"])
        self.assertIn("no_recomendado", r["motivo"])
        self.assertIn("break-even", r["motivo"])
        self.assertLess(r["ev"], 0)

    def test_recomendado_si_ev_positivo(self):
        prep = self._prep()
        r = ev.evaluar_regla(prep, range(1, 9), {0: 50.0, 6: 50.0}, muestras=300)
        self.assertTrue(r["recomendado"])
        self.assertGreater(r["ev"], 0)
        self.assertGreater(r["p_8de8"] * r["premio_esperado"], r["coste"])

    def test_sin_tabla_no_hay_ev(self):
        prep = self._prep()
        r = ev.evaluar_regla(prep, range(1, 9), {}, muestras=10)
        self.assertIsNone(r["ev"])
        self.assertFalse(r["recomendado"])

    def test_evaluar_jornada_incluye_seleccion_actual_y_reglas(self):
        fijos = [(i, 0.7, 0.7) for i in range(1, 15)]
        pred, masa = _prediccion(fijos)
        pred["elige8_seguro"] = {"seleccionados": [1, 2, 3, 4, 5, 6, 7, 8]}
        r = ev.evaluar_jornada(pred, masa, {0: 5.0, 7: 50.0}, muestras=200)
        self.assertEqual(r["estado"], "ok")
        for clave in ("actual_elige8_seguro", "mas_probables", "edge", "triples_dentro"):
            self.assertIn(clave, r["reglas"])
        self.assertIn("bandera_recomendado_publicable", r)
        self.assertIn("modo_sorpresas", r)


class BacktestTests(unittest.TestCase):
    def test_backtest_sintetico_escribe_criterio_y_veredicto(self):
        filas = []
        for k in range(6):
            fijos = [(i, 0.9, 0.9) for i in range(1, 9)] + [(i, 0.5, 0.5) for i in range(9, 15)]
            pred, masa = _prediccion(fijos)
            prep = ev.preparar_partidos(pred, masa)
            # resultados: los 8 favoritos aciertan; k sorpresas entre los 6 libres
            reales = {n: "1" for n in range(1, 15)}
            for n in range(9, 9 + k):
                reales[n] = "2"
            filas.append({"jornada": 100 + k, "fecha": f"2026-10-{10 + k:02d}", "tipo": "domestica", "prep": prep,
                          "reales": reales, "n_sorpresas": ev.n_sorpresas(prep, reales),
                          "n_sorpresas_top8": ev.n_sorpresas(prep, reales, ev.relevantes_top8(prep)),
                          "premio": 2.0 * (3 ** k), "acertantes": 100})
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "bt.json"
            r = ev.backtest(filas=filas, muestras=100, ruta_salida=ruta)
            self.assertTrue(ruta.exists())
        self.assertEqual(r["criterio"], ev.CRITERIO_BACKTEST)
        self.assertIn(r["veredicto"], ("DESPLEGAR_BANDERA", "NO_DESPLEGAR"))
        self.assertEqual(len(r["jornadas"]), 6)
        self.assertEqual(r["por_regla"]["mas_probables"]["aciertos_8de8"], 6)
        self.assertEqual(r["por_regla"]["mas_probables"]["coste"], 3.0)
        self.assertIn("tabla_premio_por_sorpresas", r)
        self.assertIn("exploratorio_top8", r)
        self.assertIn("edge_no_pierde_mas_que_mas_probables", r["chequeos"])

    def test_backtest_sin_filas(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = ev.backtest(filas=[], ruta_salida=Path(tmp) / "bt.json")
        self.assertEqual(r["veredicto"], "SIN_DATOS")


if __name__ == "__main__":
    unittest.main()
