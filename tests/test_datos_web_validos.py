import json
import os
import re
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
DATA = ROOT / "data"
INDEX = ROOT / "index.html"

# Auditoria 26/11 (revision): main.yml ejecuta TODA la carpeta tests ANTES del
# pipeline. Un test que falle ahi deja de publicar la web cada 30 minutos, y el
# pipeline (que es quien regeneraria el fichero) ya no se ejecuta. Por eso las
# comprobaciones que no protegen lo que la web carga no corren en el cron
# (GITHUB_EVENT_NAME schedule / workflow_dispatch): corren en local y en
# ci-pr.yml.
EN_CRON_DE_PUBLICACION = os.environ.get("GITHUB_EVENT_NAME") in ("schedule", "workflow_dispatch")
# Tras el pipeline (paso "Comprobar el boleto recien generado") si corren:
# ahi un fallo impide el commit del ciclo que lo genera en vez de atascar el
# siguiente.
POST_PIPELINE = os.environ.get("QUINIELA_POST_PIPELINE") == "1"
SOLO_FUERA_DEL_CRON = unittest.skipIf(
    EN_CRON_DE_PUBLICACION and not POST_PIPELINE,
    "no bloquea el cron antes del pipeline; corre en local, en PR y tras el pipeline")


def _constante_no_json(nombre):
    raise ValueError(f"constante {nombre} no es JSON valido (JSON.parse del navegador la rechaza)")


def cargar_como_navegador(texto):
    """json.loads tan estricto como JSON.parse del navegador.

    json.loads(strict=True) solo rechaza caracteres de control dentro de
    strings: ACEPTA NaN, Infinity y -Infinity, que json.dumps emite por
    defecto (allow_nan=True) y que JSON.parse rechaza. parse_constant recibe
    justo esas tres constantes, asi que basta con que lance (auditoria 26/11,
    hallazgo 206)."""
    return json.loads(texto, strict=True, parse_constant=_constante_no_json)


def rutas_literales_getjson(html):
    """Rutas fijas que index.html pide con getJson('data/....json')."""
    return sorted(set(re.findall(r"getJson\(\s*['\"](data/[^'\"`$]+\.json)['\"]", html)))


def carpetas_de_plantillas_getjson(html):
    """Carpetas de las rutas en plantilla: getJson(`data/jornadas/jornada_${n}.json`)
    -> 'data/jornadas'. Solo se puede conocer la carpeta (el prefijo fijo hasta
    la ultima barra antes del primer ${...})."""
    carpetas = set()
    for ruta in re.findall(r"getJson\(\s*`(data/[^`]*)`", html):
        fijo = ruta.split("${", 1)[0]
        carpetas.add(fijo.rsplit("/", 1)[0])
    return sorted(carpetas)


class CargarComoNavegadorTests(unittest.TestCase):
    """El validador, probado con fixtures (no depende de los datos del repo)."""

    def test_rechaza_nan_infinity_y_menos_infinity(self):
        for texto in ('{"a": NaN}', '{"a": Infinity}', '{"a": -Infinity}', '[1, NaN]'):
            with self.subTest(texto=texto):
                # El json.loads de antes lo daba por bueno:
                json.loads(texto, strict=True)
                with self.assertRaises(ValueError):
                    cargar_como_navegador(texto)

    def test_rechaza_caracter_de_control_dentro_de_un_string(self):
        with self.assertRaises(ValueError):
            cargar_como_navegador('{"a": "linea1\nlinea2"}')

    def test_acepta_json_normal_y_las_palabras_dentro_de_strings(self):
        datos = cargar_como_navegador('{"a": 1.5, "b": null, "c": "NaN e Infinity como texto", "d": -3}')
        self.assertEqual(datos["a"], 1.5)
        self.assertIsNone(datos["b"])
        self.assertEqual(datos["c"], "NaN e Infinity como texto")

    def test_extrae_las_rutas_literales_de_getjson(self):
        html = (
            "await getJson('data/predicciones/ultima_prediccion.json');\n"
            "await getJson(\"data/quinielas_jugadas.json\", null);\n"
            "await getJson(`data/jornadas/jornada_${n}.json`, null);\n"
        )
        self.assertEqual(rutas_literales_getjson(html), [
            "data/predicciones/ultima_prediccion.json",
            "data/quinielas_jugadas.json",
        ])

    def test_extrae_la_carpeta_de_las_rutas_en_plantilla(self):
        html = (
            "await getJson(`data/jornadas/jornada_${n}.json`, null);\n"
            "await getJson(`data/jornadas/detalles_j${n}.json`, null);\n"
            "await getJson(`data/${carpeta}/x.json`);\n"
            "await getJson('data/quinielas_jugadas.json');\n"
        )
        self.assertEqual(carpetas_de_plantillas_getjson(html), ["data", "data/jornadas"])


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
                    # Caracteres de control dentro de strings, NaN e Infinity:
                    # todo lo que JSON.parse del navegador rechaza.
                    cargar_como_navegador(path.read_text(encoding="utf-8"))
                except Exception as exc:
                    errores.append(f"{path.relative_to(ROOT)}: {exc}")
        self.assertGreater(vistos, 10, "no se encontraron los datos -¿cambio la estructura de carpetas?")
        self.assertEqual(errores, [], "JSON invalido para el navegador:\n" + "\n".join(errores))

    @SOLO_FUERA_DEL_CRON
    def test_ningun_json_de_data_tiene_nan_ni_infinity(self):
        # Barrido de TODO data/. No corre en el cron antes del pipeline: un NaN
        # en una subcarpeta que la web no carga atascaria la publicacion sin
        # que el pipeline pudiera regenerarlo.
        # Tambien las subcarpetas (backtesting/pre_cierre, porcentajes_lae/...,
        # temporadas/...): no las carga la web directamente, pero el pipeline
        # copia valores de ahi a los JSON que si carga, y un NaN se propaga.
        errores = []
        vistos = 0
        for path in sorted(DATA.rglob("*.json")):
            vistos += 1
            try:
                cargar_como_navegador(path.read_text(encoding="utf-8-sig"))
            except ValueError as exc:
                errores.append(f"{path.relative_to(ROOT)}: {exc}")
        self.assertGreater(vistos, 10)
        self.assertEqual(errores, [], "JSON no estricto dentro de data/:\n" + "\n".join(errores))

    @SOLO_FUERA_DEL_CRON
    def test_las_rutas_fijas_de_getjson_apuntan_a_carpetas_validadas(self):
        # Si la web empieza a cargar un JSON de una carpeta nueva, este test
        # obliga a que quede cubierta por la validacion estricta de arriba.
        rutas = rutas_literales_getjson(INDEX.read_text(encoding="utf-8"))
        self.assertGreater(len(rutas), 10, "no se encontraron llamadas getJson en index.html")
        carpetas = {c.resolve() for c in CARPETAS_WEB}
        fuera = [r for r in rutas if (ROOT / r).parent.resolve() not in carpetas]
        # Rutas en plantilla (`data/jornadas/jornada_${n}.json`): solo la carpeta.
        fuera += [c + "/..." for c in carpetas_de_plantillas_getjson(INDEX.read_text(encoding="utf-8"))
                  if (ROOT / c).resolve() not in carpetas]
        self.assertEqual(fuera, [], "getJson carga rutas fuera de CARPETAS_WEB: " + ", ".join(fuera))

    def test_memoria_socio_tiene_el_bloque_que_usa_el_chat(self):
        path = ROOT / "data" / "memoria_ia" / "memoria_socio.json"
        data = cargar_como_navegador(path.read_text(encoding="utf-8"))
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
