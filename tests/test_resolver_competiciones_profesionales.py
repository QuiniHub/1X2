import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resolver_competiciones_profesionales import normalizar, resolver


class ResolverCompeticionesProfesionalesTests(unittest.TestCase):
    def test_abreviaturas_espanolas_no_caen_en_liga_extranjera(self):
        cats = {
            "primera": {"girona", "rayo vallecano madrid", "oviedo", "villarreal"},
            "segunda": set(),
            "mundial": set(),
            "selecciones": set(),
        }

        self.assertEqual(normalizar("R. Vallecano"), "rayo vallecano madrid")
        self.assertEqual(normalizar("R. Oviedo"), "oviedo")
        self.assertEqual(
            resolver({"local": "Girona", "visitante": "R. Vallecano"}, cats)["competicion"],
            "primera_division",
        )
        self.assertEqual(
            resolver({"local": "Villarreal", "visitante": "R. Oviedo"}, cats)["competicion"],
            "primera_division",
        )

    def test_liga_f_se_detecta_por_el_propio_nombre_del_club(self):
        # Aviso de Marc el 2026-08-25, antes de que empiece la Jornada 3:
        # la Quiniela va a incluir partidos de Liga F (futbol femenino). El
        # pipeline no tiene clasificacion/historico/forma propios para esa
        # competicion -debe reconocerla (no caer en liga_extranjera con
        # confianza 0.62 como si fuera una liga extranjera cualquiera) y
        # marcar confianza baja de verdad.
        cats = {"primera": set(), "segunda": set(), "mundial": set(), "selecciones": set()}
        info = resolver({"local": "Athletic Club Femenino", "visitante": "Real Madrid Femenino"}, cats)
        self.assertEqual(info["competicion"], "liga_f")
        self.assertLess(info["confianza"], 0.5)

    def test_liga_f_no_colisiona_con_el_club_masculino_homonimo(self):
        # "Real Madrid Femenino" comparte nombre de club con "Real Madrid CF"
        # (Primera) -si el club masculino estuviera en el catalogo de Primera,
        # el partido NO debe clasificarse como primera_division solo porque
        # las palabras "real"/"madrid" coincidan.
        cats = {"primera": {"madrid", "barcelona"}, "segunda": set(), "mundial": set(), "selecciones": set()}
        info = resolver({"local": "Real Madrid Femenino", "visitante": "FC Barcelona Femeni"}, cats)
        self.assertEqual(info["competicion"], "liga_f")

    def test_liga_f_formato_real_con_sufijo_f_entre_parentesis(self):
        # Formato REAL confirmado en data/jornadas/jornada_3.json (fuente
        # quinielafutbol.info): los partidos de Liga F llevan un sufijo
        # "(F)" -ej. "Athletic Club (F)", "Real Madrid (F)"- no la palabra
        # "Femenino" completa como se habia asumido al principio (commit
        # 7b9aa6d12). Sin este caso, el fix original no habria funcionado
        # con los datos reales de la propia Jornada 3.
        cats = {"primera": {"athletic", "madrid"}, "segunda": set(), "mundial": set(), "selecciones": set()}
        info = resolver({"local": "Athletic Club (F)", "visitante": "Badalona (F)"}, cats)
        self.assertEqual(info["competicion"], "liga_f")
        info2 = resolver({"local": "Real Madrid (F)", "visitante": "Atlético de Madrid (F)"}, cats)
        self.assertEqual(info2["competicion"], "liga_f")
        self.assertNotEqual(info2["competicion"], "primera_division")
        self.assertNotEqual(info["competicion"], "primera_division")

    def test_celta_b_no_cae_en_liga_extranjera(self):
        # Bug real (jornada 1 de LaLiga 26/27, 2026-08-11): la fuente de
        # quinielafutbol.info usa el nombre antiguo "Celta B" para el filial
        # del Celta en Segunda -sin el alias, no coincidia con "RC Celta
        # Fortuna" (el nombre real en clasificaciones.json) y el partido
        # caia en liga_extranjera, activando el modelo equivocado.
        cats = {
            "primera": set(),
            "segunda": {"cadiz", "celta fortuna"},
            "mundial": set(),
            "selecciones": set(),
        }

        self.assertEqual(normalizar("Celta B"), "celta fortuna")
        self.assertEqual(
            resolver({"local": "Cadiz CF", "visitante": "Celta B"}, cats)["competicion"],
            "segunda_division",
        )


if __name__ == "__main__":
    unittest.main()
