import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor_prediccion_quiniela import (
    cobertura_automatica,
    coste,
    indice_sorpresa_quinielistica,
    prioridad_doble,
)


def partido(num, probs, incertidumbre=120, sorpresa=60):
    return {
        "num": num,
        "local": f"Local {num}",
        "visitante": f"Visitante {num}",
        "probabilidades": probs,
        "incertidumbre": incertidumbre,
        "probabilidad_sorpresa": sorpresa,
    }


def equipo_competitivo(nombre, estado, motivacion="baja", vivos=None):
    return {
        "equipo": nombre,
        "motivacion_competitiva": motivacion,
        "objetivos": [{"objetivo": "permanencia", "estado": estado}],
        "objetivos_vivos": vivos if vivos is not None else [],
    }


class MotorPrediccionTests(unittest.TestCase):
    def test_coste_elige8_es_por_apuesta(self):
        resultado = coste(dobles=2, triples=1, elige8=True)

        self.assertEqual(resultado["apuestas"], 12)
        self.assertEqual(resultado["importe_quiniela"], 9.0)
        self.assertEqual(resultado["importe_elige8"], 6.0)
        self.assertEqual(resultado["importe_total"], 15.0)

    def test_cobertura_automatica_evitar_14_fijos_en_jornada_abierta(self):
        evaluados = [
            partido(i, {"1": 35.0, "X": 34.0, "2": 31.0})
            for i in range(1, 15)
        ]

        dobles, triples, detalle = cobertura_automatica(evaluados)

        self.assertGreaterEqual(dobles, 4)
        self.assertGreaterEqual(triples, 1)
        self.assertIn("Cobertura automatica", detalle)

    def test_cobertura_automatica_respeta_boleto_sencillo_si_no_hay_riesgo(self):
        evaluados = [
            partido(i, {"1": 72.0, "X": 18.0, "2": 10.0}, incertidumbre=45, sorpresa=20)
            for i in range(1, 15)
        ]

        dobles, triples, detalle = cobertura_automatica(evaluados)

        self.assertEqual(dobles, 0)
        self.assertEqual(triples, 0)
        self.assertIn("boleto sencillo", detalle)

    def test_indice_sorpresa_detecta_favorito_atacable(self):
        evaluado = partido(1, {"1": 56.0, "X": 24.0, "2": 20.0}, incertidumbre=104, sorpresa=48)
        evaluado["contexto_competitivo_local"] = equipo_competitivo(
            "Local 1",
            "asegurado_matematicamente",
        )
        evaluado["contexto_competitivo_visitante"] = equipo_competitivo(
            "Visitante 1",
            "riesgo_descenso",
            "maxima",
            vivos=[{"objetivo": "permanencia", "estado": "riesgo_descenso"}],
        )
        evaluado["_local"] = {"racha_actual": {"sin_ganar": 3}, "tendencias": {"goles_contra_por_partido": 1.6}}
        evaluado["_visitante"] = {"racha_actual": {"sin_perder": 3}, "tendencias": {"goles_favor_por_partido": 1.4}}
        patrones = {
            "patrones": {
                "visitante_descenso_vs_local_favorito": {"tasa_sorpresa": 70},
                "visitante_necesitado_vs_local_objetivo_cerrado": {"tasa_sorpresa": 60},
                "equipo_necesitado_vs_equipo_sin_objetivo": {"tasa_sorpresa": 65},
            }
        }

        indice = indice_sorpresa_quinielistica(evaluado, patrones)

        self.assertGreaterEqual(indice["indice"], 60)
        self.assertTrue(indice["favorito_atacable"])
        self.assertEqual(indice["favorito"], "1")
        self.assertEqual(indice["cobertura_sugerida"], "DOBLE")
        self.assertIn("X", indice["signos_contra_favorito"])

    def test_prioridad_doble_prioriza_favorito_atacable(self):
        favorito_atacable = partido(1, {"1": 56.0, "X": 24.0, "2": 20.0}, incertidumbre=104, sorpresa=48)
        favorito_atacable["contexto_competitivo_local"] = equipo_competitivo(
            "Local 1",
            "asegurado_matematicamente",
        )
        favorito_atacable["contexto_competitivo_visitante"] = equipo_competitivo(
            "Visitante 1",
            "riesgo_descenso",
            "maxima",
            vivos=[{"objetivo": "permanencia", "estado": "riesgo_descenso"}],
        )
        favorito_atacable["_indice_sorpresa_quinielistica"] = indice_sorpresa_quinielistica(favorito_atacable)

        abierto_generico = partido(2, {"1": 42.0, "X": 31.0, "2": 27.0}, incertidumbre=104, sorpresa=48)
        abierto_generico["_indice_sorpresa_quinielistica"] = indice_sorpresa_quinielistica(abierto_generico)

        self.assertGreater(prioridad_doble(favorito_atacable), prioridad_doble(abierto_generico))


if __name__ == "__main__":
    unittest.main()
