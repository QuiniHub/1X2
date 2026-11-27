"""Tests del revisor de boleto (27/11/2026): cada regla de reglas_boleto.json
se aplica de verdad a un boleto."""
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import revisar_boleto as rb

REGLAS = rb.cargar_reglas()


def _pred(mercados, sorpresa=None):
    partidos = []
    for k in range(1, 15):
        m = mercados.get(k, {"1": 60, "X": 25, "2": 15})
        partidos.append({"num": k, "local": f"L{k}", "visitante": f"V{k}", "probabilidades": m, "mercado_losilla": m})
    pred = {"jornada": 99, "partidos": partidos}
    if sorpresa:
        pred["sorpresa_nombrada"] = {"estado": "ok", "num": sorpresa[0], "signo": sorpresa[1]}
    return pred


def _rev(signos, pred, **kw):
    kw.setdefault("fechas", {})
    kw.setdefault("europea", False)
    kw.setdefault("calendario", [])
    return rb.revisar(signos, pred, reglas=REGLAS, **kw)


def _ids(res):
    return [a["regla"] for a in res["avisos"]]


class ReglasTests(unittest.TestCase):
    def test_fichero_de_reglas_cargado(self):
        for clave in ("R01_doble_1x_por_costumbre", "R02_favorito_mercado_fuera", "R03_cubrir_lo_que_se_nombra",
                      "R04_fijo_local_racha_casa", "R07_presupuesto_y_bote"):
            self.assertIn(clave, REGLAS)

    def test_favorito_del_mercado_fuera(self):
        pred = _pred({7: {"1": 32, "X": 30, "2": 38}})
        res = _rev("1 1 1 1 1 1 1X 1 1 1 1 1 1 1", pred)
        self.assertIn("R02_favorito_mercado_fuera", _ids(res))
        res2 = _rev("1 1 1 1 1 1 X2 1 1 1 1 1 1 1", pred)
        self.assertNotIn("R02_favorito_mercado_fuera", _ids(res2))

    def test_doble_1x_que_deberia_ser_12_y_todos_1x(self):
        pred = _pred({8: {"1": 47, "X": 28, "2": 25}, 5: {"1": 50, "X": 35, "2": 15}})
        res = _rev("1 1 1 1 1X 1 1 1X 1 1 1 1 1 1", pred)
        mensajes = [a for a in res["avisos"] if a["regla"] == "R01_doble_1x_por_costumbre"]
        self.assertTrue(any(a.get("partido") == 8 for a in mensajes))       # 12 cubre mas con el 2 corregido
        self.assertFalse(any(a.get("partido") == 5 for a in mensajes))      # aqui la X manda
        self.assertTrue(any(a.get("partido") is None for a in mensajes))    # todos los dobles son 1X

    def test_sorpresa_nombrada_sin_cubrir(self):
        pred = _pred({}, sorpresa=(9, "X"))
        self.assertIn("R03_cubrir_lo_que_se_nombra", _ids(_rev("1 1 1 1 1 1 1 1 1 1 1 1 1 1", pred)))
        self.assertNotIn("R03_cubrir_lo_que_se_nombra", _ids(_rev("1 1 1 1 1 1 1 1 1X 1 1 1 1 1", pred)))
        res = _rev("1 1 1 1 1 1 1 1 1X 1 1 1 1 1", pred, sorpresas_extra=[(8, "2")])
        self.assertIn("R03_cubrir_lo_que_se_nombra", _ids(res))

    def test_doble_del_sabado(self):
        pred = _pred({11: {"1": 50, "X": 30, "2": 20}})
        res = _rev("1 1 1 1 1 1 1 1 1 1 1X 1 1 1", pred, fechas={11: date(2026, 11, 28)})
        self.assertIn("R06_dobles_del_sabado", _ids(res))
        res2 = _rev("1 1 1 1 1 1 1 1 1 1 1X 1 1 1", pred, fechas={11: date(2026, 11, 29)})
        self.assertNotIn("R06_dobles_del_sabado", _ids(res2))

    def test_local_en_racha_en_casa_cubierto_de_mas(self):
        cal = [{"fecha": date(2026, 10, d), "kl": rb_clave("L1"), "kv": "x", "gl": 2, "gv": 0} for d in (1, 8, 15, 22, 29)]
        pred = _pred({1: {"1": 70, "X": 19, "2": 11}})
        res = _rev("1X 1 1 1 1 1 1 1 1 1 1 1 1 1", pred, fechas={1: date(2026, 11, 28)}, calendario=cal)
        self.assertIn("R04_fijo_local_racha_casa", _ids(res))

    def test_presupuesto_y_bote(self):
        pred = _pred({})
        res = _rev("1X2 1X2 1X2 1 1 1 1 1 1 1 1 1 1 1", pred, presupuesto=18)
        self.assertIn("R07_presupuesto_y_bote", _ids(res))
        self.assertEqual(res["apuestas"], 27)
        res2 = _rev("1X2 1X2 1X2 1X 1X 1X 1 1 1 1 1 1 1 1", pred, apuestas=24, presupuesto=18)
        self.assertNotIn("R07_presupuesto_y_bote", _ids(res2))

    def test_elige8_en_europa(self):
        self.assertIn("R08_elige8_europa", _ids(_rev("1 1 1 1 1 1 1 1 1 1 1 1 1 1", _pred({}), elige8=True, europea=True)))

    def test_signos_mal_formados(self):
        with self.assertRaises(ValueError):
            rb.normalizar_signos("1 1 1")
        self.assertEqual(rb.normalizar_signos("1 x2 21 1 1 1 1 1 1 1 1 1 1 1")[1:3], ["X2", "12"])


def rb_clave(nombre):
    from modelo_dixon_coles import clave_equipo
    return clave_equipo(nombre)


if __name__ == "__main__":
    unittest.main()
