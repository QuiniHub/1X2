import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_fuente_lesiones_laliga as afl


# Fragmento calcado del HTML real de futbolfantasy.com/laliga/lesionados
# (capturado en vivo el 2026-07-18), cubriendo las 3 categorias reales:
# lesionado (gravedad-0), duda (gravedad-1) y disponible (gravedad-2).
HTML_REAL = """
<html><body>
<section class="mod lesionados col-12 col-md-6 mb-4">
    <div class="container"><div class="row block-new">
    <header class="title col-12"><img class="icono" src="//x/1.png"> Athletic</header>
    <div class="elemento lesionado col-12">
        <div class="d-flex pl-0 imagen-c camiseta">
            <div class="fotocontainer laliga my-2 gravedad-0">
                <a href="https://www.futbolfantasy.com/jugadores/unai-egiluz"></a>
            </div>
            <div class="icono-wrapper">
                <span class="lesion" style="bottom:0px;">
                    <img src="https://static.futbolfantasy.com/uploads/images/lesionado_box_min.png" />
                </span>
                <span class="probabilidad-widget"><span class="prob-0 prob-0">0%</span></span>
            </div>
        </div>
        <div class=" with-links  d-flex datos-c">
            <div class="datos">
                <a href="https://www.futbolfantasy.com/jugadores/unai-egiluz" class="jugador">Unai Egiluz</a>
                <div class="comentario">
                    <span class="lesion">Rotura de lig. cruzado anterior</span>
                    <span><i class="far fa-calendar"></i> Desde 15/05 (64 dias)</span>
                    <span class="gravedad-0">Baja hasta enero 2027</span>
                </div>
            </div>
        </div>
        <div class="links links-c">
            <a href="https://www.futbolfantasy.com/laliga/noticias/144996" class="lesion link">
                <span class="fas fa-file-medical"></span>
                <span class="label">Parte medico</span>
            </a>
        </div>
    </div>
    <div class="elemento lesionado col-12">
        <div class="d-flex pl-0 imagen-c camiseta">
            <div class="fotocontainer laliga my-2 gravedad-1">
                <a href="https://www.futbolfantasy.com/jugadores/maroan-sannadi"></a>
            </div>
            <div class="icono-wrapper">
                <span class="lesion" style="bottom:0px;">
                    <img src="https://static.futbolfantasy.com/uploads/images/duda_box_min.png" />
                </span>
                <span class="probabilidad-widget"><span class="prob-0 prob-0">0%</span></span>
            </div>
        </div>
        <div class=" with-links  d-flex datos-c">
            <div class="datos">
                <a href="https://www.futbolfantasy.com/jugadores/maroan-sannadi" class="jugador">Maroan Sannadi</a>
                <div class="comentario">
                    <span class="lesion">Lesion de rodilla</span>
                    <span><i class="far fa-calendar"></i> Desde 15/07 (3 dias)</span>
                    <span class="gravedad-1">Duda para la jornada 0</span>
                </div>
            </div>
        </div>
    </div>
    <div class="elemento lesionado col-12">
        <div class="d-flex pl-0 imagen-c camiseta">
            <div class="fotocontainer laliga my-2 gravedad-2">
                <a href="https://www.futbolfantasy.com/jugadores/andoni-gorosabel"></a>
            </div>
            <div class="icono-wrapper">
                <span class="lesion" style="bottom:0px;">
                    <img src="https://static.futbolfantasy.com/uploads/images/disponible_box_min.png" />
                </span>
                <span class="probabilidad-widget"><span class="prob-0 prob-0">70%</span></span>
            </div>
        </div>
        <div class=" with-links  d-flex datos-c">
            <div class="datos">
                <a href="https://www.futbolfantasy.com/jugadores/andoni-gorosabel" class="jugador">Andoni Gorosabel</a>
                <div class="comentario">
                    <span class="lesion">Lesion en el aductor</span>
                    <span><i class="far fa-calendar"></i> Desde 06/07 (12 dias)</span>
                    <span class="gravedad-2">Disponible para la jornada 0</span>
                </div>
            </div>
        </div>
    </div>
    </div></div>
</section>
<section class="mod lesionados col-12 col-md-6 mb-4">
    <div class="container"><div class="row block-new">
    <header class="title col-12"><img class="icono" src="//x/2.png"> Atletico</header>
    <div class="elemento lesionado col-12">
        <div class="d-flex pl-0 imagen-c camiseta">
            <div class="fotocontainer laliga my-2 gravedad-1">
                <a href="https://www.futbolfantasy.com/jugadores/morten-hjulmand"></a>
            </div>
            <div class="icono-wrapper">
                <span class="lesion"><img src="https://static.futbolfantasy.com/uploads/images/duda_box_min.png" /></span>
                <span class="probabilidad-widget"><span class="prob-0 prob-0">60%</span></span>
            </div>
        </div>
        <div class=" with-links  d-flex datos-c">
            <div class="datos">
                <a href="https://www.futbolfantasy.com/jugadores/morten-hjulmand" class="jugador">Morten Hjulmand</a>
                <div class="comentario">
                    <span class="lesion">Contusion</span>
                    <span><i class="far fa-calendar"></i> Desde 15/07 (3 dias)</span>
                    <span class="gravedad-1">Disponible para la jornada 0</span>
                </div>
            </div>
        </div>
    </div>
    </div></div>
</section>
</body></html>
"""


class ExtraerLesionadosTests(unittest.TestCase):
    def test_extrae_los_2_equipos_con_sus_jugadores(self):
        equipos = afl.extraer_lesionados(HTML_REAL)
        self.assertEqual(set(equipos.keys()), {"Athletic", "Atletico"})
        self.assertEqual(len(equipos["Athletic"]), 3)
        self.assertEqual(len(equipos["Atletico"]), 1)

    def test_categoria_se_lee_del_icono_no_del_texto(self):
        equipos = afl.extraer_lesionados(HTML_REAL)
        por_categoria = {j["jugador"]: j["categoria"] for j in equipos["Athletic"]}
        self.assertEqual(por_categoria["Unai Egiluz"], "lesionado")
        self.assertEqual(por_categoria["Maroan Sannadi"], "duda")
        self.assertEqual(por_categoria["Andoni Gorosabel"], "disponible")

    def test_campos_completos_del_jugador_lesionado(self):
        equipos = afl.extraer_lesionados(HTML_REAL)
        egiluz = next(j for j in equipos["Athletic"] if j["jugador"] == "Unai Egiluz")
        self.assertEqual(egiluz["gravedad"], 0)
        self.assertEqual(egiluz["probabilidad_disponibilidad"], 0.0)
        self.assertEqual(egiluz["lesion"], "Rotura de lig. cruzado anterior")
        self.assertEqual(egiluz["dias"], 64)
        self.assertIn("Desde 15/05", egiluz["fecha_texto"])
        self.assertEqual(egiluz["estado_texto"], "Baja hasta enero 2027")
        self.assertEqual(egiluz["enlace_tipo"], "Parte medico")
        self.assertTrue(egiluz["enlace_url"].startswith("https://"))

    def test_jugador_disponible_sin_enlace_no_falla(self):
        equipos = afl.extraer_lesionados(HTML_REAL)
        gorosabel = next(j for j in equipos["Athletic"] if j["jugador"] == "Andoni Gorosabel")
        self.assertEqual(gorosabel["probabilidad_disponibilidad"], 70.0)
        self.assertIsNone(gorosabel["enlace_url"])

    def test_html_vacio_no_falla(self):
        self.assertEqual(afl.extraer_lesionados("<html><body>sin secciones</body></html>"), {})


class FusionarConAnteriorTests(unittest.TestCase):
    def test_conserva_datos_previos_si_scrape_nuevo_vacio(self):
        anterior = {"equipos": {"Athletic": [{"jugador": "X"}]}}
        salida = afl.fusionar_con_anterior(anterior, {}, ["aviso de prueba"])
        self.assertEqual(salida["equipos"], anterior["equipos"])
        self.assertTrue(salida["conserva_datos_previos"])

    def test_usa_datos_nuevos_si_hay(self):
        anterior = {"equipos": {"Athletic": [{"jugador": "Viejo"}]}}
        nuevos = {"Barcelona": [{"jugador": "Nuevo"}]}
        salida = afl.fusionar_con_anterior(anterior, nuevos, [])
        self.assertEqual(salida["equipos"], nuevos)
        self.assertFalse(salida["conserva_datos_previos"])


class ExtraerConMockTests(unittest.TestCase):
    def setUp(self):
        self._original_descargar = afl.descargar
        self._original_salida = afl.SALIDA

    def tearDown(self):
        afl.descargar = self._original_descargar
        afl.SALIDA = self._original_salida

    def test_main_no_falla_si_la_web_da_error(self):
        def _romper(url):
            raise RuntimeError("timeout simulado")
        afl.descargar = _romper
        with tempfile.TemporaryDirectory() as tmp_dir:
            afl.SALIDA = Path(tmp_dir) / "fuente_lesiones_laliga.json"
            afl.main()  # no debe lanzar excepcion
            salida = afl.cargar_json(afl.SALIDA, {})
            self.assertTrue(salida["avisos"])
            self.assertTrue(salida["conserva_datos_previos"])

    def test_main_guarda_datos_reales_si_la_web_responde(self):
        def _fake_get(url):
            return HTML_REAL
        afl.descargar = _fake_get
        with tempfile.TemporaryDirectory() as tmp_dir:
            afl.SALIDA = Path(tmp_dir) / "fuente_lesiones_laliga.json"
            afl.main()
            salida = afl.cargar_json(afl.SALIDA, {})
            self.assertEqual(set(salida["equipos"].keys()), {"Athletic", "Atletico"})
            self.assertFalse(salida["conserva_datos_previos"])


if __name__ == "__main__":
    unittest.main()
