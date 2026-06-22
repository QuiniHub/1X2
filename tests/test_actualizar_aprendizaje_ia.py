import unittest

from actualizar_aprendizaje_ia import generar_ajuste_motor, registrar_revision, resumen_vacio


class ActualizarAprendizajeIATest(unittest.TestCase):
    def test_generar_ajuste_motor_convierte_fallos_en_reglas(self):
        resumen = {
            "partidos_revisados": 111,
            "fallos": 42,
            "fallos_por_tipo": {
                "Fijo fallado": 23,
                "No cubrio empate": 11,
                "Doble insuficiente": 8,
            },
        }

        ajuste = generar_ajuste_motor(resumen)

        self.assertEqual(ajuste["muestra"], "suficiente")
        self.assertGreater(ajuste["boost_empate_zona_riesgo"], 0)
        self.assertGreater(ajuste["riesgo_extra_fijo_fragil"], 0)
        self.assertGreater(ajuste["riesgo_extra_triple_insuficiente"], 0)
        self.assertEqual(ajuste["min_dobles_auto"], 3)
        self.assertEqual(ajuste["min_triples_auto"], 1)

    def test_registrar_revision_guarda_signo_omitido_en_fallo(self):
        resumen = resumen_vacio()
        partido = {"local": "A", "visitante": "B", "resultado": "1-1"}

        registrar_revision(resumen, 1, partido, "1", "X", "test")

        self.assertEqual(resumen["fallos"], 1)
        self.assertEqual(resumen["fallos_por_tipo"]["No cubrio empate"], 1)
        self.assertEqual(resumen["signos_omitidos_en_fallo"]["X"], 1)
        self.assertEqual(resumen["detalle"][0]["signo_omitido"], "X")

    def test_registrar_revision_enriquece_detalle_aprendizaje(self):
        resumen = resumen_vacio()
        partido = {"local": "A", "visitante": "B", "resultado": "2-0"}
        prediccion = {
            "probabilidades": {"1": 55.0, "X": 25.0, "2": 20.0},
            "origen_probabilidades": "modelo_test",
            "razonamiento": "Decision final: 1.",
            "cuotas": {"1": 1.8},
        }
        pesos = {"pesos": {"empate": 0.1, "sorpresa": 0.09}}

        registrar_revision(resumen, 1, partido, "X", "1", "test", prediccion, pesos)

        detalle = resumen["detalle"][0]
        self.assertEqual(detalle["probabilidades_usadas"]["1"], 55.0)
        self.assertEqual(detalle["pesos_modelo"]["empate"], 0.1)
        self.assertEqual(detalle["fuentes_utilizadas"], ["modelo_test"])
        self.assertEqual(detalle["resultado_final"], "2-0")
        self.assertEqual(detalle["motivo_error"], "Fijo fallado")
        self.assertEqual(detalle["cuotas"]["1"], 1.8)


if __name__ == "__main__":
    unittest.main()
