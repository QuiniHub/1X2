import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import auditar_fuentes_profesionales as afp


def _fuente_losilla_con_partidos(n):
    return {
        "probabilidades": {
            "jornada": 73,
            "partidos": [
                {"numero": i, "local": f"Local {i}", "visitante": f"Visitante {i}", "probabilidad_1": 40.0}
                for i in range(1, n + 1)
            ],
        }
    }


class AuditarFuentesProfesionalesTests(unittest.TestCase):
    def test_porcentajes_publicos_se_marca_conectado_con_datos_reales(self):
        fuentes = afp.aplicar_estado_conector(afp.copiar_fuentes(), {}, _fuente_losilla_con_partidos(14))
        self.assertEqual(fuentes["porcentajes_publicos_quiniela"]["estado"], "conectado_scraper")

    def test_porcentajes_publicos_sigue_pendiente_sin_datos(self):
        fuentes = afp.aplicar_estado_conector(afp.copiar_fuentes(), {}, {})
        self.assertEqual(fuentes["porcentajes_publicos_quiniela"]["estado"], "pendiente_fuente")

    def test_porcentajes_publicos_sigue_pendiente_con_muy_pocos_partidos(self):
        """Un puñado suelto de partidos (p.ej. de otra jornada o un scrape a
        medias) no debe contar como "conectado" -exige al menos 10, un
        boleto real casi completo."""
        fuentes = afp.aplicar_estado_conector(afp.copiar_fuentes(), {}, _fuente_losilla_con_partidos(2))
        self.assertEqual(fuentes["porcentajes_publicos_quiniela"]["estado"], "pendiente_fuente")

    def test_aplicar_estado_conector_sin_fuente_losilla_no_falla(self):
        """Llamada sin el tercer argumento (compatibilidad hacia atras)."""
        fuentes = afp.aplicar_estado_conector(afp.copiar_fuentes(), {})
        self.assertEqual(fuentes["porcentajes_publicos_quiniela"]["estado"], "pendiente_fuente")

    def test_cuotas_mercado_error_conexion_si_token_configurado_y_falla(self):
        """Reproduce el caso real: QUINIHUB_PRO_DATA_TOKEN configurado, pero
        la API responde 403 para todos los fixtures -distinto de
        "pendiente_secret" (nunca configurado)."""
        datos = {
            "estado_global": "sin_datos_profesionales",
            "resumen": {"cuotas": 0, "bajas_estructuradas": 0, "alineaciones_probables": 0},
            "configuracion": {"token_configurado": True, "url_configurada": True},
            "proveedores": {"api_football": {"errores": ["403 Client Error: Forbidden for url: ..."]}},
        }
        fuentes = afp.aplicar_estado_conector(afp.copiar_fuentes(), datos)
        self.assertEqual(fuentes["cuotas_mercado"]["estado"], "error_conexion")
        self.assertIn("403", fuentes["cuotas_mercado"]["siguiente_paso"])
        self.assertEqual(fuentes["lesiones_sanciones"]["estado"], "error_conexion")
        self.assertEqual(fuentes["alineaciones_probables"]["estado"], "error_conexion")

    def test_cuotas_mercado_pendiente_secret_si_nunca_se_configuro(self):
        datos = {"estado_global": "pendiente_secrets", "resumen": {}}
        fuentes = afp.aplicar_estado_conector(afp.copiar_fuentes(), datos)
        self.assertEqual(fuentes["cuotas_mercado"]["estado"], "pendiente_secret")

    def test_cuotas_mercado_conectado_si_hay_cuotas_reales(self):
        datos = {
            "estado_global": "operativo",
            "resumen": {"cuotas": 5},
            "configuracion": {"token_configurado": True},
            "proveedores": {"api_football": {"errores": []}},
        }
        fuentes = afp.aplicar_estado_conector(afp.copiar_fuentes(), datos)
        self.assertEqual(fuentes["cuotas_mercado"]["estado"], "conectado_api")

    def test_error_conexion_cuenta_como_critica_pendiente(self):
        """Una fuente critica en error_conexion (token roto) no debe
        desaparecer de criticas_pendientes solo porque su estado ya no
        empieza por "pendiente" -si no, el resumen global diria
        erroneamente que ya esta todo cubierto."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            original_out = afp.OUT
            original_datos = afp.DATOS_PROFESIONALES
            original_losilla = afp.FUENTE_LOSILLA
            try:
                afp.OUT = tmp / "fuentes_profesionales.json"
                afp.DATOS_PROFESIONALES = tmp / "datos_profesionales.json"
                afp.FUENTE_LOSILLA = tmp / "fuente_losilla.json"
                afp.DATOS_PROFESIONALES.write_text(json.dumps({
                    "estado_global": "sin_datos_profesionales",
                    "resumen": {"cuotas": 0, "bajas_estructuradas": 0, "alineaciones_probables": 0},
                    "configuracion": {"token_configurado": True, "url_configurada": True},
                    "proveedores": {"api_football": {"errores": ["403 Client Error: Forbidden for url: ..."]}},
                }, ensure_ascii=False), encoding="utf-8")
                afp.main()
                salida = json.loads(afp.OUT.read_text(encoding="utf-8"))
                self.assertIn("cuotas_mercado", salida["resumen"]["criticas_pendientes"])
                self.assertEqual(salida["estado_global"], "en_construccion")
            finally:
                afp.OUT = original_out
                afp.DATOS_PROFESIONALES = original_datos
                afp.FUENTE_LOSILLA = original_losilla

    def test_main_genera_salida_valida(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            original_out = afp.OUT
            original_datos = afp.DATOS_PROFESIONALES
            original_losilla = afp.FUENTE_LOSILLA
            try:
                afp.OUT = tmp / "fuentes_profesionales.json"
                afp.DATOS_PROFESIONALES = tmp / "datos_profesionales.json"
                afp.FUENTE_LOSILLA = tmp / "fuente_losilla.json"
                afp.FUENTE_LOSILLA.write_text(
                    json.dumps(_fuente_losilla_con_partidos(14), ensure_ascii=False), encoding="utf-8"
                )
                afp.main()
                salida = json.loads(afp.OUT.read_text(encoding="utf-8"))
                self.assertEqual(
                    salida["fuentes"]["porcentajes_publicos_quiniela"]["estado"], "conectado_scraper"
                )
            finally:
                afp.OUT = original_out
                afp.DATOS_PROFESIONALES = original_datos
                afp.FUENTE_LOSILLA = original_losilla


if __name__ == "__main__":
    unittest.main()
