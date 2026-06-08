import unittest

from normalizar_textos_generados import normalizar_valor, reparar_mojibake_texto


class NormalizarTextosGeneradosTest(unittest.TestCase):
    def test_repara_mojibake_comun(self):
        self.assertEqual(reparar_mojibake_texto("B\u00c3\u00a9lgica"), "B\u00e9lgica")
        self.assertEqual(reparar_mojibake_texto("T\u00c3\u00banez"), "T\u00fanez")

    def test_no_cambia_texto_correcto(self):
        self.assertEqual(reparar_mojibake_texto("M\u00e1laga CF"), "M\u00e1laga CF")

    def test_normaliza_estructuras_anidadas(self):
        datos = {"partidos": [{"local": "B\u00c3\u00a9lgica", "visitante": "T\u00c3\u00banez"}]}
        esperado = {"partidos": [{"local": "B\u00e9lgica", "visitante": "T\u00fanez"}]}
        self.assertEqual(normalizar_valor(datos), esperado)


if __name__ == "__main__":
    unittest.main()
