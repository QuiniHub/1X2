import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import optimizador_ev_premio as oep
from modelo_reparto_quiniela import EvaluadorEV, columnas_boleto


def _prediccion(jornada=12, partidos=14):
    lista = []
    for n in range(1, partidos + 1):
        lista.append({
            "num": n,
            "local": f"LOCAL{n}",
            "visitante": f"VISITANTE{n}",
            "probabilidades": {"1": 50.0, "X": 30.0, "2": 20.0},
            "signo_base": "1",
            "signo_final": "1X" if n <= 2 else "1",
            "tipo": "DOBLE" if n <= 2 else "FIJO",
        })
    return {
        "jornada": jornada,
        "prediccion_disponible": True,
        "prediccion_permitida": True,
        "coste": {"apuestas": 4},
        "partidos": lista,
    }


def _fuente_losilla(jornada=12):
    lista = []
    for n in range(1, 15):
        lista.append({
            "numero": n,
            "local": f"LOCAL{n}",
            "visitante": f"VISITANTE{n}",
            "probabilidades_signo": {"1": 48.0, "X": 28.0, "2": 24.0},
            "fuentes_detalle": {"lae": {"1": 70, "X": 20, "2": 10}},
        })
    return {"probabilidades": {"jornada": jornada, "partidos": lista}}


class MezclarProbabilidadesTests(unittest.TestCase):
    def test_mezcla_50_50_normalizada(self):
        mezcla = oep.mezclar_probabilidades({"1": 60, "X": 20, "2": 20}, {"1": 40, "X": 40, "2": 20})
        self.assertAlmostEqual(mezcla["1"], 0.5)
        self.assertAlmostEqual(mezcla["X"], 0.3)
        self.assertAlmostEqual(sum(mezcla.values()), 1.0)

    def test_sin_losilla_usa_solo_motor(self):
        mezcla = oep.mezclar_probabilidades({"1": 60, "X": 20, "2": 20}, None)
        self.assertAlmostEqual(mezcla["1"], 0.6)


class OptimizarBoletoTests(unittest.TestCase):
    def test_respeta_el_presupuesto(self):
        p_real = [{"1": 50, "X": 30, "2": 20}] * 14
        masa = [{"1": 70, "X": 20, "2": 10}] * 14
        evaluador = EvaluadorEV(p_real, masa, n_muestras=300, semilla=5)
        boleto = oep.optimizar_boleto(evaluador, ["1"] * 14, presupuesto_apuestas=8)
        self.assertLessEqual(columnas_boleto(boleto), 8)
        self.assertEqual(len(boleto), 14)

    def test_nunca_empeora_el_arranque(self):
        p_real = [{"1": 50, "X": 30, "2": 20}] * 14
        masa = [{"1": 70, "X": 20, "2": 10}] * 14
        evaluador = EvaluadorEV(p_real, masa, n_muestras=300, semilla=5)
        inicial = ["1"] * 14
        boleto = oep.optimizar_boleto(evaluador, inicial, presupuesto_apuestas=4)
        self.assertGreaterEqual(
            evaluador.evaluar(boleto)["ev_eur"],
            evaluador.evaluar(inicial)["ev_eur"],
        )


class CalcularBloqueEvTests(unittest.TestCase):
    def _bloque(self, prediccion=None, fuente=None):
        return oep.calcular_bloque_ev(
            prediccion if prediccion is not None else _prediccion(),
            fuente if fuente is not None else _fuente_losilla(),
            n_muestras=300,
            n_muestras_final=500,
            recaudacion=2_000_000.0,
        )

    def test_bloque_ok_con_presupuesto_respetado(self):
        bloque = self._bloque()
        self.assertEqual(bloque["estado"], "ok")
        self.assertEqual(bloque["jornada"], 12)
        self.assertLessEqual(bloque["apuestas"], bloque["presupuesto_apuestas"])
        self.assertEqual(len(bloque["partidos"]), 14)
        self.assertIsInstance(bloque["ev_premio_eur"], float)
        self.assertIsInstance(bloque["ev_boleto_conservador_eur"], float)
        self.assertEqual(bloque["total_cambios"], len(bloque["cambios_respecto_a_conservadora"]))

    def test_es_determinista_con_la_misma_semilla(self):
        a = self._bloque()
        b = self._bloque()
        self.assertEqual(a["partidos"], b["partidos"])
        self.assertEqual(a["ev_premio_eur"], b["ev_premio_eur"])

    def test_sin_14_partidos_no_disponible(self):
        bloque = self._bloque(prediccion=_prediccion(partidos=10))
        self.assertEqual(bloque["estado"], "no_disponible")

    def test_sin_porcentajes_lae_no_disponible(self):
        # jornada sin archivo versionado en el repo y sin lae en la fuente
        bloque = self._bloque(prediccion=_prediccion(jornada=99),
                              fuente=_fuente_losilla(jornada=98))
        self.assertEqual(bloque["estado"], "no_disponible")
        self.assertIn("apostantes", bloque["motivo"])


class PipelineTests(unittest.TestCase):
    def test_los_scripts_nuevos_estan_en_el_pipeline(self):
        import actualizar_todo
        self.assertIn("actualizar_porcentajes_lae.py", actualizar_todo.SCRIPTS_ACTIVOS)
        self.assertIn("optimizador_ev_premio.py", actualizar_todo.SCRIPTS_ACTIVOS)
        self.assertIn("actualizar_porcentajes_lae.py", actualizar_todo.SCRIPTS_NO_CRITICOS_RED)
        self.assertIn("optimizador_ev_premio.py", actualizar_todo.SCRIPTS_NO_CRITICOS_RED)
        # el orden importa: los porcentajes se capturan tras actualizar Losilla
        # y el optimizador corre despues del motor y sus correcciones
        activos = actualizar_todo.SCRIPTS_ACTIVOS
        self.assertGreater(
            activos.index("actualizar_porcentajes_lae.py"),
            activos.index("actualizar_fuente_losilla.py"),
        )
        self.assertGreater(
            activos.index("optimizador_ev_premio.py"),
            activos.index("corregir_emparejamiento_equipos.py"),
        )

    def test_limpiar_prediccion_bloqueada_retira_el_bloque(self):
        import limpiar_prediccion_bloqueada
        self.assertIn("boleto_ev_premio", limpiar_prediccion_bloqueada.CAMPOS_RAIZ_PREDICTIVOS)


if __name__ == "__main__":
    unittest.main()
