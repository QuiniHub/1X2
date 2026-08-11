import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generar_contexto_competitivo import cerrar_equipo, preparar_tabla


class CerrarEquipoReinicioTemporadaTests(unittest.TestCase):
    """Bug real detectado en la Jornada 1 de LaLiga 26/27 (2026-08-11): con
    pj=0 para todos los equipos, cerrar_equipo() calculaba conclusiones
    matematicamente absurdas (un equipo "salvado matematicamente", otro con
    "riesgo de descenso" y motivacion "maxima") el mismo dia que arranca la
    temporada, sin haberse jugado ni un partido -esto distorsionaba fuerte
    la probabilidad final del motor (ver commit del 2026-08-11)."""

    def test_pj_cero_no_marca_salvado_ni_riesgo_descenso(self):
        equipo = {"equipo": "Equipo Nuevo", "pj": 0, "puntos": 0, "puntos_en_juego": 114}
        objetivos_falsos = [
            {"objetivo": "descenso", "estado": "salvado_matematicamente", "vivo": False, "terminal": True},
        ]

        resultado = cerrar_equipo(equipo, objetivos_falsos)

        self.assertEqual(resultado["situacion_competitiva"], "temporada_no_iniciada")
        self.assertEqual(resultado["motivacion_competitiva"], "baja")
        self.assertEqual(resultado["objetivos_vivos"], [])
        self.assertNotEqual(resultado["situacion_competitiva"], "salvado_matematicamente")
        self.assertNotEqual(resultado["situacion_competitiva"], "riesgo_descenso")

    def test_pj_mayor_que_cero_sigue_calculando_normal(self):
        equipo = {"equipo": "Equipo En Marcha", "pj": 5, "puntos": 3, "puntos_en_juego": 99}
        objetivo_real = {
            "objetivo": "descenso",
            "estado": "riesgo_descenso",
            "vivo": True,
            "terminal": False,
            "lectura": "riesgo real",
        }

        resultado = cerrar_equipo(equipo, [objetivo_real])

        self.assertEqual(resultado["situacion_competitiva"], "riesgo_descenso")
        self.assertEqual(resultado["objetivos_vivos"], [objetivo_real])


class PrepararTablaPosicionReinicioTests(unittest.TestCase):
    """Bug real relacionado (mismo dia, 2026-08-11): con pj=0 la "posicion"
    del dato de origen es un artefacto de orden (alfabetico/roster), no una
    clasificacion real -pero tier_por_posicion() en motor_prediccion_quiniela.py
    (usado por boleto_millonario para el patron "top10 vs resto de la tabla")
    la leia igual, dando avisos "millonaria" falsos en la Jornada 1 basados en
    una posicion sin sentido. Marc: "el historial de ligas pasadas solo sirve
    para entender el futbol en general, no para esta temporada nueva -ahora
    mismo el unico soporte historico real son los resultados de amistosos"."""

    def test_pj_cero_anula_la_posicion(self):
        tabla = [{"equipo": "Equipo A", "posicion": 6, "pj": 0, "puntos": 0}]

        equipos = preparar_tabla(tabla, total_partidos=38)

        self.assertEqual(equipos[0]["posicion"], 0)

    def test_pj_mayor_que_cero_conserva_la_posicion_real(self):
        tabla = [{"equipo": "Equipo B", "posicion": 6, "pj": 10, "puntos": 18}]

        equipos = preparar_tabla(tabla, total_partidos=38)

        self.assertEqual(equipos[0]["posicion"], 6)


if __name__ == "__main__":
    unittest.main()
