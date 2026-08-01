import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aplicar_elige8_seguro import aplicar_elige8_seguro, probabilidad_acierto_elige8, eficiencia_elige8


def partido(num, top=62.0, sorpresa=20.0, indice=20.0):
    return {
        "num": num,
        "local": f"Local {num}",
        "visitante": f"Visitante {num}",
        "signo_final": "1",
        "signo_base": "1",
        "probabilidades": {"1": top, "X": 22.0, "2": 16.0},
        "incertidumbre": 55.0,
        "probabilidad_sorpresa": sorpresa,
        "indice_sorpresa_quinielistica": indice,
        "calidad_datos": "alta",
        "cobertura_sorpresa_sugerida": "FIJO",
    }


class Elige8ModosTests(unittest.TestCase):
    def test_bloqueo_conserva_estado_bloqueada(self):
        prediccion = {
            "estado": "bloqueada",
            "prediccion_disponible": False,
            "partidos": [partido(i) for i in range(1, 15)],
        }

        aplicar_elige8_seguro(prediccion)

        self.assertEqual(prediccion["estado"], "bloqueada")
        self.assertFalse(prediccion["publicar_prediccion"])
        self.assertTrue(prediccion["publicar_solo_boleto"])

    def test_crea_modos_conservador_y_rentable(self):
        prediccion = {
            "estado": "lista_para_publicar",
            "prediccion_disponible": True,
            "configuracion": {"elige8": True},
            "partidos": [partido(i) for i in range(1, 15)],
        }

        aplicar_elige8_seguro(prediccion)

        self.assertEqual(prediccion["configuracion"]["elige8_modo"], "conservador")
        self.assertEqual(prediccion["configuracion"]["elige8_modos_disponibles"], ["conservador", "rentable"])
        self.assertIn("conservador", prediccion["elige8_modos"]["modos"])
        self.assertIn("rentable", prediccion["elige8_modos"]["modos"])
        self.assertEqual(len(prediccion["elige8_modos"]["modos"]["conservador"]["seleccionados"]), 8)
        self.assertEqual(len(prediccion["elige8_modos"]["modos"]["rentable"]["seleccionados"]), 8)
        self.assertTrue(all("confianza_real" in item for item in prediccion["elige8_modos"]["modos"]["conservador"]["ranking"]))


class ProbabilidadAciertoElige8Tests(unittest.TestCase):
    """probabilidad_acierto_elige8 sigue siendo la probabilidad GENUINA de
    cobertura (correcta para mostrar: un triple de verdad garantiza ese
    resultado) -no toca su semantica, solo confirma que no cambio."""

    def test_triple_cubre_100_por_ciento_de_verdad(self):
        triple_reñido = {
            "signo_final": "1X2",
            "probabilidades": {"1": 34.1, "X": 31.1, "2": 34.8},
        }
        self.assertAlmostEqual(probabilidad_acierto_elige8(triple_reñido), 100.0)

    def test_fijo_devuelve_su_propia_probabilidad(self):
        fijo_solido = {
            "signo_final": "1",
            "probabilidades": {"1": 58.3, "X": 23.4, "2": 18.3},
        }
        self.assertAlmostEqual(probabilidad_acierto_elige8(fijo_solido), 58.3)


class EficienciaElige8Tests(unittest.TestCase):
    """Caso real: jornada 75, P1 (VPS-Inter Turku) triple con empate casi
    perfecto a 3 bandas vs P2 (TPS-Mariehamn) fijo con favorito solido.
    Antes del fix, el ranking usaba probabilidad_acierto_elige8 directamente
    y el triple (100% de cobertura "gratis") ganaba siempre a cualquier
    fijo, sin importar lo reñido que estuviera -justo lo que la regla 1
    (feedback_metodo_prediccion_manual.md) dice que no hay que asumir.
    eficiencia_elige8 descuenta el coste real (multiplicador x2/x3) antes
    de comparar."""

    def test_triple_reñido_no_rankea_mas_alto_que_fijo_solido(self):
        triple_reñido = {
            "signo_final": "1X2",
            "probabilidades": {"1": 34.1, "X": 31.1, "2": 34.8},
        }
        fijo_solido = {
            "signo_final": "1",
            "probabilidades": {"1": 58.3, "X": 23.4, "2": 18.3},
        }

        eficiencia_triple = eficiencia_elige8(triple_reñido)
        eficiencia_fijo = eficiencia_elige8(fijo_solido)

        self.assertAlmostEqual(eficiencia_triple, 100.0 / 3, places=2)
        self.assertAlmostEqual(eficiencia_fijo, 58.3)
        self.assertGreater(eficiencia_fijo, eficiencia_triple)

    def test_doble_flojo_no_rankea_mas_alto_que_fijo_solido(self):
        doble_contra_gran_favorito = {
            "signo_final": "1X",
            "probabilidades": {"1": 10.0, "X": 14.0, "2": 76.0},
        }
        fijo_solido = {
            "signo_final": "1",
            "probabilidades": {"1": 62.0, "X": 22.0, "2": 16.0},
        }

        eficiencia_doble = eficiencia_elige8(doble_contra_gran_favorito)
        eficiencia_fijo = eficiencia_elige8(fijo_solido)

        self.assertAlmostEqual(eficiencia_doble, 12.0)
        self.assertGreater(eficiencia_fijo, eficiencia_doble)

    def test_doble_muy_solido_si_puede_rankear_mas_alto_que_fijo_debil(self):
        """Un doble genuinamente fuerte (90% cubierto) SI puede ganarle a un
        fijo debil (40%) pese al coste x2 -no es "nunca doble", es "el
        doble tiene que compensar de verdad el coste extra"."""
        doble_fuerte = {
            "signo_final": "1X",
            "probabilidades": {"1": 60.0, "X": 30.0, "2": 10.0},
        }
        fijo_debil = {
            "signo_final": "1",
            "probabilidades": {"1": 40.0, "X": 32.0, "2": 28.0},
        }

        eficiencia_doble = eficiencia_elige8(doble_fuerte)
        eficiencia_fijo = eficiencia_elige8(fijo_debil)

        self.assertAlmostEqual(eficiencia_doble, 45.0)
        self.assertAlmostEqual(eficiencia_fijo, 40.0)
        self.assertGreater(eficiencia_doble, eficiencia_fijo)


if __name__ == "__main__":
    unittest.main()
