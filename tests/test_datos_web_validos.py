import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Carpetas cuyos .json carga index.html via getJson() -si un archivo de
# estas no es JSON estricto, el navegador (JSON.parse) lo rechaza EN
# SILENCIO (getJson devuelve el fallback) y la funcionalidad que dependa
# de el desaparece sin error visible. Bug real (01/09/2026):
# memoria_socio.json quedo con un caracter de control dentro de un string
# -Python lo tolera con strict=False, el navegador no- y el chat perdio
# la memoria del socio sin que nada lo avisara.
CARPETAS_WEB = [
    ROOT / "data",
    ROOT / "data" / "memoria_ia",
    ROOT / "data" / "jornadas",
    ROOT / "data" / "predicciones",
    ROOT / "data" / "premios",
]


class DatosWebValidosTests(unittest.TestCase):
    def test_todos_los_json_que_carga_la_web_son_json_estricto(self):
        errores = []
        vistos = 0
        for carpeta in CARPETAS_WEB:
            if not carpeta.is_dir():
                continue
            for path in sorted(carpeta.glob("*.json")):
                vistos += 1
                try:
                    # strict=True (el default) rechaza caracteres de control
                    # dentro de strings, igual que JSON.parse del navegador.
                    json.loads(path.read_text(encoding="utf-8"), strict=True)
                except Exception as exc:
                    errores.append(f"{path.relative_to(ROOT)}: {exc}")
        self.assertGreater(vistos, 10, "no se encontraron los datos -¿cambio la estructura de carpetas?")
        self.assertEqual(errores, [], "JSON invalido para el navegador:\n" + "\n".join(errores))

    def test_memoria_socio_tiene_el_bloque_que_usa_el_chat(self):
        path = ROOT / "data" / "memoria_ia" / "memoria_socio.json"
        data = json.loads(path.read_text(encoding="utf-8"), strict=True)
        bloque = data.get("bloque_para_chat")
        self.assertTrue(isinstance(bloque, str) and len(bloque) > 200,
                        "bloque_para_chat vacio o demasiado corto -el chat de la web se queda sin la memoria del socio")
        # Presupuesto de contexto: este bloque va al principio del contexto
        # del chat (recorte total de 6800 en consultas de datos) -si crece
        # sin control, expulsa a los datos reales de las jornadas y el
        # modelo vuelve a inventar (bug real del 01/09/2026).
        self.assertLess(len(bloque), 2600,
                        f"bloque_para_chat ocupa {len(bloque)} caracteres -recortalo, expulsa a los datos reales del contexto del chat")


if __name__ == "__main__":
    unittest.main()
