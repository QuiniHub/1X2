import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jornada_objetivo_quiniela as objetivo


def escribir_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def escribir_jornada(base, numero, fecha=None):
    escribir_json(
        base / f"jornada_{numero}.json",
        {
            "jornada": numero,
            "partidos": [
                {
                    "num": idx + 1,
                    "local": f"Local {idx + 1}",
                    "visitante": f"Visitante {idx + 1}",
                    "signo_oficial": "Pendiente",
                    **({"fecha": fecha} if fecha else {}),
                }
                for idx in range(14)
            ],
        },
    )


class JornadaObjetivoQuinielaTests(unittest.TestCase):
    def test_no_salta_a_jornada_futura_cargada(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jornadas = tmp / "data" / "jornadas"
            for numero in (68, 70):
                escribir_jornada(jornadas, numero)

            historial = tmp / "data" / "historial_quinielas.json"
            escribir_json(
                historial,
                {
                    "jornadas": [
                        {
                            "jornada": 67,
                            "nuestra_quiniela": "1 X 2 1 X 2 1 X 2 1 X 2 1 X",
                            "resultado_oficial": "11111111111111",
                            "validada": True,
                        },
                        {
                            "jornada": 68,
                            "nuestra_quiniela": "No validada",
                            "resultado_oficial": "Pendiente",
                            "validada": False,
                        },
                    ]
                },
            )
            quinielas = tmp / "data" / "quinielas_jugadas.json"
            escribir_json(quinielas, {"jugadas": []})

            self.assertEqual(
                objetivo.jornada_objetivo_prediccion(jornadas, historial, quinielas),
                68,
            )
            resumen = objetivo.resumen_jornada_objetivo(jornadas, historial, quinielas)
            self.assertEqual(resumen["ultima_jornada_aprendida"], 67)
            self.assertEqual(resumen["jornada_objetivo"], 68)
            self.assertEqual(resumen["jornadas_futuras_cargadas"], [70])
            self.assertEqual(resumen["jornadas_intermedias_faltantes"], [69])

    def test_objetivo_es_espera_si_no_esta_cargada(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jornadas = tmp / "data" / "jornadas"
            escribir_jornada(jornadas, 70)
            historial = tmp / "data" / "historial_quinielas.json"
            escribir_json(
                historial,
                {
                    "jornadas": [
                        {
                            "jornada": 69,
                            "signos": ["1"] * 14,
                            "validada": True,
                        }
                    ]
                },
            )
            quinielas = tmp / "data" / "quinielas_jugadas.json"
            escribir_json(quinielas, {"jugadas": []})

            resumen = objetivo.resumen_jornada_objetivo(jornadas, historial, quinielas)
            self.assertEqual(resumen["jornada_objetivo"], 70)
            self.assertTrue(resumen["jornada_objetivo_cargada"])

    def test_objetivo_salta_hueco_si_hay_siguiente_cargada(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jornadas = tmp / "data" / "jornadas"
            escribir_jornada(jornadas, 70)
            historial = tmp / "data" / "historial_quinielas.json"
            escribir_json(
                historial,
                {
                    "jornadas": [
                        {
                            "jornada": 68,
                            "signos": ["1"] * 14,
                            "validada": True,
                        }
                    ]
                },
            )
            quinielas = tmp / "data" / "quinielas_jugadas.json"
            escribir_json(quinielas, {"jugadas": []})

            resumen = objetivo.resumen_jornada_objetivo(jornadas, historial, quinielas)
            self.assertEqual(resumen["ultima_jornada_aprendida"], 68)
            self.assertEqual(resumen["jornada_objetivo"], 70)
            self.assertTrue(resumen["jornada_objetivo_cargada"])
            self.assertEqual(resumen["jornadas_intermedias_faltantes"], [69])

    def test_reinicio_de_temporada_vuelve_a_jornada_1(self):
        # Caso real: jornada 76 (nordica, cierra el ciclo de verano) ya
        # aprendida, y jornada 1 de la temporada 26/27 (LaLiga) ya cargada
        # con fecha posterior -aunque su numero sea menor, es la jornada
        # objetivo real, no "76 + 1" (que no existe en la numeracion de LAE).
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jornadas = tmp / "data" / "jornadas"
            escribir_jornada(jornadas, 76, fecha="2026-08-07")
            escribir_jornada(jornadas, 1, fecha="2026-08-15")

            historial = tmp / "data" / "historial_quinielas.json"
            escribir_json(historial, {"jornadas": []})
            quinielas = tmp / "data" / "quinielas_jugadas.json"
            escribir_json(
                quinielas,
                {"jugadas": [{"jornada": 76, "signos": ["1"] * 14, "validada": True}]},
            )

            resumen = objetivo.resumen_jornada_objetivo(jornadas, historial, quinielas)
            self.assertEqual(resumen["ultima_jornada_aprendida"], 76)
            self.assertEqual(resumen["jornada_objetivo"], 1)
            self.assertTrue(resumen["jornada_objetivo_cargada"])
            self.assertEqual(resumen["jornadas_futuras_cargadas"], [])

    def test_tras_jugar_la_jornada_1_nueva_avanza_a_la_2(self):
        # Bug real (18/08/2026): con la J1 de 26/27 ya jugada y guardada, el
        # objetivo se quedaba clavado en la propia J1 en bucle. La causa era
        # que "ultima aprendida" se calculaba por NUMERO (max = 76, de la
        # temporada vieja) en vez de por fecha, asi que el reinicio de
        # temporada volvia a resolver "la primera posterior a la J76" = J1,
        # jornada tras jornada, sin avanzar nunca.
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jornadas = tmp / "data" / "jornadas"
            escribir_jornada(jornadas, 76, fecha="2026-08-09")
            escribir_jornada(jornadas, 1, fecha="2026-08-15")
            escribir_jornada(jornadas, 2, fecha="2026-08-22")

            historial = tmp / "data" / "historial_quinielas.json"
            escribir_json(historial, {"jornadas": []})
            quinielas = tmp / "data" / "quinielas_jugadas.json"
            escribir_json(
                quinielas,
                {
                    "jugadas": [
                        {"jornada": 76, "signos": ["1"] * 14, "validada": True},
                        {"jornada": 1, "signos": ["1"] * 14, "validada": True},
                    ]
                },
            )

            resumen = objetivo.resumen_jornada_objetivo(jornadas, historial, quinielas)
            self.assertEqual(resumen["ultima_jornada_aprendida"], 1)
            self.assertEqual(resumen["jornada_objetivo"], 2)
            self.assertTrue(resumen["jornada_objetivo_cargada"])

    def test_prefiere_la_cronologicamente_siguiente_sobre_el_numero_menor(self):
        # Con varias jornadas cargadas posteriores, debe elegir la mas
        # proxima en el TIEMPO, no la de numero mas bajo.
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jornadas = tmp / "data" / "jornadas"
            escribir_jornada(jornadas, 76, fecha="2026-08-09")
            escribir_jornada(jornadas, 2, fecha="2026-08-22")
            escribir_jornada(jornadas, 3, fecha="2026-08-29")

            historial = tmp / "data" / "historial_quinielas.json"
            escribir_json(historial, {"jornadas": []})
            quinielas = tmp / "data" / "quinielas_jugadas.json"
            escribir_json(
                quinielas,
                {"jugadas": [{"jornada": 76, "signos": ["1"] * 14, "validada": True}]},
            )

            self.assertEqual(
                objetivo.jornada_objetivo_prediccion(jornadas, historial, quinielas),
                2,
            )

    def test_reinicio_de_temporada_sin_jornada_1_cargada_aun(self):
        # Mismo escenario pero la jornada 1 todavia no se ha publicado en la
        # fuente -debe seguir esperando, no inventar una jornada 77.
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jornadas = tmp / "data" / "jornadas"
            escribir_jornada(jornadas, 76, fecha="2026-08-07")

            historial = tmp / "data" / "historial_quinielas.json"
            escribir_json(historial, {"jornadas": []})
            quinielas = tmp / "data" / "quinielas_jugadas.json"
            escribir_json(
                quinielas,
                {"jugadas": [{"jornada": 76, "signos": ["1"] * 14, "validada": True}]},
            )

            resumen = objetivo.resumen_jornada_objetivo(jornadas, historial, quinielas)
            self.assertEqual(resumen["ultima_jornada_aprendida"], 76)
            self.assertEqual(resumen["jornada_objetivo"], 77)
            self.assertFalse(resumen["jornada_objetivo_cargada"])


if __name__ == "__main__":
    unittest.main()
