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


class ParsearCeldaPosicionEquipoTests(unittest.TestCase):
    """AS.com rediseno su tabla de clasificacion en agosto 2026: paso de
    lineas de texto sueltas (posicion, nombre y sigla en lineas separadas)
    a una <table> real con la primera celda pegada tipo "1AlavesALA". El
    parser viejo dejaba de encontrar filas (0 de 20 equipos) y la pestaña
    Liga 26/27 se quedaba clavada en pretemporada aunque ya hubiera
    resultados reales -este bloque cubre el formato nuevo."""

    def test_celda_con_sigla_normal(self):
        # limpiar_nombre_as() pasa el nombre por canonico(), que normaliza
        # "Alaves" al nombre oficial completo -es el comportamiento real.
        self.assertEqual(
            aco.parsear_celda_posicion_equipo("1AlavesALA"),
            (1, "Deportivo Alaves"),
        )

    def test_celda_con_dos_digitos_de_posicion(self):
        self.assertEqual(
            aco.parsear_celda_posicion_equipo("12SevillaSEV"),
            (12, "Sevilla FC"),
        )

    def test_equipo_sin_sigla_repite_el_nombre_entero(self):
        # Filiales recien ascendidos (ej. Celta Fortuna) no tienen sigla
        # corta conocida: AS.com repite el nombre completo dos veces.
        self.assertEqual(
            aco.parsear_celda_posicion_equipo("5Celta FortunaCelta Fortuna"),
            (5, "Celta Fortuna"),
        )

    def test_celda_irreconocible_devuelve_none(self):
        self.assertIsNone(aco.parsear_celda_posicion_equipo("Posición variación y equipo"))
        self.assertIsNone(aco.parsear_celda_posicion_equipo(""))


class ParsearEstadisticasAsTests(unittest.TestCase):
    def test_ocho_valores_numericos_validos(self):
        stats = aco.parsear_estadisticas_as(["3", "1", "1", "0", "0", "3", "0", "3", "G", ""])
        self.assertEqual(stats, {
            "puntos": 3, "pj": 1, "g": 1, "e": 0, "p": 0,
            "gf": 3, "gc": 0, "dg": 3,
        })

    def test_diferencia_de_goles_negativa(self):
        stats = aco.parsear_estadisticas_as(["0", "1", "0", "0", "1", "0", "1", "-1"])
        self.assertEqual(stats["dg"], -1)

    def test_menos_de_ocho_celdas_no_es_fila_de_stats(self):
        self.assertIsNone(aco.parsear_estadisticas_as(["3", "1", "1"]))

    def test_celda_no_numerica_no_es_fila_de_stats(self):
        self.assertIsNone(aco.parsear_estadisticas_as(["PTS", "PJ", "G", "E", "P", "GF", "GC", "DIF"]))


if __name__ == "__main__":
    unittest.main()
