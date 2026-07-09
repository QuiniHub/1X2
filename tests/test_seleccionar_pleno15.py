import tempfile
import unittest
from pathlib import Path

import seleccionar_pleno15 as sp15


def _partido_seguro(num, local="A", visitante="B"):
    return {
        "num": num,
        "local": local,
        "visitante": visitante,
        "probabilidades": {"1": 90.0, "X": 5.0, "2": 5.0},
        "incertidumbre": 10.0,
        "surprise_score": 0.0,
        "calidad_datos": "alta",
        "origen_probabilidades": "modelo_entrenado",
    }


def _pleno_incierto():
    return {
        "num": 15,
        "local": "Sarpsborg 08",
        "visitante": "Viking",
        "probabilidades": {"1": 40.0, "X": 34.0, "2": 26.0},
        "incertidumbre": 140.0,
        "surprise_score": 90.0,
        "calidad_datos": "baja",
        "origen_probabilidades": "fallback_posicion",
    }


class CandidatosPrediccionTests(unittest.TestCase):
    """El Pleno al 15 siempre es el partido 15 del boleto oficial -no se
    puede jugar el marcador exacto de otro partido en esa casilla. Estos
    tests reproducen el bug real de las jornadas 70/71/72, donde el sistema
    trataba los 14 partidos normales como "candidatos" intercambiables y
    sustituia la identidad del Pleno al 15 por la del que saliera mas
    seguro."""

    def test_solo_devuelve_el_partido_15_aunque_otros_sean_mas_seguros(self):
        data = {
            "jornada": 72,
            "partidos": [_partido_seguro(n) for n in range(1, 15)],
            "pleno15": _pleno_incierto(),
        }
        candidatos = sp15.candidatos_prediccion(data)
        self.assertEqual(len(candidatos), 1)
        self.assertEqual(candidatos[0]["num"], 15)

    def test_usa_el_partido_15_de_partidos_si_no_hay_bloque_pleno15(self):
        data = {
            "jornada": 72,
            "partidos": [_partido_seguro(n) for n in range(1, 15)] + [_pleno_incierto()],
        }
        candidatos = sp15.candidatos_prediccion(data)
        self.assertEqual(len(candidatos), 1)
        self.assertEqual(candidatos[0]["num"], 15)

    def test_vacio_si_no_hay_ningun_partido_15(self):
        data = {"jornada": 72, "partidos": [_partido_seguro(n) for n in range(1, 15)]}
        self.assertEqual(sp15.candidatos_prediccion(data), [])


class MainNuncaSustituyeElPartido15Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._originales = {"ULTIMA": sp15.ULTIMA, "SALIDA": sp15.SALIDA, "PREDICCIONES": sp15.PREDICCIONES}
        sp15.PREDICCIONES = tmp
        sp15.ULTIMA = tmp / "ultima_prediccion.json"
        sp15.SALIDA = tmp / "pleno15_jornada_actual.json"

    def tearDown(self):
        for clave, valor in self._originales.items():
            setattr(sp15, clave, valor)
        self._tmp.cleanup()

    def test_la_recomendacion_final_siempre_es_el_partido_15(self):
        """Reproduce el bug real: el partido 8 (aqui, con nombres reales de
        la jornada 72) tiene probabilidades mucho mas seguras que el
        partido 15 real, y el sistema antiguo lo sustituia como Pleno al 15
        entero (num, local, visitante incluidos)."""
        data = {
            "jornada": 72,
            "partidos": [
                _partido_seguro(n, "Fredrikstad", "Lillestrøm") if n == 8 else _partido_seguro(n)
                for n in range(1, 15)
            ],
            "pleno15": _pleno_incierto(),
        }
        sp15.guardar_json(sp15.ULTIMA, data)

        sp15.main()

        actualizado = sp15.cargar_json(sp15.ULTIMA)
        self.assertEqual(actualizado["pleno15"]["num"], 15)
        self.assertEqual(actualizado["pleno15"]["local"], "Sarpsborg 08")
        self.assertEqual(actualizado["pleno15"]["visitante"], "Viking")


if __name__ == "__main__":
    unittest.main()
