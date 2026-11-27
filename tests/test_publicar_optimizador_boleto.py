"""Tests del publicador del optimizador de boleto (26/11/2026)."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import publicar_optimizador_boleto as pub


class ResumenBacktestTests(unittest.TestCase):
    def test_resumen_lee_las_claves_reales(self):
        r = pub.resumen_backtest()
        # el JSON del backtest existe en el repo: las claves mapeadas deben venir con valor
        self.assertEqual(r["variante_publicada"], "P13plus")
        self.assertIsNotNone(r["nuestro_premio_eur"])
        self.assertIsNotNone(r["variante_trece_o_mas"])
        # el veredicto bruto va aparte; el campo que pinta la web lleva ademas el
        # aviso de que P13plus se eligio a posteriori (auditoria 26/11/2026)
        self.assertIn(r["veredicto_variante_publicada_bruto"], ("supera", "no supera"))
        self.assertTrue(r["veredicto_variante_publicada"].startswith(r["veredicto_variante_publicada_bruto"]))
        self.assertIn("a posteriori", r["veredicto_variante_publicada"])


class BloqueTests(unittest.TestCase):
    def test_bloque_con_prediccion_real_o_no_disponible(self):
        bloque = pub.construir_bloque()
        self.assertIn(bloque["estado"], ("ok", "no_disponible"))
        self.assertEqual(bloque["modo"], "sombra")
        if bloque["estado"] == "ok":
            self.assertEqual(len(bloque["signos"]), 14)
            self.assertEqual(bloque["columnas"], pub.PRESUPUESTO_PRINCIPAL)
            cols = 1
            for s in bloque["signos"]:
                cols *= len(s)
            self.assertLessEqual(cols, pub.PRESUPUESTO_PRINCIPAL)
            self.assertEqual(set(bloque["alternativas_por_presupuesto"]), {str(p) for p in pub.PRESUPUESTOS_ALTERNATIVOS})
            self.assertTrue(0 <= bloque["P13plus"] <= 1)


if __name__ == "__main__":
    unittest.main()
