import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_clasificaciones_oficiales as aco


def celda_th(nombre, posicion=1, sigla="ALA", variacion=None):
    """Reconstruye el <th> real de AS.com para una fila de clasificacion.
    variacion=None -> equipo sin cambio de puesto (sin el span extra que
    causaba el bug real: posicion 1 + variacion 1 concatenados en el texto
    plano como "11..." en vez de "1...")."""
    variacion_html = (
        f'<div class="a_tb_pc"><span class="a_tb_pc_ic"></span>'
        f'<span class="a_tb_pc_tx">{variacion}</span></div>'
        if variacion is not None else '<div class="a_tb_pc"></div>'
    )
    html = (
        f'<th class="fix" scope="row"><div class="a_tb_fc">'
        f'<span class="a_tb_ps">{posicion}</span>{variacion_html}'
        f'<a class="a_tb_tm-lk" href="#"><span class="a_bd a_bd--md"></span>'
        f'<span class="_hidden-xs">{nombre}</span>'
        f'<abbr class="_hidden-md _hidden-lg" title="{nombre}">{sigla}</abbr></a></div></th>'
    )
    return BeautifulSoup(html, "html.parser").find("th")


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
    """AS.com rediseno su tabla de clasificacion en agosto 2026 (paso de
    lineas de texto sueltas a una <table> real), y en cuanto empezaron a
    jugarse partidos de la jornada 2 añadio ademas un indicador de
    variacion (sube/baja puestos) entre la posicion y el nombre. El parser
    viejo leia el texto plano ya concatenado (ej. "1AlavesALA") y con la
    variacion presente pasaba a "11AlavesALA" -Alaves aparecia con
    posicion 11 y nombre "1Alaves" en vez de posicion 1 y nombre "Alaves"
    (bug real visto en produccion el 2026-08-19). Fix: leer posicion y
    nombre directamente de sus elementos HTML (.a_tb_ps / span._hidden-xs)
    en vez de contar digitos en texto pegado -asi la variacion, presente o
    no, nunca se mezcla con la posicion."""

    def test_celda_sin_variacion_de_puesto(self):
        # limpiar_nombre_as() pasa el nombre por canonico(), que normaliza
        # "Alaves" al nombre oficial completo -es el comportamiento real.
        celda = celda_th("Alaves", posicion=1, sigla="ALA")
        self.assertEqual(aco.parsear_celda_posicion_equipo(celda), (1, "Deportivo Alaves"))

    def test_celda_con_variacion_de_puesto_no_contamina_la_posicion(self):
        # Caso real que rompio el parser viejo: equipo que subio 1 puesto,
        # AS.com añade el digito "1" de variacion junto a la posicion.
        celda = celda_th("Alaves", posicion=1, sigla="ALA", variacion=1)
        self.assertEqual(aco.parsear_celda_posicion_equipo(celda), (1, "Deportivo Alaves"))

    def test_celda_con_dos_digitos_de_posicion(self):
        celda = celda_th("Sevilla", posicion=12, sigla="SEV")
        self.assertEqual(aco.parsear_celda_posicion_equipo(celda), (12, "Sevilla FC"))

    def test_celda_con_dos_digitos_de_posicion_y_variacion(self):
        celda = celda_th("Sevilla", posicion=12, sigla="SEV", variacion=3)
        self.assertEqual(aco.parsear_celda_posicion_equipo(celda), (12, "Sevilla FC"))

    def test_equipo_sin_sigla_conocida_se_lee_igual(self):
        # Filiales recien ascendidos (ej. Celta Fortuna): la sigla de
        # AS.com puede ser el nombre completo repetido, pero ya no importa
        # porque el nombre se lee de su propio span, no de lo que sobre
        # tras quitar la sigla.
        celda = celda_th("Celta Fortuna", posicion=5, sigla="Celta Fortuna")
        self.assertEqual(aco.parsear_celda_posicion_equipo(celda), (5, "Celta Fortuna"))

    def test_celda_irreconocible_devuelve_none(self):
        celda_vacia = BeautifulSoup("<th>Posición variación y equipo</th>", "html.parser").find("th")
        self.assertIsNone(aco.parsear_celda_posicion_equipo(celda_vacia))


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
