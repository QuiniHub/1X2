"""Auditoria 26/11/2026, paquete P7 (hallazgo 104).

Comprobacion del boleto RECIEN GENERADO: main.yml la ejecuta despues de
actualizar_todo.py y antes del commit, con QUINIELA_POST_PIPELINE=1.

BLOQUEAN el commit: boleto con incoherencias criticas y jornada en juego sin
congelar. Solo AVISAN (::warning::): boleto que no es el del motor y espejo
jornada_N.json distinto de ultima_prediccion.json (hallazgo 111, sin arreglar
en sus scripts).

Fuera de ese paso se salta a proposito: en "Ejecutar pruebas" (antes del
pipeline) los datos son los del ciclo anterior y un fallo ahi no arregla
nada, solo impide que el pipeline los regenere.
"""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import validar_publicacion_autonoma as vpa

PREDICCIONES = ROOT / "data" / "predicciones"


def avisar(titulo, problemas):
    """Anotacion ::warning:: en Actions, sin fallo.

    Si este paso falla NO se hace commit de nada del ciclo (resultados,
    clasificaciones, premios). Por eso solo bloquean los dos tests de
    incoherencias criticas (boleto injugable, jornada en juego sin congelar);
    lo que validar_publicacion_autonoma clasifica como aviso sigue siendo
    aviso aqui: mismo criterio en los dos sitios."""
    for problema in problemas:
        print(f"::warning title={titulo}::{problema}")


@unittest.skipUnless(
    os.environ.get("QUINIELA_POST_PIPELINE") == "1",
    "solo se ejecuta despues del pipeline (QUINIELA_POST_PIPELINE=1)",
)
class BoletoPublicadoTests(unittest.TestCase):
    def setUp(self):
        ruta = PREDICCIONES / "ultima_prediccion.json"
        if not ruta.exists():
            self.skipTest("no hay ultima_prediccion.json")
        self.pred = json.loads(ruta.read_text(encoding="utf-8"))
        normalizada = vpa.normalizar_estado_publicacion(dict(self.pred))
        if normalizada.get("prediccion_disponible") is False or not normalizada.get("publicar_prediccion", True):
            self.skipTest("prediccion retenida por la compuerta: no hay boleto que validar")
        marca = self.pred.get("prediccion_congelada_al_cierre") or {}
        self.congelada = bool(isinstance(marca, dict) and marca.get("activa"))

    def test_el_boleto_no_tiene_incoherencias_criticas(self):
        criticos, _ = vpa.invariantes_boleto(self.pred)
        self.assertEqual(criticos, [])

    def test_el_boleto_es_el_del_motor(self):
        # Una prediccion congelada es la foto del cierre tal cual (puede ser
        # anterior al arreglo): no se le exige nada mas que ser jugable.
        if self.congelada:
            self.skipTest("prediccion congelada al cierre")
        _, tolerados = vpa.invariantes_boleto(self.pred)
        avisar("Boleto distinto del del motor", tolerados)

    def test_la_jornada_en_juego_esta_congelada(self):
        estado = vpa.estado_congelacion(self.pred)
        self.assertIsNone(estado.get("error"), estado)

    def test_el_espejo_de_la_jornada_tiene_el_mismo_boleto(self):
        espejo_ruta = PREDICCIONES / f"jornada_{self.pred.get('jornada')}.json"
        if not espejo_ruta.exists():
            avisar("Espejo de la jornada", [f"no existe {espejo_ruta.name}"])
            return
        try:
            espejo = json.loads(espejo_ruta.read_text(encoding="utf-8"))
        except ValueError:
            avisar("Espejo de la jornada", [f"{espejo_ruta.name} es ilegible"])
            return

        def boleto(datos):
            return [(p.get("num"), p.get("tipo"), p.get("signo_final"), bool(p.get("elige8")))
                    for p in datos.get("partidos") or []]

        problemas = []
        if boleto(espejo) != boleto(self.pred):
            problemas.append(f"{espejo_ruta.name} y ultima_prediccion.json no llevan el mismo boleto")
        if espejo.get("coste") != self.pred.get("coste"):
            problemas.append(f"{espejo_ruta.name} y ultima_prediccion.json no llevan el mismo coste")
        avisar("Espejo de la jornada", problemas)


if __name__ == "__main__":
    unittest.main()
