import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import aplicar_objetivos_oficiales_json as aoj
import forzar_overrides as fov


CONTEXTO_INICIO_TEMPORADA = {
    "primera": {"equipos": [
        {"equipo": "RC Celta de Vigo", "partidos_restantes": 35},
        {"equipo": "Sevilla FC", "partidos_restantes": 35},
    ]},
    "segunda": {"equipos": [{"equipo": "Cordoba CF", "partidos_restantes": 39}]},
}

CONTEXTO_RECTA_FINAL = {
    "primera": {"equipos": [
        {"equipo": "RC Celta de Vigo", "partidos_restantes": 1},
    ]},
    "segunda": {"equipos": []},
}


class OverridesVigentesTests(unittest.TestCase):
    """Bug real (01/09/2026): objetivos_jornada_actual.json (overrides
    manuales del 29/06/2026 para la ULTIMA jornada de la 25/26) se siguio
    aplicando cada ciclo durante toda la pretemporada y el arranque de la
    26/27 -inyectando motivacion "maxima" y lecturas de Europa League
    obsoletas a 8 equipos, incluido un Malaga que cambio de division."""

    def test_archivo_sin_valido_hasta_se_ignora(self):
        vigente, motivo = aoj.overrides_vigentes({"equipos": {"X": {}}}, CONTEXTO_RECTA_FINAL)
        self.assertFalse(vigente)
        self.assertIn("valido_hasta", motivo)

    def test_archivo_caducado_se_ignora(self):
        datos = {"valido_hasta": "2026-05-25", "equipos": {"X": {}}}
        vigente, motivo = aoj.overrides_vigentes(datos, CONTEXTO_RECTA_FINAL)
        self.assertFalse(vigente)
        self.assertIn("caducado", motivo)

    def test_con_muchas_jornadas_por_delante_se_ignora_aunque_no_caduque(self):
        # Los overrides de "ultima jornada" no tienen sentido a 35 partidos
        # del final aunque alguien les ponga una caducidad generosa -mismo
        # principio que el gate de 10 jornadas del motor.
        datos = {"valido_hasta": "2099-12-31", "equipos": {"X": {}}}
        vigente, motivo = aoj.overrides_vigentes(datos, CONTEXTO_INICIO_TEMPORADA)
        self.assertFalse(vigente)
        self.assertIn(">10", motivo)

    def test_vigente_en_recta_final_con_caducidad_futura(self):
        datos = {"valido_hasta": "2099-12-31", "equipos": {"X": {}}}
        vigente, motivo = aoj.overrides_vigentes(datos, CONTEXTO_RECTA_FINAL)
        self.assertTrue(vigente, motivo)

    def test_forzar_overrides_aplica_la_misma_guardia(self):
        # forzar_overrides.py aplica EL MISMO archivo -sin la guardia
        # duplicada alli, arreglar solo un aplicador deja el bug vivo (la
        # misma leccion del 26/08: buscar TODOS los escritores).
        vigente, motivo = fov.overrides_vigentes({"equipos": {"X": {}}}, CONTEXTO_RECTA_FINAL)
        self.assertFalse(vigente)
        self.assertIn("valido_hasta", motivo)
        datos = {"valido_hasta": "2099-12-31", "equipos": {"X": {}}}
        vigente, _ = fov.overrides_vigentes(datos, CONTEXTO_INICIO_TEMPORADA)
        self.assertFalse(vigente)
        vigente, _ = fov.overrides_vigentes(datos, CONTEXTO_RECTA_FINAL)
        self.assertTrue(vigente)


if __name__ == "__main__":
    unittest.main()
