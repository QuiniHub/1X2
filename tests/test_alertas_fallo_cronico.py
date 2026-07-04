import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_todo as at


class AlertaFalloCronicoTests(unittest.TestCase):
    def setUp(self):
        self._ruta_original = at.HISTORIAL_FALLOS
        at.HISTORIAL_FALLOS = ROOT / "data" / "_test_diagnostico_fallos_cronicos.json"
        if at.HISTORIAL_FALLOS.exists():
            at.HISTORIAL_FALLOS.unlink()

    def tearDown(self):
        if at.HISTORIAL_FALLOS.exists():
            at.HISTORIAL_FALLOS.unlink()
        at.HISTORIAL_FALLOS = self._ruta_original

    def test_fallos_por_debajo_del_umbral_no_alertan(self):
        salida = io.StringIO()
        with redirect_stdout(salida):
            for _ in range(at.UMBRAL_FALLO_CRONICO - 1):
                at.registrar_resultado_script("script_x.py", False)
        self.assertNotIn("ALERTA_FALLO_CRONICO", salida.getvalue())
        historial = at.cargar_historial_fallos()
        self.assertEqual(
            historial["script_x.py"]["fallos_consecutivos"],
            at.UMBRAL_FALLO_CRONICO - 1,
        )

    def test_alcanzar_el_umbral_dispara_la_alerta(self):
        salida = io.StringIO()
        with redirect_stdout(salida):
            for _ in range(at.UMBRAL_FALLO_CRONICO):
                at.registrar_resultado_script("script_y.py", False)
        self.assertIn("ALERTA_FALLO_CRONICO", salida.getvalue())
        self.assertIn("script_y.py", salida.getvalue())

    def test_un_exito_limpia_el_historial_de_ese_script(self):
        for _ in range(at.UMBRAL_FALLO_CRONICO):
            at.registrar_resultado_script("script_z.py", False)
        self.assertIn("script_z.py", at.cargar_historial_fallos())

        at.registrar_resultado_script("script_z.py", True)
        self.assertNotIn("script_z.py", at.cargar_historial_fallos())

    def test_scripts_distintos_no_se_mezclan(self):
        at.registrar_resultado_script("script_a.py", False)
        at.registrar_resultado_script("script_b.py", False)
        at.registrar_resultado_script("script_b.py", False)
        historial = at.cargar_historial_fallos()
        self.assertEqual(historial["script_a.py"]["fallos_consecutivos"], 1)
        self.assertEqual(historial["script_b.py"]["fallos_consecutivos"], 2)


if __name__ == "__main__":
    unittest.main()
