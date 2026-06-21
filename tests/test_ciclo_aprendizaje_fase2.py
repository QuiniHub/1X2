import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import construir_memoria_ia
from contrato_aprendizaje import (
    fiabilidad_equipos,
    metricas_probabilisticas,
    revisar_partido,
    upsert_validacion_generada,
)
from motor_prediccion_quiniela import (
    ajustar_por_diario_aprendizaje,
    ajustar_por_fiabilidad_equipos,
    ajustar_por_pesos_dinamicos,
)


def prediccion_jornada():
    partidos = []
    for num in range(1, 15):
        partidos.append({
            "num": num,
            "local": f"Local {num}",
            "visitante": f"Visitante {num}",
            "probabilidades": {"1": 62.0, "X": 23.0, "2": 15.0},
            "signo_base": "1",
            "signo_final": "1" if num != 2 else "1X",
            "tipo": "FIJO" if num != 2 else "DOBLE",
            "incertidumbre": 48,
            "categoria_sorpresa": "baja",
            "favorito": "1",
            "favorito_nombre": f"Local {num}",
            "elige8": num <= 8,
        })
    return {
        "jornada": 99,
        "temporada": "2025/2026",
        "competicion": "quiniela",
        "generado_en": "2026-06-20T10:00:00+00:00",
        "partidos": partidos,
    }


class CicloAprendizajeFase2Tests(unittest.TestCase):
    def test_upsert_persiste_prediccion_ia_en_json_intermedio(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "quinielas_generadas_ia.json"

            actualizado, motivo = upsert_validacion_generada(prediccion_jornada(), destino)
            repetido, motivo_repetido = upsert_validacion_generada(prediccion_jornada(), destino)

            data = json.loads(destino.read_text(encoding="utf-8"))
            self.assertTrue(actualizado)
            self.assertEqual(motivo, "actualizada")
            self.assertFalse(repetido)
            self.assertEqual(motivo_repetido, "sin_cambios")
            self.assertEqual(len(data["jugadas"]), 1)
            self.assertEqual(len(data["jugadas"][0]["signos"]), 14)
            self.assertEqual(data["jugadas"][0]["origen"], "prediccion_ia_json")

    def test_cargador_aprendizaje_usa_generadas_ia_sin_pisar_manual(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            manual = base / "quinielas_jugadas.json"
            generada = base / "quinielas_generadas_ia.json"
            historial = base / "historial_quinielas.json"
            manual.write_text(json.dumps({
                "jugadas": [{"jornada": 99, "signos": ["1"] * 14, "origen": "manual"}]
            }), encoding="utf-8")
            generada.write_text(json.dumps({
                "jugadas": [{"jornada": 100, "signos": ["X"] * 14, "origen": "prediccion_ia_json"}]
            }), encoding="utf-8")
            historial.write_text(json.dumps({"jornadas": []}), encoding="utf-8")

            anteriores = (
                construir_memoria_ia.QUINIELAS_JUGADAS,
                construir_memoria_ia.QUINIELAS_GENERADAS_IA,
                construir_memoria_ia.HISTORIAL_QUINIELAS_JSON,
            )
            try:
                construir_memoria_ia.QUINIELAS_JUGADAS = manual
                construir_memoria_ia.QUINIELAS_GENERADAS_IA = generada
                construir_memoria_ia.HISTORIAL_QUINIELAS_JSON = historial
                jugadas = construir_memoria_ia.cargar_quinielas_jugadas()
            finally:
                (
                    construir_memoria_ia.QUINIELAS_JUGADAS,
                    construir_memoria_ia.QUINIELAS_GENERADAS_IA,
                    construir_memoria_ia.HISTORIAL_QUINIELAS_JSON,
                ) = anteriores

            self.assertEqual(jugadas[99]["origen"], "manual")
            self.assertEqual(jugadas[100]["origen"], "prediccion_ia_json")

    def test_revision_calcula_metricas_probabilisticas_y_sorpresa(self):
        pred = prediccion_jornada()["partidos"][0]
        revision_ok = revisar_partido(
            99,
            {"num": 1, "local": "Local 1", "visitante": "Visitante 1", "resultado": "2-0"},
            pred,
            pronostico="1",
            origen="test",
        )
        revision_fallo = revisar_partido(
            99,
            {"num": 2, "local": "Local 2", "visitante": "Visitante 2", "resultado": "0-1"},
            {**prediccion_jornada()["partidos"][1], "categoria_sorpresa": "alta"},
            pronostico="1X",
            origen="test",
        )

        metricas = metricas_probabilisticas([revision_ok, revision_fallo])

        self.assertTrue(revision_ok["acierto"])
        self.assertFalse(revision_fallo["acierto"])
        self.assertEqual(revision_fallo["ranking_signo_real"], 3)
        self.assertGreater(revision_fallo["brier_score"], 1.0)
        self.assertEqual(metricas["accuracy_top1"], 50.0)
        self.assertEqual(metricas["accuracy_top2"], 50.0)
        self.assertEqual(metricas["accuracy_sorpresas"]["total"], 1)

    def test_fiabilidad_equipos_resume_accuracy_y_favoritos(self):
        revisiones = [
            revisar_partido(
                99,
                {"num": 1, "local": "Equipo A", "visitante": "Equipo B", "resultado": "2-0"},
                {"num": 1, "local": "Equipo A", "visitante": "Equipo B", "probabilidades": {"1": 70, "X": 20, "2": 10}, "signo_final": "1", "favorito": "1"},
                pronostico="1",
            ),
            revisar_partido(
                100,
                {"num": 1, "local": "Equipo A", "visitante": "Equipo C", "resultado": "0-1"},
                {"num": 1, "local": "Equipo A", "visitante": "Equipo C", "probabilidades": {"1": 65, "X": 20, "2": 15}, "signo_final": "1", "favorito": "1", "categoria_sorpresa": "alta"},
                pronostico="1",
            ),
        ]

        fiabilidad = fiabilidad_equipos(revisiones)
        equipo = fiabilidad["equipos"]["Equipo A"]

        self.assertEqual(equipo["partidos_evaluados"], 2)
        self.assertEqual(equipo["aciertos"], 1)
        self.assertEqual(equipo["fallos"], 1)
        self.assertEqual(equipo["fallos_como_favorito"], 1)
        self.assertEqual(equipo["accuracy_global"], 50.0)

    def test_pesos_dinamicos_explicados_y_usados_por_motor(self):
        pesos = {
            "referencia": {
                "forma_reciente": 0.20,
                "casa_fuera": 0.15,
                "clasificacion": 0.16,
                "goles": 0.12,
                "empate": 0.10,
                "sorpresa": 0.09,
                "motivacion_competitiva": 0.07,
                "necesidad_descenso_ascenso_europa": 0.07,
                "fatiga": 0.02,
                "bajas": 0.02,
            },
            "pesos": {
                "forma_reciente": 0.24,
                "casa_fuera": 0.18,
                "clasificacion": 0.18,
                "goles": 0.14,
                "empate": 0.14,
                "sorpresa": 0.13,
                "motivacion_competitiva": 0.09,
                "necesidad_descenso_ascenso_europa": 0.09,
                "fatiga": 0.04,
                "bajas": 0.04,
            },
        }
        local_stats = {
            "posicion": 2,
            "pj": 10,
            "gf": 20,
            "gc": 8,
            "local": {"pj": 5, "pts": 12},
            "tendencias": {"forma_5_pts": 12, "forma_10_pts": 20},
        }
        visitante_stats = {
            "posicion": 12,
            "pj": 10,
            "gf": 9,
            "gc": 16,
            "visitante": {"pj": 5, "pts": 4},
            "tendencias": {"forma_5_pts": 5, "forma_10_pts": 12},
        }
        contexto = {"alertas": ["fatiga", "lesiones"]}

        probs, riesgo, lecturas, aplicaciones = ajustar_por_pesos_dinamicos(
            {"1": 50.0, "X": 28.0, "2": 22.0},
            pesos,
            {"motivacion_competitiva": "alta", "objetivos_vivos": [{"objetivo": "europa"}]},
            {},
            contexto,
            {},
            local_stats,
            visitante_stats,
        )

        pesos_usados = {item["peso"] for item in aplicaciones}
        self.assertIn("forma_reciente", pesos_usados)
        self.assertIn("casa_fuera", pesos_usados)
        self.assertIn("clasificacion", pesos_usados)
        self.assertIn("goles", pesos_usados)
        self.assertIn("empate", pesos_usados)
        self.assertIn("sorpresa", pesos_usados)
        self.assertIn("motivacion_competitiva/necesidad_descenso_ascenso_europa", pesos_usados)
        self.assertIn("fatiga", pesos_usados)
        self.assertIn("bajas", pesos_usados)
        self.assertGreater(riesgo, 0)
        self.assertNotEqual(probs["1"], 50.0)
        self.assertTrue(lecturas)

    def test_memoria_nueva_influye_en_siguiente_prediccion(self):
        probs_fiabilidad, riesgo_fiabilidad, lecturas_fiabilidad = ajustar_por_fiabilidad_equipos(
            {"1": 58.0, "X": 25.0, "2": 17.0},
            {"equipos": {"Local 1": {"partidos_evaluados": 8, "accuracy_global": 35, "nivel_fiabilidad_motor": "baja"}}},
            "Local 1",
            "Visitante 1",
        )
        probs_diario, riesgo_diario, lecturas_diario = ajustar_por_diario_aprendizaje(
            {"1": 58.0, "X": 25.0, "2": 17.0},
            {"entradas": [{"partido": "1. Local 1 - Visitante 1", "acierto": False, "categoria_fallo": "empate_no_cubierto"}]},
            "Local 1",
            "Visitante 1",
        )

        self.assertLess(probs_fiabilidad["1"], 58.0)
        self.assertGreater(riesgo_fiabilidad, 0)
        self.assertTrue(lecturas_fiabilidad)
        self.assertGreater(probs_diario["X"], 25.0)
        self.assertGreater(riesgo_diario, 0)
        self.assertTrue(lecturas_diario)


if __name__ == "__main__":
    unittest.main()
