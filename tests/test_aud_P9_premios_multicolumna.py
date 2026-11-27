"""Auditoria 26/11, hallazgo 252.

tests/test_calcular_premios_origen.py tiene un test llamado
'test_el_calculo_multicolumna_con_esta_tabla_da_el_premio_real' que suma el
total a mano dentro del propio test: no ejecuta calcular_premio_multicolumna.
Estos tests SI llaman a la funcion de produccion, con la tabla real de la J70
(los importes que publico la fuente) y boletos pequenos cuyo desglose se
puede comprobar a mano.

Sin red y sin tocar data/: la funcion es pura.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import calcular_premios as cp


# Importes reales de la J70 (los mismos del HTML de test_calcular_premios_origen)
TABLA_J70 = {"15": 17119.56, "14": 3043.48, "13": 63.17, "12": 8.77,
             "11": 2.03, "10": 0.0, "elige8": 25.73}


def _boleto(jugadas):
    """jugadas: lista de 14 cadenas ('1', '1X', '1X2'...)."""
    tipos = {1: "FIJO", 2: "DOBLE", 3: "TRIPLE"}
    return {"partidos": [
        {"num": i, "signo_final": signos, "tipo": tipos[len(signos)]}
        for i, signos in enumerate(jugadas, start=1)
    ]}


def _oficial(signos):
    return {"partidos": [{"num": i, "signo_oficial": s} for i, s in enumerate(signos, start=1)]}


class PremioMulticolumnaTests(unittest.TestCase):
    def test_dos_dobles_y_un_triple_se_desglosan_columna_a_columna(self):
        # 11 fijos acertados + doble '1X' (acierta 1 de 2) + doble 'X2'
        # (no acierta) + triple (acierta 1 de 3): 2*2*3 = 12 columnas.
        #   13 aciertos: 1*2*1 = 2 columnas
        #   12 aciertos: 1*2*2 + 1*2*1 = 6 columnas
        #   11 aciertos: 1*2*2 = 4 columnas
        boleto = _boleto(["1"] * 11 + ["1X", "X2", "1X2"])
        r = cp.calcular_premio_multicolumna(boleto, _oficial(["1"] * 14), TABLA_J70)
        self.assertEqual(r["columnas_totales"], 12)
        self.assertEqual(r["distribucion_aciertos"], {"13": 2, "12": 6, "11": 4})
        self.assertEqual(r["desglose"]["13"]["columnas"], 2)
        self.assertEqual(r["desglose"]["12"]["subtotal"], 52.62)
        # 2*63,17 + 6*8,77 + 4*2,03
        self.assertEqual(r["total"], 187.08)

    def test_el_elige8_se_suma_una_sola_vez_y_no_por_columna(self):
        boleto = _boleto(["1"] * 11 + ["1X", "X2", "1X2"])
        r = cp.calcular_premio_multicolumna(boleto, _oficial(["1"] * 14), TABLA_J70, gano_elige8=True)
        self.assertEqual(r["total"], round(187.08 + 25.73, 2))
        self.assertEqual(r["desglose"]["elige8"]["columnas"], 1)

    def test_categoria_sin_premio_no_entra_en_el_desglose(self):
        # 10 fijos acertados y 4 fallados: una sola columna de 10, que en la
        # J70 pagaba 0,00 EUR -> no hay premio.
        boleto = _boleto(["1"] * 14)
        oficial = _oficial(["1"] * 10 + ["2"] * 4)
        self.assertIsNone(cp.calcular_premio_multicolumna(boleto, oficial, TABLA_J70))

    def test_columna_unica_de_catorce(self):
        r = cp.calcular_premio_multicolumna(_boleto(["X"] * 14), _oficial(["X"] * 14), TABLA_J70)
        self.assertEqual(r["columnas_totales"], 1)
        self.assertEqual(r["total"], 3043.48)

    def test_boleto_grande_por_convolucion_da_lo_mismo_que_contar_a_mano(self):
        # 7 fijos acertados + 7 triples = 2187 columnas (> 2000: rama de
        # convolucion). Con k triples acertados hay C(7,k)*2^(7-k) columnas:
        #   14: 1   13: 14   12: 84   11: 280   10: 560 ...
        boleto = _boleto(["1"] * 7 + ["1X2"] * 7)
        r = cp.calcular_premio_multicolumna(boleto, _oficial(["1"] * 14), TABLA_J70)
        self.assertEqual(r["columnas_totales"], 2187)
        self.assertEqual(sum(r["distribucion_aciertos"].values()), 2187)
        self.assertEqual(r["distribucion_aciertos"]["14"], 1)
        self.assertEqual(r["distribucion_aciertos"]["13"], 14)
        self.assertEqual(r["distribucion_aciertos"]["12"], 84)
        self.assertEqual(r["distribucion_aciertos"]["11"], 280)
        # 3043,48 + 14*63,17 + 84*8,77 + 280*2,03
        self.assertEqual(r["total"], 5232.94)

    def test_partido_sin_signo_oficial_no_cuenta_ni_multiplica_columnas(self):
        boleto = _boleto(["1"] * 13 + ["1X2"])
        oficial = _oficial(["1"] * 13 + ["Pendiente"])
        r = cp.calcular_premio_multicolumna(boleto, oficial, TABLA_J70)
        self.assertEqual(r["columnas_totales"], 1)
        self.assertEqual(r["distribucion_aciertos"], {"13": 1})

    def test_sin_tabla_o_sin_partidos_devuelve_none(self):
        self.assertIsNone(cp.calcular_premio_multicolumna(_boleto(["1"] * 14), _oficial(["1"] * 14), {}))
        self.assertIsNone(cp.calcular_premio_multicolumna({"partidos": []}, _oficial(["1"] * 14), TABLA_J70))


if __name__ == "__main__":
    unittest.main()
