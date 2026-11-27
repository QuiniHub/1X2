"""Auditoria 26/11/2026, paquete P7: actualizar_todo.py, compuerta y workflows.

Hallazgos 104, 112, 117, 118, 138, 166, 167, 169, 170, 217, 222.
"""
import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_todo as at
import compuerta_jornada

WORKFLOWS = ROOT / ".github" / "workflows"


class _Aislado(unittest.TestCase):
    """Nunca se escribe en el data/ real ni se lanza un subproceso de verdad."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        parche = mock.patch.object(at, "HISTORIAL_FALLOS", self.tmp / "fallos.json")
        parche.start()
        self.addCleanup(parche.stop)

    def silencio(self):
        return contextlib.redirect_stdout(io.StringIO())


class CriticidadTests(_Aislado):
    def test_el_conjunto_no_critico_es_exactamente_lo_que_no_es_critico(self):
        activos = set(at.SCRIPTS_ACTIVOS)
        self.assertEqual(set(at.SCRIPTS_NO_CRITICOS_RED), activos - at.SCRIPTS_CRITICOS_PREDICCION)
        self.assertFalse(set(at.SCRIPTS_NO_CRITICOS_RED) & at.SCRIPTS_CRITICOS_PREDICCION)
        for nombre in at.SCRIPTS_ACTIVOS:
            self.assertEqual(at.es_critico(nombre), nombre not in at.SCRIPTS_NO_CRITICOS_RED)

    def test_todos_los_scripts_activos_existen(self):
        faltan = [s for s in at.SCRIPTS_ACTIVOS if not (ROOT / s).exists()]
        self.assertEqual(faltan, [])

    def test_fallo_de_un_no_critico_no_detiene_y_queda_registrado(self):
        error = subprocess.CalledProcessError(1, "x")
        with mock.patch.object(at.subprocess, "run", side_effect=error), self.silencio():
            self.assertFalse(at.ejecutar_script("calcular_premios.py"))
        self.assertEqual(at.cargar_historial_fallos()["calcular_premios.py"]["fallos_consecutivos"], 1)

    def test_fallo_de_un_critico_detiene_el_ciclo(self):
        error = subprocess.CalledProcessError(1, "x")
        for nombre in sorted(at.SCRIPTS_CRITICOS_PREDICCION):
            with mock.patch.object(at.subprocess, "run", side_effect=error), self.silencio():
                with self.assertRaises(at.ErrorCriticoPrediccion):
                    at.ejecutar_script(nombre)

    def test_script_critico_que_falta_detiene_el_ciclo(self):
        with mock.patch.object(at, "ROOT", self.tmp), self.silencio():
            with self.assertRaises(at.ErrorCriticoPrediccion):
                at.ejecutar_script("motor_prediccion_objetivo.py")
            self.assertFalse(at.ejecutar_script("calcular_premios.py"))


class TimeoutTests(_Aislado):
    def test_cada_subproceso_lleva_timeout(self):
        with mock.patch.object(at.subprocess, "run") as run, self.silencio():
            self.assertTrue(at.ejecutar_script("calcular_premios.py"))
        self.assertEqual(run.call_args.kwargs.get("timeout"), at.timeout_script_seg())
        self.assertGreater(at.timeout_script_seg(), 0)

    def test_timeout_configurable_por_entorno(self):
        with mock.patch.dict(at.os.environ, {"ACTUALIZAR_TODO_TIMEOUT_SEG": "120"}):
            self.assertEqual(at.timeout_script_seg(), 120)
        with mock.patch.dict(at.os.environ, {"ACTUALIZAR_TODO_TIMEOUT_SEG": "basura"}):
            self.assertEqual(at.timeout_script_seg(), at.TIMEOUT_SCRIPT_SEG_DEFECTO)

    def test_un_script_colgado_no_critico_se_corta_y_se_sigue(self):
        colgado = subprocess.TimeoutExpired("x", 900)
        with mock.patch.object(at.subprocess, "run", side_effect=colgado), self.silencio():
            self.assertFalse(at.ejecutar_script("actualizar_fuente_losilla.py"))
        self.assertIn("actualizar_fuente_losilla.py", at.cargar_historial_fallos())

    def test_el_motor_colgado_detiene_el_ciclo(self):
        colgado = subprocess.TimeoutExpired("x", 900)
        with mock.patch.object(at.subprocess, "run", side_effect=colgado), self.silencio():
            with self.assertRaises(at.ErrorCriticoPrediccion):
                at.ejecutar_script("motor_prediccion_objetivo.py")


class CongelarTests(_Aislado):
    def test_congelar_falla_con_la_jornada_en_juego_no_se_publica(self):
        error = subprocess.CalledProcessError(1, "x")
        with mock.patch.object(at.subprocess, "run", side_effect=error), \
                mock.patch.object(at, "jornada_en_juego", return_value=True), self.silencio():
            with self.assertRaises(at.ErrorCriticoPrediccion):
                at.ejecutar_script(at.SCRIPT_CONGELAR)

    def test_congelar_falla_sin_jornada_en_juego_solo_avisa(self):
        error = subprocess.CalledProcessError(1, "x")
        with mock.patch.object(at.subprocess, "run", side_effect=error), \
                mock.patch.object(at, "jornada_en_juego", return_value=False), self.silencio():
            self.assertFalse(at.ejecutar_script(at.SCRIPT_CONGELAR))

    def test_si_no_se_puede_saber_se_asume_en_juego(self):
        import validar_publicacion_autonoma as vpa
        with mock.patch.object(vpa, "estado_congelacion", side_effect=RuntimeError("x")), self.silencio():
            self.assertTrue(at.jornada_en_juego())

    def test_se_congela_antes_de_los_derivados_y_otra_vez_al_final(self):
        activos = at.SCRIPTS_ACTIVOS
        posiciones = [i for i, s in enumerate(activos) if s == at.SCRIPT_CONGELAR]
        self.assertEqual(len(posiciones), 2)
        temprana, final = posiciones
        self.assertEqual(activos[temprana - 1], "alinear_boleto_con_analisis.py")
        for derivado in ("generar_estado_vivo_ia.py", "ajustar_estado_vivo_motivacion.py",
                         "calcular_premios.py", "diagnostico_sistema.py",
                         "control_calidad_actualizacion.py", "construir_memoria_historica_profunda.py"):
            self.assertGreater(activos.index(derivado), temprana, derivado)
        # La final va detras del snapshot y de todos los que reescriben bloques.
        for previo in ("guardar_snapshot_prediccion.py", "calibrar_probabilidades.py",
                       "aplicar_elige8_seguro.py", "seleccionar_pleno15.py", "columna_valiente.py"):
            self.assertGreater(final, activos.index(previo), previo)
        self.assertEqual(activos[final + 1], "validar_publicacion_autonoma.py")
        self.assertEqual(activos[-1], "validar_publicacion_autonoma.py")


def escribir_j1(raiz, fecha, resultado="3-0"):
    carpeta = raiz / "data" / "jornadas"
    carpeta.mkdir(parents=True, exist_ok=True)
    partidos = [{"num": n, "local": f"L{n}", "visitante": f"V{n}", "fecha": fecha, "resultado": resultado}
                for n in range(1, 15)]
    (carpeta / "jornada_1.json").write_text(json.dumps({"jornada": 1, "partidos": partidos}), encoding="utf-8")


class TemporadaPorFechaTests(_Aislado):
    def setUp(self):
        super().setUp()
        parche = mock.patch.object(at, "ROOT", self.tmp)
        parche.start()
        self.addCleanup(parche.stop)

    def test_la_j1_de_la_temporada_pasada_no_cuenta_como_iniciada(self):
        # Julio de 2027: jornada_1.json conserva los resultados de agosto de 2026.
        escribir_j1(self.tmp, "2026-08-15")
        self.assertFalse(at.temporada_ya_iniciada(date(2027, 7, 20)))
        self.assertFalse(at.temporada_ya_iniciada(date(2027, 8, 5)))

    def test_la_j1_de_esta_temporada_si_cuenta(self):
        escribir_j1(self.tmp, "2026-08-15")
        self.assertTrue(at.temporada_ya_iniciada(date(2026, 8, 16)))
        self.assertTrue(at.temporada_ya_iniciada(date(2026, 11, 27)))
        self.assertTrue(at.temporada_ya_iniciada(date(2027, 3, 1)))

    def test_j1_nueva_sin_resultados_sigue_siendo_pretemporada(self):
        escribir_j1(self.tmp, "2027-08-14", resultado="Pendiente")
        self.assertFalse(at.temporada_ya_iniciada(date(2027, 8, 10)))

    def test_etiqueta_de_temporada_correcta_todo_el_anio(self):
        self.assertEqual(at.etiqueta_temporada(date(2026, 11, 27)), "2026/2027")
        self.assertEqual(at.etiqueta_temporada(date(2027, 3, 1)), "2026/2027")
        self.assertEqual(at.etiqueta_temporada(date(2027, 7, 1)), "2027/2028")

    def test_pretemporada_2027_no_ejecuta_el_script_de_la_26_27(self):
        escribir_j1(self.tmp, "2026-08-15")
        (self.tmp / "preparar_temporada_2026_2027.py").write_text("raise SystemExit(9)", encoding="utf-8")
        salida = io.StringIO()
        with mock.patch.object(at.subprocess, "run") as run, contextlib.redirect_stdout(salida):
            self.assertFalse(at.gestionar_mercado_y_temporada(date(2027, 7, 20)))
        run.assert_not_called()
        self.assertIn("preparar_temporada_2027_2028.py", salida.getvalue())
        self.assertIn("preparar_temporada_2027_2028.py", at.cargar_historial_fallos())

    def test_pretemporada_ejecuta_el_script_de_su_temporada(self):
        (self.tmp / "preparar_temporada_2027_2028.py").write_text("", encoding="utf-8")
        with mock.patch.object(at.subprocess, "run") as run, self.silencio():
            self.assertTrue(at.gestionar_mercado_y_temporada(date(2027, 7, 20)))
        self.assertTrue(str(run.call_args.args[0][1]).endswith("preparar_temporada_2027_2028.py"))

    def test_con_la_temporada_en_marcha_no_se_prepara_nada(self):
        escribir_j1(self.tmp, "2026-08-15")
        with mock.patch.object(at.subprocess, "run") as run, self.silencio():
            at.gestionar_mercado_y_temporada(date(2026, 8, 20))
            at.gestionar_mercado_y_temporada(date(2026, 11, 27))
        run.assert_not_called()


class CadenaTests(unittest.TestCase):
    def test_los_overrides_los_aplica_un_solo_script(self):
        self.assertNotIn("aplicar_objetivos_oficiales_json.py", at.SCRIPTS_ACTIVOS)
        activos = at.SCRIPTS_ACTIVOS
        self.assertLess(activos.index("generar_contexto_competitivo.py"), activos.index("forzar_overrides.py"))
        self.assertLess(activos.index("forzar_overrides.py"), activos.index("validar_contexto_actual.py"))

    def test_la_compuerta_se_ejecuta_de_verdad_como_paso(self):
        self.assertTrue(callable(getattr(compuerta_jornada, "main", None)))
        texto = (ROOT / "compuerta_jornada.py").read_text(encoding="utf-8")
        self.assertIn('if __name__ == "__main__":', texto)

    def test_la_compuerta_como_paso_informa_y_no_escribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "estado_jornada_objetivo.json").write_text(json.dumps({"jornada_objetivo": 1}), encoding="utf-8")
            antes = sorted(p.name for p in data.iterdir())
            salida = io.StringIO()
            with mock.patch.object(compuerta_jornada, "DATA", data), contextlib.redirect_stdout(salida):
                compuerta_jornada.main()
            self.assertIn("Compuerta de jornada 1", salida.getvalue())
            self.assertEqual(sorted(p.name for p in data.iterdir()), antes)


class WorkflowTests(unittest.TestCase):
    def leer(self, nombre):
        return (WORKFLOWS / nombre).read_text(encoding="utf-8").replace("\r\n", "\n")

    def test_todos_los_jobs_tienen_limite_de_tiempo(self):
        for nombre in ("main.yml", "ci-pr.yml", "importar-memoria-quinielas.yml"):
            texto = self.leer(nombre)
            self.assertEqual(len(re.findall(r"^    runs-on:", texto, re.M)),
                             len(re.findall(r"^    timeout-minutes: \d+", texto, re.M)), nombre)

    def test_el_boleto_se_comprueba_despues_del_pipeline_y_antes_del_commit(self):
        texto = self.leer("main.yml")
        pipeline = texto.index("python actualizar_todo.py")
        comprobar = texto.index("tests.test_aud_P7_boleto_publicado")
        guardar = texto.index("- name: Guardar cambios")
        self.assertLess(pipeline, comprobar)
        self.assertLess(comprobar, guardar)
        self.assertIn('QUINIELA_POST_PIPELINE: "1"', texto[pipeline:guardar])
        self.assertIn("tests.test_calidad_prediccion", texto[pipeline:guardar])
        self.assertTrue((ROOT / "tests" / "test_aud_P7_boleto_publicado.py").exists())


if __name__ == "__main__":
    unittest.main()
