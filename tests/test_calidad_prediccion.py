import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PREDICCION = ROOT / "data" / "predicciones" / "ultima_prediccion.json"

SIGNOS_VALIDOS = {"1", "X", "2"}
LONGITUD_POR_TIPO = {"FIJO": 1, "DOBLE": 2, "TRIPLE": 3}


def cargar_prediccion():
    if not PREDICCION.exists():
        return None
    return json.loads(PREDICCION.read_text(encoding="utf-8"))


class CalidadPrediccionTests(unittest.TestCase):
    """Valida invariantes reales de la ultima prediccion publicada, no solo su estructura.

    Estos tests leen data/predicciones/ultima_prediccion.json tal cual esta en el
    repo. Si algun script del pipeline deja el boleto en un estado matematicamente
    incoherente (costes que no cuadran, Elige8 con menos de 8, un DOBLE con un solo
    signo...), esto falla aqui en vez de descubrirse jugando la quiniela.
    """

    def setUp(self):
        self.prediccion = cargar_prediccion()
        if not self.prediccion or not self.prediccion.get("partidos"):
            self.skipTest("No hay prediccion real disponible para validar (sin partidos).")
        self.partidos = self.prediccion["partidos"]

    def test_hay_exactamente_14_partidos_numerados_sin_huecos(self):
        nums = sorted(p["num"] for p in self.partidos)
        self.assertEqual(nums, list(range(1, 15)))

    def test_probabilidades_suman_100_por_partido(self):
        for p in self.partidos:
            probs = p.get("probabilidades") or {}
            total = sum(float(v) for v in probs.values())
            self.assertAlmostEqual(
                total, 100.0, delta=1.0,
                msg=f"Partido {p.get('num')}: probabilidades suman {total}, no ~100",
            )

    def test_signo_final_usa_solo_signos_validos(self):
        for p in self.partidos:
            signo_final = str(p.get("signo_final") or "")
            self.assertTrue(signo_final, f"Partido {p.get('num')} sin signo_final")
            self.assertTrue(
                set(signo_final) <= SIGNOS_VALIDOS,
                f"Partido {p.get('num')}: signo_final '{signo_final}' tiene caracteres invalidos",
            )

    def test_tipo_coincide_con_longitud_de_signo_final(self):
        for p in self.partidos:
            tipo = p.get("tipo")
            signo_final = str(p.get("signo_final") or "")
            esperado = LONGITUD_POR_TIPO.get(tipo)
            self.assertIsNotNone(esperado, f"Partido {p.get('num')}: tipo desconocido '{tipo}'")
            self.assertEqual(
                len(signo_final), esperado,
                f"Partido {p.get('num')}: tipo={tipo} pero signo_final='{signo_final}' "
                f"tiene longitud {len(signo_final)}",
            )

    def test_signo_base_esta_incluido_en_signo_final(self):
        for p in self.partidos:
            signo_base = p.get("signo_base")
            signo_final = str(p.get("signo_final") or "")
            if signo_base:
                self.assertIn(
                    signo_base, signo_final,
                    f"Partido {p.get('num')}: signo_base '{signo_base}' no esta "
                    f"cubierto por signo_final '{signo_final}'",
                )

    def test_elige8_marca_exactamente_8_partidos(self):
        elegidos = [p for p in self.partidos if p.get("en_elige8") or p.get("elige8")]
        if not elegidos:
            self.skipTest("Elige8 no parece estar calculado en esta prediccion (posiblemente bloqueada).")
        self.assertEqual(len(elegidos), 8, f"Elige8 deberia tener 8 partidos, tiene {len(elegidos)}")

    def test_coste_es_coherente_con_dobles_y_triples(self):
        coste = self.prediccion.get("coste") or {}
        if not coste:
            self.skipTest("No hay bloque de coste calculado en esta prediccion.")
        tipos = [p.get("tipo") for p in self.partidos]
        dobles = tipos.count("DOBLE")
        triples = tipos.count("TRIPLE")
        apuestas_esperadas = (2 ** dobles) * (3 ** triples)
        self.assertEqual(
            coste.get("apuestas"), apuestas_esperadas,
            f"coste.apuestas={coste.get('apuestas')} pero {dobles} dobles y "
            f"{triples} triples dan {apuestas_esperadas} apuestas",
        )
        importe_esperado = round(max(apuestas_esperadas * 0.75, 1.50), 2)
        self.assertAlmostEqual(
            coste.get("importe_quiniela", 0), importe_esperado, delta=0.01,
            msg=f"importe_quiniela no coincide con {apuestas_esperadas} apuestas a 0.75e (minimo 1.50e)",
        )


if __name__ == "__main__":
    unittest.main()
