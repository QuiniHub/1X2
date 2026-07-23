import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import aprender_patrones_competitivos as apc


def equipo_vivo(nombre, situacion="en_descenso_con_opciones"):
    return {"equipo": nombre, "objetivos_vivos": [{"estado": situacion}], "situacion_competitiva": situacion, "puntos": 10}


def equipo_cerrado(nombre, puntos=10):
    return {"equipo": nombre, "objetivos_vivos": [], "situacion_competitiva": "no_se_juega_nada_clasificatorio", "puntos": puntos}


class TablaTests(unittest.TestCase):
    def test_aplicar_partido_reparte_puntos(self):
        tabla = apc.tabla_vacia()
        apc.aplicar_partido(tabla, "A", "B", 2, 0)
        apc.aplicar_partido(tabla, "A", "C", 1, 1)
        self.assertEqual(tabla["A"]["puntos"], 4)
        self.assertEqual(tabla["B"]["puntos"], 0)
        self.assertEqual(tabla["C"]["puntos"], 1)
        self.assertEqual(tabla["A"]["pj"], 2)

    def test_tabla_a_lista_ordenada_por_puntos_y_dg(self):
        tabla = apc.tabla_vacia()
        apc.aplicar_partido(tabla, "A", "B", 3, 0)
        apc.aplicar_partido(tabla, "C", "D", 1, 0)
        filas = apc.tabla_a_lista_ordenada(tabla)
        nombres = [f["equipo"] for f in filas]
        self.assertEqual(nombres[0], "A")
        self.assertEqual(filas[0]["posicion"], 1)
        self.assertEqual(filas[0]["dg"], 3)

    def test_tabla_a_lista_ordenada_ignora_equipos_sin_jugar(self):
        tabla = apc.tabla_vacia()
        apc.aplicar_partido(tabla, "A", "B", 1, 0)
        _ = tabla["C"]  # referenciado pero sin partidos jugados
        filas = apc.tabla_a_lista_ordenada(tabla)
        nombres = [f["equipo"] for f in filas]
        self.assertNotIn("C", nombres)


class ClasificacionHelpersTests(unittest.TestCase):
    def test_objetivo_cerrado_solo_si_no_hay_vivos(self):
        self.assertTrue(apc.objetivo_cerrado(equipo_cerrado("A")))
        self.assertFalse(apc.objetivo_cerrado(equipo_vivo("A")))
        self.assertFalse(apc.objetivo_cerrado(None))

    def test_necesidad_viva_requiere_objetivos_vivos(self):
        self.assertTrue(apc.necesidad_viva(equipo_vivo("A")))
        self.assertFalse(apc.necesidad_viva(equipo_cerrado("A")))

    def test_descenso_vivo_solo_en_situaciones_de_descenso(self):
        self.assertTrue(apc.descenso_vivo(equipo_vivo("A", "riesgo_descenso")))
        self.assertFalse(apc.descenso_vivo(equipo_vivo("A", "defiende_liderato")))
        self.assertFalse(apc.descenso_vivo(equipo_cerrado("A")))


class AnalizarCalendarioHistoricoTests(unittest.TestCase):
    """Prueba el fix central: la situacion competitiva usada para juzgar cada
    jornada debe reconstruirse ANTES de esa jornada (con lo jugado hasta
    entonces), nunca con datos de jornadas futuras ni con el snapshot de hoy."""

    def setUp(self):
        self._original = dict(apc.ANALIZADORES)
        self.llamadas = []

        def analizador_espia(tabla_previa):
            equipos_vistos = sorted(e["equipo"] for e in tabla_previa)
            self.llamadas.append(equipos_vistos)
            # Jornada 2 en adelante: Z (con muchos puntos) esta "cerrado",
            # Y (con pocos puntos) tiene necesidad viva -asi se puede
            # verificar que el patron se detecta con la tabla correcta.
            equipos = []
            for e in tabla_previa:
                if e["equipo"] == "Z" and e["puntos"] >= 3:
                    equipos.append(equipo_cerrado("Z", puntos=e["puntos"]))
                elif e["equipo"] == "Y":
                    equipos.append(equipo_vivo("Y"))
                else:
                    equipos.append({"equipo": e["equipo"], "objetivos_vivos": [], "situacion_competitiva": "no_se_juega_nada_clasificatorio", "puntos": e["puntos"]})
            return {"equipos": equipos}

        apc.ANALIZADORES = {"primera": analizador_espia, "segunda": analizador_espia}
        self.addCleanup(lambda: setattr(apc, "ANALIZADORES", self._original))

    def test_no_usa_resultados_futuros_para_juzgar_la_jornada_actual(self):
        calendario = {
            "temporada": "TEST",
            "jornadas": [
                {"jornada": 1, "partidos": [
                    {"local": "Z", "visitante": "W", "resultado": "3-0"},
                    {"local": "X", "visitante": "Y", "resultado": "3-0"},
                ]},
                {"jornada": 2, "partidos": [
                    # Y (necesitado) recibe a Z (ya "cerrado" tras la j1) -> el
                    # analizador-espia solo puede saber que Z esta "cerrado"
                    # porque ya jugo y gano en la jornada 1; si este metodo
                    # mirase el futuro o el snapshot de hoy en vez de la
                    # tabla reconstruida hasta la j1, este caso no se
                    # detectaria igual.
                    {"local": "Y", "visitante": "Z", "resultado": "1-1"},
                ]},
            ],
        }
        patrones = defaultdict(apc.base_patron)
        apc.analizar_calendario_historico("primera", calendario, patrones)

        # La jornada 1 no debe generar llamada al analizador con tabla_previa
        # no vacia mas que en la jornada 2 (jornada 1 arranca sin historial).
        self.assertEqual(len(self.llamadas), 1, "solo la jornada 2 tiene tabla previa con partidos jugados")
        self.assertEqual(self.llamadas[0], ["W", "X", "Y", "Z"], "la tabla previa a la jornada 2 solo debe reflejar la jornada 1")

        # local=Y (necesita), visitante=Z (cerrado) -> "necesitado_local_vs_visitante_objetivo_cerrado"
        clave = "necesitado_local_vs_visitante_objetivo_cerrado"
        self.assertIn(clave, patrones)
        self.assertEqual(patrones[clave]["casos"], 1)
        # signo real fue "X" (1-1); sorpresa = signo != "2" = True (el local Y no pierde)
        self.assertEqual(patrones[clave]["sorpresas"], 1)

        clave_general = "equipo_necesitado_vs_equipo_sin_objetivo"
        self.assertIn(clave_general, patrones)
        self.assertEqual(patrones[clave_general]["casos"], 1)
        self.assertEqual(patrones[clave_general]["sorpresas"], 1)


if __name__ == "__main__":
    unittest.main()
