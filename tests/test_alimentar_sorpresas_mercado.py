import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import alimentar_sorpresas_mercado as asm


class EsEntradaEsquemaActualTests(unittest.TestCase):
    def test_entrada_esquema_actual_se_conserva(self):
        entrada = {"jornada": 74, "num_partido": 3, "categoria_sorpresa": "desconocido"}
        self.assertTrue(asm.es_entrada_esquema_actual(entrada))

    def test_entrada_del_otro_escritor_se_conserva(self):
        # Auditoria 26/11: 'numero_partido' NO es un esquema antiguo: es la
        # clave con la que escribe actualizar_aprendizaje_ia en el mismo ciclo.
        entrada = {"jornada": 69, "numero_partido": 12, "categoria_sorpresa": "racha_rota"}
        self.assertTrue(asm.es_entrada_esquema_actual(entrada))
        self.assertEqual(asm.normalizar_entrada(dict(entrada, temporada="2025_2026"))["num_partido"], 12)

    def test_entrada_sin_ningun_identificador_se_descarta(self):
        self.assertFalse(asm.es_entrada_esquema_actual({"categoria_sorpresa": "desconocido"}))


class InferirCategoriaYAlertasTests(unittest.TestCase):
    def test_detecta_derbi_por_nombre_de_equipos(self):
        categoria, alertas = asm.inferir_categoria_y_alertas("", False, "Real Madrid", "Barcelona")
        self.assertEqual(categoria, asm.CAT_DERBI)
        self.assertIn("derbi_todo_puede_pasar", alertas)

    def test_detecta_motivacional_por_riesgo_necesidad(self):
        categoria, alertas = asm.inferir_categoria_y_alertas("", True, "Equipo A", "Equipo B")
        self.assertEqual(categoria, asm.CAT_MOTIVACIONAL)

    def test_sin_senales_cae_en_desconocido(self):
        categoria, alertas = asm.inferir_categoria_y_alertas("", False, "Equipo A", "Equipo B")
        self.assertEqual(categoria, asm.CAT_DESCONOCIDO)
        self.assertEqual(alertas, [])


if __name__ == "__main__":
    unittest.main()
