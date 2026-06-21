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


def prediccion_jornada(jornada=99, local_base="Local"):
    partidos = []
    for num in range(1, 15):
        partidos.append({
            "num": num,
            "local": f"{local_base} {num}",
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
        "jornada": jornada,
        "temporada": "2025/2026",
        "competicion": "quiniela",
        "generado_en": "2026-06-20T10:00:00+00:00",
        "partidos": partidos,
    }


def prediccion_memoria(jornada):
    prediccion = prediccion_jornada(jornada=jornada, local_base="Equipo Memoria")
    prediccion["generado_en"] = f"2026-06-20T10:{jornada % 60:02d}:00+00:00"
    for partido in prediccion["partidos"]:
        num = int(partido["num"])
        partido.update({
            "local": "Equipo Memoria",
            "visitante": f"Rival {jornada}-{num}",
            "probabilidades": {"1": 64.0, "X": 22.0, "2": 14.0},
            "signo_base": "1",
            "signo_final": "1",
            "tipo": "FIJO",
            "incertidumbre": 52,
            "categoria_sorpresa": "alta" if num <= 10 else "baja",
            "indice_sorpresa_quinielistica": 72 if num <= 10 else 20,
            "probabilidad_sorpresa": 64 if num <= 10 else 20,
            "favorito": "1",
            "favorito_nombre": "Equipo Memoria",
            "favorito_atacable": num <= 10,
            "elige8": num <= 8,
        })
    return prediccion


def jornada_resultados_desde_prediccion(prediccion):
    partidos = []
    for partido in prediccion["partidos"]:
        num = int(partido["num"])
        fallo = num <= 10
        partidos.append({
            "num": num,
            "local": partido["local"],
            "visitante": partido["visitante"],
            "resultado": "0-1" if fallo else "2-0",
            "signo_oficial": "2" if fallo else "1",
        })
    return {
        "jornada": prediccion["jornada"],
        "fecha": "2026-06-20",
        "partidos": partidos,
        "pleno15": {"resultado": "1"},
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

    def test_flujo_end_to_end_tempdir_predice_persiste_aprende_y_reusa_memoria(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data = base / "data"
            jornadas = data / "jornadas"
            predicciones = data / "predicciones"
            memoria = data / "memoria_ia"
            jornadas.mkdir(parents=True)
            predicciones.mkdir(parents=True)
            memoria.mkdir(parents=True)

            generadas = data / "quinielas_generadas_ia.json"
            (data / "quinielas_jugadas.json").write_text(json.dumps({"jugadas": []}), encoding="utf-8")
            (data / "historial_quinielas.json").write_text(json.dumps({"jornadas": []}), encoding="utf-8")

            for jornada in (201, 202):
                prediccion = prediccion_memoria(jornada)
                upsert_validacion_generada(prediccion, generadas)
                (predicciones / f"jornada_{jornada}.json").write_text(
                    json.dumps(prediccion, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                (jornadas / f"jornada_{jornada}.json").write_text(
                    json.dumps(jornada_resultados_desde_prediccion(prediccion), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )

            anteriores = {
                "JORNADAS_QUINIELA": construir_memoria_ia.JORNADAS_QUINIELA,
                "QUINIELAS_JUGADAS": construir_memoria_ia.QUINIELAS_JUGADAS,
                "QUINIELAS_GENERADAS_IA": construir_memoria_ia.QUINIELAS_GENERADAS_IA,
                "HISTORIAL_QUINIELAS_JSON": construir_memoria_ia.HISTORIAL_QUINIELAS_JSON,
                "PREDICCIONES": construir_memoria_ia.PREDICCIONES,
                "PESOS_DINAMICOS": construir_memoria_ia.PESOS_DINAMICOS,
            }
            try:
                construir_memoria_ia.JORNADAS_QUINIELA = jornadas
                construir_memoria_ia.QUINIELAS_JUGADAS = data / "quinielas_jugadas.json"
                construir_memoria_ia.QUINIELAS_GENERADAS_IA = generadas
                construir_memoria_ia.HISTORIAL_QUINIELAS_JSON = data / "historial_quinielas.json"
                construir_memoria_ia.PREDICCIONES = predicciones
                construir_memoria_ia.PESOS_DINAMICOS = memoria / "pesos_dinamicos.json"

                resumen = construir_memoria_ia.analizar_nuestras_quinielas()
                diario = resumen.pop("_diario_aprendizaje")
                revisiones = resumen.pop("_revisiones_contrato")
                metricas = metricas_probabilisticas(revisiones)
                pesos = construir_memoria_ia.construir_pesos_dinamicos({"nuestras_quinielas": resumen}, diario)
                fiabilidad = fiabilidad_equipos(revisiones)
            finally:
                for nombre, valor in anteriores.items():
                    setattr(construir_memoria_ia, nombre, valor)

            (memoria / "diario_aprendizaje.json").write_text(
                json.dumps({"version": "1.0", "generado_en": "test", "total_entradas": len(diario), "entradas": diario}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (memoria / "metricas_probabilisticas.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")
            (memoria / "pesos_dinamicos.json").write_text(json.dumps(pesos, ensure_ascii=False, indent=2), encoding="utf-8")
            (memoria / "fiabilidad_equipos.json").write_text(json.dumps(fiabilidad, ensure_ascii=False, indent=2), encoding="utf-8")

            self.assertEqual(len(revisiones), 28)
            self.assertEqual(metricas["partidos_evaluados"], 28)
            self.assertEqual(pesos["muestra"]["partidos_validados"], 28)
            self.assertIn("Equipo Memoria", fiabilidad["equipos"])
            self.assertLess(fiabilidad["equipos"]["Equipo Memoria"]["accuracy_global"], 45)

            fiabilidad_leida = json.loads((memoria / "fiabilidad_equipos.json").read_text(encoding="utf-8"))
            diario_leido = json.loads((memoria / "diario_aprendizaje.json").read_text(encoding="utf-8"))
            pesos_leidos = json.loads((memoria / "pesos_dinamicos.json").read_text(encoding="utf-8"))

            probs_base = {"1": 58.0, "X": 25.0, "2": 17.0}
            probs_fiabilidad, riesgo_fiabilidad, lecturas_fiabilidad = ajustar_por_fiabilidad_equipos(
                probs_base,
                fiabilidad_leida,
                "Equipo Memoria",
                "Rival 203-1",
            )
            probs_diario, riesgo_diario, lecturas_diario = ajustar_por_diario_aprendizaje(
                probs_fiabilidad,
                diario_leido,
                "Equipo Memoria",
                "Rival 203-1",
            )
            probs_final, riesgo_pesos, lecturas_pesos, aplicaciones = ajustar_por_pesos_dinamicos(
                probs_diario,
                pesos_leidos,
                {},
                {},
                {},
                {},
                {"pj": 20, "gf": 18, "gc": 26, "posicion": 14, "local": {"pj": 10, "pts": 10}, "tendencias": {"forma_5_pts": 3, "forma_10_pts": 10}},
                {"pj": 20, "gf": 24, "gc": 18, "posicion": 7, "visitante": {"pj": 10, "pts": 16}, "tendencias": {"forma_5_pts": 9, "forma_10_pts": 16}},
            )

            self.assertLess(probs_fiabilidad["1"], probs_base["1"])
            self.assertNotEqual(probs_final, probs_base)
            self.assertGreater(riesgo_fiabilidad + riesgo_diario + riesgo_pesos, 0)
            self.assertTrue(lecturas_fiabilidad)
            self.assertTrue(lecturas_diario or lecturas_pesos)
            self.assertTrue(aplicaciones)


if __name__ == "__main__":
    unittest.main()
