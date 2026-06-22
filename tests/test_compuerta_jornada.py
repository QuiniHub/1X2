import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compuerta_jornada import estado_compuerta, normalizar_estado_publicacion


def escribir_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def jornada(numero, cerrada=True):
    return {
        "jornada": numero,
        "partidos": [
            {
                "num": idx + 1,
                "local": f"Local {idx + 1}",
                "visitante": f"Visitante {idx + 1}",
                "resultado": "1-0" if cerrada else "Pendiente",
                "signo_oficial": "1" if cerrada else "Pendiente",
            }
            for idx in range(14)
        ],
    }


class CompuertaJornadaTests(unittest.TestCase):
    def test_bloquea_si_jornada_anterior_no_esta_cerrada(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data = Path(tmp_dir) / "data"
            escribir_json(data / "jornadas" / "jornada_1.json", jornada(1, cerrada=False))

            estado = estado_compuerta(2, data)

            self.assertFalse(estado["prediccion_permitida"])
            self.assertEqual(estado["estado"], "bloqueada")
            self.assertTrue(estado["publicar_solo_boleto"])
            self.assertFalse(estado["publicar_prediccion"])

    def test_aprendiendo_si_jornada_anterior_cerrada_sin_memoria(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            data = Path(tmp_dir) / "data"
            escribir_json(data / "jornadas" / "jornada_1.json", jornada(1, cerrada=True))

            estado = estado_compuerta(2, data)

            self.assertFalse(estado["prediccion_permitida"])
            self.assertEqual(estado["estado"], "aprendiendo")
            self.assertIn("Aprendizaje pendiente", estado["motivo"])

    def test_prediccion_no_disponible_no_puede_quedar_lista(self):
        estado = normalizar_estado_publicacion({
            "prediccion_disponible": False,
            "estado": "lista_para_publicar",
            "aprendizaje_pendiente": True,
        })

        self.assertEqual(estado["estado"], "aprendiendo")
        self.assertTrue(estado["publicar_solo_boleto"])
        self.assertFalse(estado["publicar_prediccion"])


if __name__ == "__main__":
    unittest.main()
