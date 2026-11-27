"""Auditoria 26/11/2026, paquete P7 (hallazgos 1, 30 y 181).

alinear_boleto_con_analisis.py volvia a repartir dobles y triples con un
criterio distinto del motor y ponia en el doble los dos signos mas probables:
quitaba la X de la cobertura de autor y borraba la X de autor de los fijos.
El unico dueno del reparto es el motor; este script solo toca textos y coste.
"""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import alinear_boleto_con_analisis as aba
import validar_publicacion_autonoma as vpa


def partido(num, signo_final="1", tipo=None, probs=None, **extra):
    probs = probs or {"1": 60.0, "X": 25.0, "2": 15.0}
    base = max(probs, key=probs.get)
    datos = {
        "num": num, "local": f"L{num}", "visitante": f"V{num}",
        "probabilidades": probs, "signo_base": base,
        "signo_final": signo_final,
        "tipo": tipo or {1: "FIJO", 2: "DOBLE", 3: "TRIPLE"}[len(signo_final)],
        "cobertura_sorpresa_sugerida": "FIJO",
        "indice_sorpresa_quinielistica": 10.0,
        "x_de_autor": {"activo": False},
        "cobertura_autor": {"activo": False},
        "elige8": False,
    }
    datos.update(extra)
    return datos


def boleto_del_motor():
    """Boleto como lo deja el motor en la J25 real (27/11/2026): triple en el
    13, dobles en 5, 7, 10 y 11, y el 7 (Celta-Villarreal) con la X de autor."""
    partidos = [partido(n) for n in range(1, 15)]
    # P7: 1=32.0, X=30.5, 2=37.4 -> los dos mas probables son 1 y 2, pero el
    # motor pone X2 por la cobertura de autor (Celta empatador).
    partidos[6] = partido(
        7, "X2", probs={"1": 32.0, "X": 30.5, "2": 37.4},
        cobertura_sorpresa_sugerida="TRIPLE", indice_sorpresa_quinielistica=100.0,
        cobertura_autor={"activo": True, "cubierta": True, "razon": "COBERTURA DE AUTOR: Celta es empatador."},
    )
    # P10: la sugerencia dice TRIPLE y el indice es el maximo; el motor lo deja en doble.
    partidos[9] = partido(
        10, "1X", probs={"1": 34.5, "X": 33.4, "2": 32.2},
        cobertura_sorpresa_sugerida="TRIPLE", indice_sorpresa_quinielistica=100.0,
        cobertura_autor={"activo": True, "cubierta": True, "razon": "COBERTURA DE AUTOR: Tenerife es empatador."},
    )
    partidos[12] = partido(13, "1X2", probs={"1": 33.0, "X": 30.6, "2": 36.3},
                           cobertura_sorpresa_sugerida="TRIPLE", indice_sorpresa_quinielistica=90.0)
    partidos[4] = partido(5, "1X", probs={"1": 50.0, "X": 29.6, "2": 20.4})
    partidos[10] = partido(11, "1X", probs={"1": 51.1, "X": 28.9, "2": 20.0})
    # P8: fijo con X de autor (signo_base 1, el motor se atreve con la X).
    partidos[7] = partido(8, "X", tipo="FIJO", probs={"1": 38.0, "X": 36.0, "2": 26.0},
                          x_de_autor={"activo": True, "razon": "X DE AUTOR: X pegada al maximo y hay empatador."})
    for num in (1, 2, 3, 4, 6, 9, 12, 14):
        partidos[num - 1]["elige8"] = True
    return {
        "jornada": 25,
        "partidos": partidos,
        "configuracion": {"dobles": 4, "triples": 1, "elige8": True},
        "criterio_cobertura": "Criterio del motor.",
    }


class AlinearRespetaAlMotorTests(unittest.TestCase):
    def setUp(self):
        self.original = boleto_del_motor()
        self.alineado = aba.alinear_prediccion(copy.deepcopy(self.original))

    def test_no_cambia_ningun_signo_ni_tipo(self):
        antes = {p["num"]: (p["tipo"], p["signo_final"]) for p in self.original["partidos"]}
        despues = {p["num"]: (p["tipo"], p["signo_final"]) for p in self.alineado["partidos"]}
        self.assertEqual(antes, despues)

    def test_el_doble_con_cobertura_de_autor_conserva_la_x(self):
        p7 = self.alineado["partidos"][6]
        self.assertEqual(p7["tipo"], "DOBLE")
        self.assertTrue(p7["cobertura_autor"]["activo"])
        self.assertIn("X", p7["signo_final"])
        self.assertEqual(p7["signo_final"], "X2")

    def test_la_x_de_autor_del_fijo_no_se_borra(self):
        p8 = self.alineado["partidos"][7]
        self.assertEqual((p8["tipo"], p8["signo_final"]), ("FIJO", "X"))
        self.assertTrue(p8["x_de_autor"]["activo"])

    def test_no_recoloca_el_triple_aunque_la_sugerencia_diga_otra_cosa(self):
        tipos = {p["num"]: p["tipo"] for p in self.alineado["partidos"]}
        self.assertEqual(tipos[13], "TRIPLE")
        self.assertEqual(tipos[10], "DOBLE")
        self.assertEqual(self.alineado["resumen"]["triples"], 1)
        self.assertEqual(self.alineado["resumen"]["dobles"], 4)

    def test_conserva_el_criterio_de_cobertura_del_motor(self):
        self.assertEqual(self.alineado["criterio_cobertura"], "Criterio del motor.")

    def test_los_textos_siguen_pasando_el_validador(self):
        for p in self.alineado["partidos"]:
            self.assertEqual(vpa.validar_razonamiento(p), [], p["num"])
        self.assertIn("Cobertura de autor", self.alineado["partidos"][6]["razonamiento"])

    def test_el_boleto_alineado_no_tiene_incoherencias(self):
        criticos, tolerados = vpa.invariantes_boleto(self.alineado)
        self.assertEqual(criticos, [])
        self.assertEqual(tolerados, [])

    def test_es_idempotente(self):
        otra_vez = aba.alinear_prediccion(copy.deepcopy(self.alineado))
        self.assertEqual(otra_vez, self.alineado)


class CosteTests(unittest.TestCase):
    def test_apuestas_salen_de_los_signos(self):
        coste = aba.alinear_prediccion(boleto_del_motor())["coste"]
        self.assertEqual(coste["apuestas"], 48)  # 2^4 * 3
        self.assertEqual(coste["importe_quiniela"], 36.0)

    def test_elige8_se_cobra_solo_sobre_los_8_elegidos(self):
        # Hallazgo 181: 8 fijos elegidos = 1 apuesta de Elige 8 (0,50), no 48.
        coste = aba.alinear_prediccion(boleto_del_motor())["coste"]
        self.assertEqual(coste["apuestas_elige8"], 1)
        self.assertEqual(coste["importe_elige8"], 0.5)
        self.assertEqual(coste["importe_total"], 36.5)

    def test_elige8_con_un_doble_y_un_triple_dentro(self):
        pred = boleto_del_motor()
        for p in pred["partidos"]:
            p["elige8"] = p["num"] in (1, 2, 3, 4, 5, 6, 9, 13)
        coste = aba.alinear_prediccion(pred)["coste"]
        self.assertEqual(coste["apuestas_elige8"], 6)  # doble (5) x triple (13)
        self.assertEqual(coste["importe_elige8"], 3.0)

    def test_sin_elige8_configurado_no_se_cobra(self):
        pred = boleto_del_motor()
        pred["configuracion"]["elige8"] = False
        coste = aba.alinear_prediccion(pred)["coste"]
        self.assertEqual(coste["importe_elige8"], 0)
        self.assertEqual(coste["importe_total"], 36.0)

    def test_prediccion_retenida_no_inventa_signos_ni_coste(self):
        pred = {
            "jornada": 25,
            "partidos": [{"num": n, "local": "A", "visitante": "B", "signo_final": "", "signo_base": ""}
                         for n in range(1, 15)],
            "configuracion": {"dobles": 0, "triples": 0, "elige8": False},
        }
        salida = aba.alinear_prediccion(pred)
        self.assertTrue(all(p["signo_final"] == "" for p in salida["partidos"]))
        self.assertTrue(all("tipo" not in p for p in salida["partidos"]))
        self.assertEqual(salida["coste"]["apuestas"], 0)
        self.assertEqual(salida["coste"]["importe_total"], 0)


if __name__ == "__main__":
    unittest.main()
