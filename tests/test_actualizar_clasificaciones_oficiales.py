import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_clasificaciones_oficiales as aco


def equipo(nombre, posicion=1):
    return {"posicion": posicion, "equipo": nombre, "pj": 0, "puntos": 0}


class DetectarTemporadaTests(unittest.TestCase):
    def test_detecta_2026_2027_si_aparece_racing(self):
        tabla_primera = [
            equipo("FC Barcelona", 1),
            equipo("Real Racing Club de Santander", 2),
            equipo("RC Deportivo de La Coruna", 3),
        ]
        self.assertEqual(aco.detectar_temporada(tabla_primera), "2026/2027")

    def test_detecta_2025_2026_si_sigue_girona_en_primera(self):
        tabla_primera = [
            equipo("FC Barcelona", 1),
            equipo("Girona FC", 2),
            equipo("RCD Mallorca", 3),
        ]
        self.assertEqual(aco.detectar_temporada(tabla_primera), "2025/2026")

    def test_detecta_2025_2026_con_tabla_vacia(self):
        self.assertEqual(aco.detectar_temporada([]), "2025/2026")

    def test_deteccion_ignora_mayusculas_y_acentos(self):
        tabla_primera = [equipo("REAL RACING CLUB DE SANTANDER", 1)]
        self.assertEqual(aco.detectar_temporada(tabla_primera), "2026/2027")


if __name__ == "__main__":
    unittest.main()
