import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_fuente_lesiones_jornadaperfecta as afj


# Fragmento calcado del HTML real de jornadaperfecta.com/lesionados/
# (capturado en vivo el 2026-07-18): un equipo sano (icono tick, sin
# jugadores), y un equipo con un lesionado y una duda.
HTML_REAL = """
<html><body>
<div class=""><div class="lesionados"><div class="lesionados-equipo">
    <div class="lesionados-equipo-escudo"><img src="https://cdn.biwenger.com/i/t/91.png" title="Alaves" id="Alaves"/></div>
    <div class="lesionados-equipo-nombre"><a href='https://www.jornadaperfecta.com/equipo/alaves'>Alaves</a></div>
</div><div class="clear"></div>
<div class="lesionados-jugador">
    <div class="lesionados-jugador-sanos">
        <img src="https://www.jornadaperfecta.com/assets/images/iconos/tick.png"/>
        <div class="lesionados-jugador-sanos-frase">Ningun jugador lesionado o duda para el proximo partido</div>
    </div>
</div>
</div></div>
<div class=""><div class="lesionados"><div class="lesionados-equipo">
    <div class="lesionados-equipo-escudo"><img src="https://cdn.biwenger.com/i/t/1.png" title="Athletic" id="Athletic"/></div>
    <div class="lesionados-equipo-nombre"><a href='https://www.jornadaperfecta.com/equipo/athletic'>Athletic</a></div>
</div><div class="clear"></div>
<div class="lesionados-jugador" style="display:flex">
    <div class="lesionados-jugador-iconos">
        <img src='/assets/images/iconos/disponible.jpg' title='Disponible en observacion' alt='Disponible en observacion'/>
        <div class="jugador-posicion df">DF</div>
    </div>
    <div style="width:100%">
        <a href="https://www.jornadaperfecta.com/jugador/gorosabel"><img class="lesionados-jugador-foto" src="https://cdn.biwenger.com/i/p/15462.png"/></a>
        <div class="lesionados-jugador-nombre">
            <a href='https://www.jornadaperfecta.com/jugador/gorosabel'>Gorosabel</a>
            <div class="lesionados-jugador-motivo">Lesion en su aductor mediano del lado derecho</div>
        </div>
    </div>
</div>
<div class="lesionados-jugador" style="display:flex">
    <div class="lesionados-jugador-iconos">
        <img src='/assets/images/iconos/lesion.png' title='Lesionado' alt='Lesionado'/>
        <div class="jugador-posicion pt">PT</div>
    </div>
    <div style="width:100%">
        <a href="https://www.jornadaperfecta.com/jugador/egiluz"><img class="lesionados-jugador-foto" src="https://cdn.biwenger.com/i/p/1.png"/></a>
        <div class="lesionados-jugador-nombre">
            <a href='https://www.jornadaperfecta.com/jugador/egiluz'>Egiluz</a>
            <div class="lesionados-jugador-motivo">Rotura de ligamento cruzado anterior</div>
        </div>
    </div>
</div>
</div></div>
</body></html>
"""


class ExtraerLesionadosTests(unittest.TestCase):
    def test_equipo_sano_no_aparece_en_el_resultado(self):
        equipos = afj.extraer_lesionados(HTML_REAL)
        self.assertNotIn("Alaves", equipos)

    def test_equipo_con_jugadores_incluye_ambos(self):
        equipos = afj.extraer_lesionados(HTML_REAL)
        self.assertIn("Athletic", equipos)
        self.assertEqual(len(equipos["Athletic"]), 2)

    def test_categoria_se_lee_del_icono(self):
        equipos = afj.extraer_lesionados(HTML_REAL)
        por_categoria = {j["jugador"]: j["categoria"] for j in equipos["Athletic"]}
        self.assertEqual(por_categoria["Gorosabel"], "disponible")
        self.assertEqual(por_categoria["Egiluz"], "lesionado")

    def test_campos_completos_del_jugador(self):
        equipos = afj.extraer_lesionados(HTML_REAL)
        egiluz = next(j for j in equipos["Athletic"] if j["jugador"] == "Egiluz")
        self.assertEqual(egiluz["lesion"], "Rotura de ligamento cruzado anterior")
        self.assertTrue(egiluz["jugador_url"].startswith("https://"))

    def test_html_vacio_no_falla(self):
        self.assertEqual(afj.extraer_lesionados("<html><body>sin bloques</body></html>"), {})


class FusionarConAnteriorTests(unittest.TestCase):
    def test_conserva_datos_previos_si_scrape_nuevo_vacio(self):
        anterior = {"equipos": {"Athletic": [{"jugador": "X"}]}}
        salida = afj.fusionar_con_anterior(anterior, {}, ["aviso de prueba"])
        self.assertEqual(salida["equipos"], anterior["equipos"])
        self.assertTrue(salida["conserva_datos_previos"])

    def test_usa_datos_nuevos_si_hay(self):
        anterior = {"equipos": {"Athletic": [{"jugador": "Viejo"}]}}
        nuevos = {"Barcelona": [{"jugador": "Nuevo"}]}
        salida = afj.fusionar_con_anterior(anterior, nuevos, [])
        self.assertEqual(salida["equipos"], nuevos)
        self.assertFalse(salida["conserva_datos_previos"])


class ExtraerConMockTests(unittest.TestCase):
    def setUp(self):
        self._original_descargar = afj.descargar
        self._original_salida = afj.SALIDA

    def tearDown(self):
        afj.descargar = self._original_descargar
        afj.SALIDA = self._original_salida

    def test_main_no_falla_si_la_web_da_error(self):
        def _romper(url):
            raise RuntimeError("timeout simulado")
        afj.descargar = _romper
        with tempfile.TemporaryDirectory() as tmp_dir:
            afj.SALIDA = Path(tmp_dir) / "fuente_lesiones_jornadaperfecta.json"
            afj.main()
            salida = afj.cargar_json(afj.SALIDA, {})
            self.assertTrue(salida["avisos"])
            self.assertTrue(salida["conserva_datos_previos"])

    def test_main_guarda_datos_reales_si_la_web_responde(self):
        def _fake_get(url):
            return HTML_REAL
        afj.descargar = _fake_get
        with tempfile.TemporaryDirectory() as tmp_dir:
            afj.SALIDA = Path(tmp_dir) / "fuente_lesiones_jornadaperfecta.json"
            afj.main()
            salida = afj.cargar_json(afj.SALIDA, {})
            self.assertEqual(set(salida["equipos"].keys()), {"Athletic"})
            self.assertFalse(salida["conserva_datos_previos"])


if __name__ == "__main__":
    unittest.main()
