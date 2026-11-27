"""Auditoria 26/11, hallazgo 213: requirements.txt declaraba pandas (no lo
importa ningun .py) y el README omitia scipy (que si es obligatorio).

Este test compara requirements.txt con los imports REALES de los .py de la
raiz del repo: todo paquete externo importado tiene que estar declarado, y
todo lo declarado tiene que usarse. Solo lee ficheros de codigo; no instala
ni importa nada.
"""
import ast
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = ROOT / "requirements.txt"
README = ROOT / "README.md"

# Auditoria 26/11 (revision): main.yml ejecuta TODA la carpeta tests ANTES del
# pipeline. Un test que falle ahi deja de publicar la web cada 30 minutos, y el
# pipeline (que es quien regeneraria el fichero) ya no se ejecuta. Por eso las
# comprobaciones que no protegen lo que la web carga no corren en el cron
# (GITHUB_EVENT_NAME schedule / workflow_dispatch): corren en local y en
# ci-pr.yml.
EN_CRON_DE_PUBLICACION = os.environ.get("GITHUB_EVENT_NAME") in ("schedule", "workflow_dispatch")

# nombre con el que se importa -> nombre del paquete en pip
IMPORT_A_PAQUETE = {
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
}
# paquetes que se usan sin 'import' (se pide por nombre a otra libreria)
USO_INDIRECTO = {
    "lxml": re.compile(r"BeautifulSoup\([^)]*['\"]lxml['\"]"),
}


def paquetes_declarados(texto):
    paquetes = []
    for linea in texto.splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        nombre = re.split(r"[<>=!~\[; ]", linea, maxsplit=1)[0].strip().lower()
        if nombre:
            paquetes.append(nombre)
    return paquetes


def modulos_importados(codigo):
    """Nombres de primer nivel importados en un fuente Python."""
    nombres = set()
    for nodo in ast.walk(ast.parse(codigo)):
        if isinstance(nodo, ast.Import):
            nombres.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            nombres.add(nodo.module.split(".")[0])
    return nombres


def _fuentes():
    return sorted(p for p in ROOT.glob("*.py"))


def _externos_usados():
    locales = {p.stem for p in _fuentes()} | {"tests"}
    estandar = set(sys.stdlib_module_names)
    usados = {}
    for ruta in _fuentes():
        codigo = ruta.read_text(encoding="utf-8-sig", errors="replace")
        try:
            importados = modulos_importados(codigo)
        except SyntaxError:
            continue  # otro equipo puede tener el fichero a medio editar
        for nombre in importados:
            if nombre in locales or nombre in estandar or nombre.startswith("_"):
                continue
            usados.setdefault(IMPORT_A_PAQUETE.get(nombre, nombre).lower(), ruta.name)
        for paquete, patron in USO_INDIRECTO.items():
            if patron.search(codigo):
                usados.setdefault(paquete, ruta.name)
    return usados


class ParserTests(unittest.TestCase):
    def test_paquetes_declarados_ignora_comentarios_y_versiones(self):
        texto = "# cabecera\nnumpy>=1.26,<3\nscikit-learn==1.4.0  # nota\n\nlxml\nrequests[socks]>=2\n"
        self.assertEqual(paquetes_declarados(texto), ["numpy", "scikit-learn", "lxml", "requests"])

    def test_modulos_importados_solo_primer_nivel_y_absolutos(self):
        codigo = "import os, numpy.linalg\nfrom scipy.optimize import minimize\nfrom . import vecino\n"
        self.assertEqual(modulos_importados(codigo), {"os", "numpy", "scipy"})


@unittest.skipIf(EN_CRON_DE_PUBLICACION,
                 "test documental: no debe parar la publicacion automatica")
class RequirementsTests(unittest.TestCase):
    def setUp(self):
        self.declarados = paquetes_declarados(REQUIREMENTS.read_text(encoding="utf-8"))
        self.usados = _externos_usados()

    def test_sin_duplicados(self):
        self.assertEqual(len(self.declarados), len(set(self.declarados)))

    def test_todo_lo_importado_esta_declarado(self):
        faltan = {p: f for p, f in self.usados.items() if p not in self.declarados}
        self.assertEqual(faltan, {}, "paquetes importados que faltan en requirements.txt")

    def test_todo_lo_declarado_se_usa(self):
        sobran = [p for p in self.declarados if p not in self.usados]
        self.assertEqual(sobran, [], "paquetes en requirements.txt que ningun .py usa")

    def test_ninguna_version_exacta_que_pueda_romper_el_ci(self):
        # El CI corre en Python 3.11 y el PC en otra version: un '==' puede no
        # tener rueda para las dos. Se admiten minimos y topes de version mayor.
        lineas = [l.split("#", 1)[0].strip() for l in REQUIREMENTS.read_text(encoding="utf-8").splitlines()]
        exactas = [l for l in lineas if "==" in l]
        self.assertEqual(exactas, [])

    def test_el_readme_lista_las_mismas_dependencias(self):
        readme = README.read_text(encoding="utf-8").lower()
        faltan = [p for p in self.declarados if p not in readme]
        self.assertEqual(faltan, [], "dependencias de requirements.txt que el README no menciona")
        self.assertNotIn("pandas", readme)


if __name__ == "__main__":
    unittest.main()
