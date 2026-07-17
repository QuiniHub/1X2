import sys
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datos_profesionales import (
    buscar_partido,
    estado_cuenta_api_football,
    leer_api_football_payload,
    leer_payload_externo,
    normalizar_payload,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeApiFootball:
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append({"url": url, "headers": headers or {}, "params": params or {}, "timeout": timeout})
        if url.endswith("/fixtures/lineups"):
            return FakeResponse({
                "response": [
                    {
                        "team": {"id": 10, "name": "Equipo Local"},
                        "startXI": [{"player": {"name": f"L{i}"}} for i in range(11)],
                    },
                    {
                        "team": {"id": 20, "name": "Equipo Visitante"},
                        "startXI": [{"player": {"name": f"V{i}"}} for i in range(10)],
                    },
                ]
            })
        if url.endswith("/fixtures"):
            return FakeResponse({
                "response": [
                    {
                        "fixture": {
                            "id": 99,
                            "date": "2026-08-16T21:00:00+00:00",
                            "venue": {"name": "Estadio Test"},
                        },
                        "league": {"id": 140, "name": "LaLiga", "season": 2026, "round": "Regular Season - 1"},
                        "teams": {
                            "home": {"id": 10, "name": "Equipo Local"},
                            "away": {"id": 20, "name": "Equipo Visitante"},
                        },
                    }
                ]
            })
        if url.endswith("/odds"):
            return FakeResponse({
                "response": [
                    {
                        "bookmakers": [
                            {
                                "name": "TestBook",
                                "bets": [
                                    {
                                        "name": "Match Winner",
                                        "values": [
                                            {"value": "Home", "odd": "1.80"},
                                            {"value": "Draw", "odd": "3.40"},
                                            {"value": "Away", "odd": "4.80"},
                                        ],
                                    }
                                ],
                            }
                        ]
                    }
                ]
            })
        if url.endswith("/injuries"):
            return FakeResponse({
                "response": [
                    {
                        "team": {"id": 10, "name": "Equipo Local"},
                        "player": {"name": "Central titular", "type": "Injured", "reason": "Muscle injury"},
                    },
                    {
                        "team": {"id": 20, "name": "Equipo Visitante"},
                        "player": {"name": "Mediocentro", "type": "Suspended", "reason": "Suspended"},
                    },
                ]
            })
        if url.endswith("/status"):
            return FakeResponse({
                "response": {
                    "subscription": {"plan": "Free", "end": "2027-01-01", "active": True},
                    "requests": {"current": 47, "limit_day": 100},
                }
            })
        if url.endswith("/standings"):
            return FakeResponse({
                "response": [
                    {
                        "league": {
                            "standings": [[
                                {
                                    "rank": 4,
                                    "team": {"id": 10, "name": "Equipo Local"},
                                    "points": 18,
                                    "goalsDiff": 7,
                                    "form": "WWDLW",
                                    "all": {"played": 9},
                                },
                                {
                                    "rank": 14,
                                    "team": {"id": 20, "name": "Equipo Visitante"},
                                    "points": 9,
                                    "goalsDiff": -3,
                                    "form": "LDLLW",
                                    "all": {"played": 9},
                                },
                            ]]
                        }
                    }
                ]
            })
        return FakeResponse({"response": []})


class DatosProfesionalesTests(unittest.TestCase):
    def test_normaliza_payload_profesional_completo(self):
        datos = normalizar_payload(
            {
                "temporada_objetivo": "2026/2027",
                "jornadas": {
                    "1": {
                        "partidos": [
                            {
                                "num": 1,
                                "local": "Equipo Local",
                                "visitante": "Equipo Visitante",
                                "calendario": {
                                    "fecha": "2026-08-16",
                                    "hora": "21:00",
                                    "temporada": "2026/2027",
                                    "fuente": "proveedor oficial",
                                },
                                "cuotas": {"1": 1.80, "X": 3.40, "2": 4.80, "fuente": "bookmaker"},
                                "bajas": {
                                    "local": {
                                        "lesiones": [{"jugador": "Central titular", "impacto": 2.4, "titular": True}],
                                        "sanciones": ["Mediocentro"],
                                    },
                                    "visitante": {"dudas": [{"jugador": "Delantero", "impacto": 0.8}]},
                                },
                                "alineaciones": {
                                    "local": {"titulares_probables": [f"L{i}" for i in range(11)], "confianza": 0.82},
                                    "visitante": {"titulares_probables": [f"V{i}" for i in range(10)], "dudas": ["V9"]},
                                },
                                "clasificacion": {
                                    "temporada": "2026/2027",
                                    "local": {"posicion": 4, "puntos": 18},
                                    "visitante": {"posicion": 14, "puntos": 9},
                                    "fuente": "tabla oficial",
                                },
                            }
                        ]
                    }
                },
            },
            origen="test",
        )

        partido = buscar_partido(datos, 1, {"local": "Equipo Local", "visitante": "Equipo Visitante"})

        self.assertEqual(datos["estado_global"], "operativo")
        self.assertEqual(datos["temporada_objetivo"], "2026/2027")
        self.assertEqual(datos["resumen"]["cuotas"], 1)
        self.assertEqual(datos["resumen"]["bajas_estructuradas"], 1)
        self.assertEqual(datos["resumen"]["alineaciones_probables"], 1)
        self.assertEqual(datos["resumen"]["calendario_oficial"], 1)
        self.assertEqual(datos["resumen"]["clasificacion_oficial"], 1)
        self.assertAlmostEqual(sum(partido["cuotas"]["probabilidades_implicitas"].values()), 100.0, places=1)
        self.assertGreater(partido["bajas"]["local"]["impacto_total"], partido["bajas"]["visitante"]["impacto_total"])
        self.assertTrue(partido["capas_disponibles"]["clasificacion_oficial"])

    def test_api_football_payload_se_normaliza_para_motor(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            jornadas = root / "data" / "jornadas"
            jornadas.mkdir(parents=True)
            (jornadas / "jornada_1.json").write_text(
                json.dumps({
                    "jornada": 1,
                    "partidos": [
                        {
                            "num": 1,
                            "local": "Equipo Local",
                            "visitante": "Equipo Visitante",
                            "fecha": "2026-08-16",
                            "hora": "21:00",
                        }
                    ],
                }),
                encoding="utf-8",
            )
            cliente = FakeApiFootball()

            payload = leer_api_football_payload(
                "https://v3.football.api-sports.io",
                "token-test",
                root=root,
                requester=cliente,
            )
            datos = normalizar_payload(payload, origen="api_football")

        partido = buscar_partido(datos, 1, {"local": "Equipo Local", "visitante": "Equipo Visitante"})

        self.assertEqual(datos["estado_global"], "operativo")
        self.assertEqual(datos["resumen"]["cuotas"], 1)
        self.assertEqual(datos["resumen"]["bajas_estructuradas"], 1)
        self.assertEqual(datos["resumen"]["alineaciones_probables"], 1)
        self.assertEqual(datos["resumen"]["calendario_oficial"], 1)
        self.assertEqual(datos["resumen"]["clasificacion_oficial"], 1)
        self.assertEqual(partido["cuotas"]["proveedor"], "TestBook")
        self.assertEqual(partido["calendario"]["fuente"], "API-Football oficial")
        self.assertEqual(partido["clasificacion"]["local"]["posicion"], 4)
        self.assertTrue(all(call["headers"]["x-apisports-key"] == "token-test" for call in cliente.calls))

    def test_estado_cuenta_api_football_lee_plan_y_cuota(self):
        """/status es barato y esta disponible incluso en el plan gratuito
        -sirve para saber SI el token es valido y que cubre el plan, en vez
        de solo ver un 403 generico en /fixtures."""
        estado = estado_cuenta_api_football(
            "https://v3.football.api-sports.io", "token-test", requester=FakeApiFootball()
        )

        self.assertTrue(estado["ok"])
        self.assertEqual(estado["plan"], "Free")
        self.assertTrue(estado["activa"])
        self.assertEqual(estado["peticiones_usadas"], 47)
        self.assertEqual(estado["peticiones_limite"], 100)

    def test_estado_cuenta_api_football_maneja_fallo_de_conexion(self):
        class RequesterRoto:
            def get(self, *a, **k):
                raise RuntimeError("connection refused")

        estado = estado_cuenta_api_football(
            "https://v3.football.api-sports.io", "token-invalido", requester=RequesterRoto()
        )

        self.assertFalse(estado["ok"])
        self.assertIn("connection refused", estado["error"])

    def test_leer_api_football_payload_incluye_estado_cuenta(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            jornadas = root / "data" / "jornadas"
            jornadas.mkdir(parents=True)
            (jornadas / "jornada_1.json").write_text(
                json.dumps({"jornada": 1, "partidos": [{"num": 1, "local": "A", "visitante": "B"}]}),
                encoding="utf-8",
            )
            payload = leer_api_football_payload(
                "https://v3.football.api-sports.io", "token-test", root=root, requester=FakeApiFootball()
            )

        estado_cuenta = payload["proveedores"]["api_football"]["estado_cuenta"]
        self.assertTrue(estado_cuenta["ok"])
        self.assertEqual(estado_cuenta["plan"], "Free")

    def test_api_football_url_sin_token_espera_secret(self):
        with patch.dict(os.environ, {"QUINIHUB_PRO_DATA_URL": "https://v3.football.api-sports.io"}, clear=True):
            self.assertIsNone(leer_payload_externo())


if __name__ == "__main__":
    unittest.main()
