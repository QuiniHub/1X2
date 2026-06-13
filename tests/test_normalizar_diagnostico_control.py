import unittest

from normalizar_diagnostico_control import combinar_alertas, estado_final


class NormalizarDiagnosticoControlTest(unittest.TestCase):
    def test_conserva_alertas_de_fuentes_aunque_control_este_ok(self):
        control = {"estado": "operativo", "alertas": []}
        diagnostico = {
            "score_salud": 93,
            "alertas": [
                {
                    "nivel": "media",
                    "titulo": "Fuentes deportivas incompletas",
                    "detalle": "Faltan cuotas, xG y alineaciones estructuradas.",
                }
            ],
        }

        estado, score, alertas = estado_final(control, diagnostico)

        self.assertEqual(estado, "operativo_con_avisos")
        self.assertEqual(score, 82)
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0]["titulo"], "Fuentes deportivas incompletas")

    def test_no_duplica_alertas_iguales(self):
        alerta = {"nivel": "media", "titulo": "A", "detalle": "B"}

        self.assertEqual(combinar_alertas([alerta], [dict(alerta)]), [alerta])

    def test_control_critico_manda_sobre_diagnostico_sano(self):
        control = {"estado": "critico", "alertas": [{"nivel": "critica", "titulo": "Sin jornada"}]}
        diagnostico = {"score_salud": 100, "alertas": []}

        estado, score, alertas = estado_final(control, diagnostico)

        self.assertEqual(estado, "critico_actualizacion")
        self.assertEqual(score, 45)
        self.assertEqual(len(alertas), 1)


if __name__ == "__main__":
    unittest.main()
