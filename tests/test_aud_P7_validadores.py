"""Auditoria 26/11/2026, paquete P7: validadores.

Hallazgos 104 y 112 (validar_publicacion_autonoma), 50/85/116/122/139
(validar_contexto_actual) y 170 (forzar_overrides).
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import forzar_overrides as fov
import validar_contexto_actual as vca
import validar_publicacion_autonoma as vpa

INICIO = datetime(2026, 11, 28, 13, 0, tzinfo=timezone.utc)


def partido(num, signo="1", tipo=None, **extra):
    tipo = tipo or {1: "FIJO", 2: "DOBLE", 3: "TRIPLE"}[len(signo)]
    frase = {"FIJO": "Se mantiene como FIJO", "DOBLE": "Se cubre con DOBLE", "TRIPLE": "Se abre TRIPLE"}[tipo]
    datos = {
        "num": num, "local": f"Local {num}", "visitante": f"Visitante {num}",
        "tipo": tipo, "signo_final": signo, "signo_base": signo[0],
        "probabilidades": {"1": 45.0, "X": 30.0, "2": 25.0},
        "razonamiento": f"{frase}. Decision final: {signo}.",
        "calidad_datos": "alta",
    }
    datos.update(extra)
    return datos


def prediccion(**cambios):
    partidos = [partido(n) for n in range(1, 15)]
    partidos[4] = partido(5, "1X")
    partidos[9] = partido(10, "1X2")
    pred = {
        "jornada": 25,
        "partidos": partidos,
        "configuracion": {"dobles": 1, "triples": 1},
        "coste": {"apuestas": 6, "importe_quiniela": 4.5},
    }
    pred.update(cambios)
    return pred


class InvariantesBoletoTests(unittest.TestCase):
    def test_boleto_coherente_no_da_nada(self):
        self.assertEqual(vpa.invariantes_boleto(prediccion()), ([], []))

    def test_coste_que_no_cuadra_con_los_signos_es_critico(self):
        criticos, _ = vpa.invariantes_boleto(prediccion(coste={"apuestas": 18, "importe_quiniela": 13.5}))
        self.assertEqual(len(criticos), 1)
        self.assertTrue(vpa.es_error_critico(criticos[0]))

    def test_importe_que_no_cuadra_con_las_apuestas_es_critico(self):
        criticos, _ = vpa.invariantes_boleto(prediccion(coste={"apuestas": 6, "importe_quiniela": 13.5}))
        self.assertEqual(len(criticos), 1)
        self.assertTrue(vpa.es_error_critico(criticos[0]))

    def test_importe_minimo_de_un_boleto_sencillo(self):
        pred = prediccion(coste={"apuestas": 1, "importe_quiniela": 1.5})
        pred["partidos"] = [partido(n) for n in range(1, 15)]
        self.assertEqual(vpa.invariantes_boleto(pred), ([], []))

    def test_signo_invalido_o_repetido_es_critico(self):
        for malo in ("", "3", "11", "1x"[0] + "Y"):
            pred = prediccion()
            pred["partidos"][0]["signo_final"] = malo
            criticos, _ = vpa.invariantes_boleto(pred)
            self.assertTrue(any(vpa.es_error_critico(e) for e in criticos), malo)

    def test_fijo_con_dos_signos_es_critico(self):
        pred = prediccion(coste={"apuestas": 12, "importe_quiniela": 9.0})
        pred["partidos"][0]["signo_final"] = "1X"
        criticos, _ = vpa.invariantes_boleto(pred)
        self.assertTrue(any("es FIJO pero" in e and vpa.es_error_critico(e) for e in criticos))

    def test_numeracion_rota_es_critica(self):
        pred = prediccion()
        pred["partidos"][13]["num"] = 13
        criticos, _ = vpa.invariantes_boleto(pred)
        self.assertTrue(any("numerados" in e and vpa.es_error_critico(e) for e in criticos))

    def test_doble_de_autor_sin_la_x_se_avisa_pero_no_bloquea(self):
        pred = prediccion()
        pred["partidos"][4] = partido(5, "12", cobertura_autor={"activo": True, "cubierta": True})
        criticos, tolerados = vpa.invariantes_boleto(pred)
        self.assertEqual(criticos, [])
        self.assertEqual(len(tolerados), 1)
        self.assertFalse(vpa.es_error_critico(tolerados[0]))

    def test_x_de_autor_en_un_fijo_es_legitima(self):
        pred = prediccion()
        pred["partidos"][0] = partido(1, "X", signo_base="1", x_de_autor={"activo": True})
        self.assertEqual(vpa.invariantes_boleto(pred), ([], []))
        pred["partidos"][0]["x_de_autor"] = {"activo": False}
        _, tolerados = vpa.invariantes_boleto(pred)
        self.assertEqual(len(tolerados), 1)

    def test_validar_prediccion_propaga_el_coste_incoherente_como_critico(self):
        errores, _, _ = vpa.validar_prediccion(prediccion(jornada=4, coste={"apuestas": 99, "importe_quiniela": 1}))
        self.assertTrue(any(vpa.es_error_critico(e) and "coste.apuestas" in e for e in errores))

    def test_validar_prediccion_ya_no_impone_otro_reparto(self):
        # El motor puede dejar el triple donde quiera: el validador no lo discute.
        pred = prediccion(jornada=4)
        for p in pred["partidos"]:
            p["cobertura_sorpresa_sugerida"] = "FIJO"
        pred["partidos"][0]["cobertura_sorpresa_sugerida"] = "TRIPLE"
        pred["partidos"][0]["indice_sorpresa_quinielistica"] = 100
        errores, avisos, _ = vpa.validar_prediccion(pred)
        self.assertFalse([e for e in errores + avisos if "mayor prioridad" in e or "mayor riesgo" in e])


class CongelacionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.jornadas = Path(self._tmp.name) / "jornadas"
        self.snapshots = Path(self._tmp.name) / "pre_cierre"
        self.jornadas.mkdir()
        self.snapshots.mkdir()
        self.pred = prediccion()
        self.escribir_jornada()
        self.escribir_snapshot()

    def escribir_jornada(self, cerrada=False, fecha="2026-11-28"):
        partidos = [{"num": p["num"], "local": p["local"], "visitante": p["visitante"], "fecha": fecha,
                     "signo_oficial": "1" if cerrada else ""} for p in self.pred["partidos"]]
        (self.jornadas / "jornada_25.json").write_text(
            json.dumps({"jornada": 25, "partidos": partidos}), encoding="utf-8")

    def escribir_snapshot(self, texto=None):
        snap = {"jornada": 25, "primer_partido_utc": INICIO.isoformat(), "prediccion": self.pred}
        (self.snapshots / "jornada_25.json").write_text(
            texto if texto is not None else json.dumps(snap), encoding="utf-8")

    def estado(self, pred=None, ahora=None):
        return vpa.estado_congelacion(pred or self.pred, ahora or INICIO + timedelta(hours=1),
                                      self.snapshots, self.jornadas)

    def test_antes_del_primer_partido_no_se_exige_nada(self):
        estado = self.estado(ahora=INICIO - timedelta(hours=1))
        self.assertFalse(estado["en_juego"])
        self.assertNotIn("error", estado)

    def test_en_juego_y_sin_congelar_es_error_critico(self):
        estado = self.estado()
        self.assertTrue(estado["en_juego"])
        self.assertTrue(vpa.es_error_critico(estado["error"]))

    def test_en_juego_y_congelada_esta_bien(self):
        pred = dict(self.pred, prediccion_congelada_al_cierre={"activa": True})
        estado = self.estado(pred)
        self.assertTrue(estado["en_juego"])
        self.assertTrue(estado["congelada"])
        self.assertNotIn("error", estado)

    def test_snapshot_ilegible_con_la_jornada_en_juego_es_critico(self):
        self.escribir_snapshot("{esto no es json")
        estado = self.estado()
        self.assertTrue(estado["en_juego"])
        self.assertTrue(vpa.es_error_critico(estado["error"]))

    def test_snapshot_ilegible_antes_de_la_jornada_solo_avisa(self):
        self.escribir_snapshot("{esto no es json")
        estado = self.estado(ahora=INICIO - timedelta(days=2))
        self.assertFalse(estado["en_juego"])
        self.assertNotIn("error", estado)
        self.assertIn("aviso", estado)

    def test_jornada_cerrada_ya_no_esta_en_juego(self):
        self.escribir_jornada(cerrada=True)
        self.assertFalse(self.estado()["en_juego"])

    def test_sin_snapshot_no_hay_nada_que_congelar(self):
        (self.snapshots / "jornada_25.json").unlink()
        estado = self.estado()
        self.assertFalse(estado["en_juego"])
        self.assertNotIn("error", estado)

    def test_snapshot_de_otra_temporada_con_el_mismo_numero_no_cuenta(self):
        # Mismo numero, otros equipos y otra fecha: no es esta jornada.
        vieja = prediccion()
        for p in vieja["partidos"]:
            p["local"], p["visitante"] = f"Otro {p['num']}", f"Rival {p['num']}"
        snap = {"jornada": 25, "primer_partido_utc": "2025-11-29T13:00:00+00:00", "prediccion": vieja}
        self.escribir_snapshot(json.dumps(snap))
        estado = self.estado()
        self.assertFalse(estado["en_juego"])
        self.assertNotIn("error", estado)

    def test_jornada_que_no_cierra_deja_de_bloquear_pasado_el_limite(self):
        dentro = self.estado(ahora=INICIO + timedelta(days=vpa.DIAS_MAX_JORNADA_EN_JUEGO, hours=-1))
        self.assertIn("error", dentro)
        fuera = self.estado(ahora=INICIO + timedelta(days=vpa.DIAS_MAX_JORNADA_EN_JUEGO + 1))
        self.assertFalse(fuera["en_juego"])
        self.assertNotIn("error", fuera)
        self.assertIn("aviso", fuera)

    def test_misma_identidad_de_jornada_que_congelar(self):
        # data/jornadas con nombres de otra fuente Y otra fecha: con el
        # criterio anterior (snapshot contra data/jornadas) el validador
        # decia "no es esta jornada" mientras congelar_bloques_sombra, que
        # compara con la prediccion, decia que si. Ahora deciden lo mismo.
        import congelar_bloques_sombra as cbs
        from guardar_snapshot_prediccion import snapshot_de_otra_jornada
        partidos = [{"num": p["num"], "local": f"Fuente B {p['num']}", "visitante": f"Rival B {p['num']}",
                     "fecha": "2026-12-05", "signo_oficial": ""} for p in self.pred["partidos"]]
        (self.jornadas / "jornada_25.json").write_text(
            json.dumps({"jornada": 25, "partidos": partidos}), encoding="utf-8")
        snap = json.loads((self.snapshots / "jornada_25.json").read_text(encoding="utf-8"))
        self.assertFalse(snapshot_de_otra_jornada(snap, self.pred))
        self.assertTrue(self.estado()["en_juego"])
        # Y congelar, sobre esos mismos ficheros, SI marca la prediccion: el
        # validador la acepta y no hay bloqueo permanente.
        preds = Path(self._tmp.name) / "predicciones"
        preds.mkdir()
        for nombre in ("jornada_25.json", "ultima_prediccion.json"):
            (preds / nombre).write_text(json.dumps(self.pred), encoding="utf-8")
        cbs.congelar(25, INICIO + timedelta(hours=1), preds, self.snapshots, preds / "ultima_prediccion.json")
        congelada = json.loads((preds / "ultima_prediccion.json").read_text(encoding="utf-8"))
        estado = self.estado(congelada)
        self.assertTrue(estado["congelada"])
        self.assertNotIn("error", estado)

    def test_validar_prediccion_bloquea_la_jornada_en_juego_sin_congelar(self):
        with mock.patch.object(vpa, "SNAPSHOTS", self.snapshots), mock.patch.object(vpa, "JORNADAS", self.jornadas), \
                mock.patch.object(vpa, "datetime") as reloj:
            reloj.now.return_value = INICIO + timedelta(hours=1)
            reloj.fromisoformat.side_effect = datetime.fromisoformat
            errores, _, _ = vpa.validar_prediccion(json.loads(json.dumps(self.pred)))
        self.assertTrue(any(vpa.es_error_critico(e) and "congelada" in e for e in errores), errores)


class EspejoYFallosCronicosTests(unittest.TestCase):
    def test_diferencias_espejo(self):
        with tempfile.TemporaryDirectory() as tmp:
            pred = prediccion()
            self.assertEqual(vpa.diferencias_espejo(pred, tmp), ["(no existe el espejo)"])
            ruta = Path(tmp) / "jornada_25.json"
            ruta.write_text(json.dumps(pred), encoding="utf-8")
            self.assertEqual(vpa.diferencias_espejo(pred, tmp), [])
            ruta.write_text(json.dumps(dict(pred, coste={"apuestas": 1})), encoding="utf-8")
            self.assertEqual(vpa.diferencias_espejo(pred, tmp), ["coste"])

    def test_fallos_cronicos_solo_desde_el_umbral(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "fallos.json"
            self.assertEqual(vpa.fallos_cronicos(ruta), [])
            ruta.write_text(json.dumps({
                "a.py": {"fallos_consecutivos": 2},
                "b.py": {"fallos_consecutivos": 555, "ultimo_fallo": "2026-11-27T11:20:05+00:00"},
            }), encoding="utf-8")
            cronicos = vpa.fallos_cronicos(ruta)
            self.assertEqual([c["script"] for c in cronicos], ["b.py"])
            self.assertEqual(cronicos[0]["fallos_consecutivos"], 555)


def contexto(restantes=3, **equipo_extra):
    equipo = {
        "equipo": "Sevilla FC", "posicion": 12, "partidos_restantes": restantes,
        "objetivos": [{"objetivo": "permanencia", "estado": "riesgo_descenso", "vivo": True}],
        "objetivo_principal": {"objetivo": "permanencia", "estado": "riesgo_descenso", "vivo": True},
        "motivacion_competitiva": "maxima",
    }
    equipo.update(equipo_extra)
    return {"primera": {"equipos": [equipo]}, "segunda": {"equipos": []}}


OVERRIDES_2526 = {
    "equipos": {"Sevilla FC": {"estado": "salvado_matematicamente", "motivacion_competitiva": "baja"}},
}


class ValidarContextoTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ovr = Path(self._tmp.name) / "objetivos_jornada_actual.json"
        parche = mock.patch.object(vca, "OVR", self.ovr)
        parche.start()
        self.addCleanup(parche.stop)

    def escribir(self, datos):
        self.ovr.write_text(json.dumps(datos), encoding="utf-8")

    def test_overrides_sin_caducidad_no_se_exigen(self):
        # El fichero real: overrides de la ultima jornada 25/26, sin valido_hasta.
        self.escribir(OVERRIDES_2526)
        overrides, motivo = vca.overrides_a_validar(contexto())
        self.assertEqual(overrides, {})
        self.assertIn("valido_hasta", motivo)

    def test_overrides_caducados_no_se_exigen(self):
        self.escribir(dict(OVERRIDES_2526, valido_hasta="2026-06-01"))
        overrides, motivo = vca.overrides_a_validar(contexto())
        self.assertEqual(overrides, {})
        self.assertIn("caducado", motivo)

    def test_overrides_lejos_del_final_no_se_exigen(self):
        self.escribir(dict(OVERRIDES_2526, valido_hasta="2999-01-01"))
        self.assertEqual(vca.overrides_a_validar(contexto(restantes=25))[0], {})

    def test_overrides_vigentes_si_se_exigen(self):
        self.escribir(dict(OVERRIDES_2526, valido_hasta="2999-01-01"))
        overrides, _ = vca.overrides_a_validar(contexto(restantes=1))
        self.assertIn("Sevilla FC", overrides)
        with self.assertRaises(SystemExit):
            vca.validar_overrides(contexto(restantes=1), overrides)

    def test_sin_fichero_de_overrides(self):
        self.assertEqual(vca.overrides_a_validar(contexto())[0], {})

    def test_el_fichero_real_ya_no_hace_fallar_al_validador(self):
        real = ROOT / "data" / "memoria_ia" / "objetivos_jornada_actual.json"
        ctx_real = ROOT / "data" / "memoria_ia" / "contexto_competitivo.json"
        if not real.exists() or not ctx_real.exists():
            self.skipTest("sin datos reales")
        datos = json.loads(real.read_text(encoding="utf-8"))
        if datos.get("valido_hasta"):
            self.skipTest("hay overrides con caducidad: los valida validar_overrides")
        with mock.patch.object(vca, "OVR", real):
            overrides, _ = vca.overrides_a_validar(json.loads(ctx_real.read_text(encoding="utf-8")))
        self.assertEqual(overrides, {})

    def test_main_no_falla_por_overrides_caducados(self):
        self.escribir(OVERRIDES_2526)
        salida = io.StringIO()
        with mock.patch.object(vca, "cargar", side_effect=lambda p: OVERRIDES_2526 if p == self.ovr else contexto()), \
                mock.patch.object(vca, "validar_fechas"), contextlib.redirect_stdout(salida):
            vca.main()
        self.assertIn("no vigentes", salida.getvalue())
        self.assertIn("sin contradicciones", salida.getvalue())

    def test_lider_con_objetivo_principal_de_zona_baja_es_contradiccion(self):
        malo = contexto(posicion=1, equipo="FC Barcelona",
                        objetivo_principal={"objetivo": "descenso", "estado": "permanencia_por_cerrar", "vivo": True})
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            fallos = vca.validar_coherencia_tabla(malo)
        # Aviso visible, nunca SystemExit: no debe volver a ser fallo cronico.
        self.assertEqual(len(fallos), 1)
        self.assertIn("FC Barcelona", fallos[0])
        self.assertIn("::warning", salida.getvalue())

    def test_main_no_falla_por_un_lider_incoherente(self):
        malo = contexto(posicion=1, equipo="FC Barcelona",
                        objetivo_principal={"objetivo": "descenso", "vivo": True})
        salida = io.StringIO()
        with mock.patch.object(vca, "cargar", return_value=malo), \
                mock.patch.object(vca, "overrides_a_validar", return_value=({}, "prueba")), \
                mock.patch.object(vca, "validar_fechas"), contextlib.redirect_stdout(salida):
            vca.main()
        self.assertIn("no bloquean", salida.getvalue())

    def test_lider_con_objetivo_de_titulo_es_coherente(self):
        bueno = contexto(posicion=1, objetivo_principal={"objetivo": "titulo_liga", "vivo": True})
        self.assertEqual(vca.validar_coherencia_tabla(bueno), [])
        self.assertEqual(vca.validar_coherencia_tabla(contexto(posicion=18)), [])
        self.assertEqual(vca.validar_coherencia_tabla(contexto(posicion=0)), [])


class ForzarOverridesTests(unittest.TestCase):
    def test_sin_ficheros_no_revienta_ni_escribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = Path(tmp) / "contexto_competitivo.json"
            ovr = Path(tmp) / "objetivos_jornada_actual.json"
            with mock.patch.object(fov, "CTX", ctx), mock.patch.object(fov, "OVR", ovr), \
                    contextlib.redirect_stdout(io.StringIO()):
                fov.main()
                ctx.write_text(json.dumps(contexto()), encoding="utf-8")
                fov.main()
            self.assertFalse(ovr.exists())
            self.assertEqual(json.loads(ctx.read_text(encoding="utf-8")), contexto())


if __name__ == "__main__":
    unittest.main()
