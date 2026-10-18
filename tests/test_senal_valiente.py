import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import senal_valiente as sv
from motor_prediccion_quiniela import clave_par_equipos_h2h


def _partido(num=1, local="Cadiz CF", visitante="Levante UD",
             probs=None, fecha="2026-10-17", **extra):
    return {
        "num": num,
        "local": local,
        "visitante": visitante,
        "fecha": fecha,
        "probabilidades": probs or {"1": 45.0, "X": 30.0, "2": 25.0},
        **extra,
    }


def _fuentes(**cambios):
    base = {"ceses": [], "estudio_x": {}, "h2h": {}, "sorpresas_equipo": {}, "contador": None}
    base.update(cambios)
    return base


def _estudio_empatador(equipo="cadiz", x_pct=36.0, x_casa=30.0, x_fuera=30.0):
    return {
        "equipos_empatadores": [{
            "equipo": equipo, "pj": 100, "x_pct": x_pct,
            "x_casa_pct": x_casa, "x_fuera_pct": x_fuera,
        }],
        "fiabilidad_nuestra_por_equipo": [],
    }


class SenalRevulsivoTests(unittest.TestCase):
    def test_traza_del_motor_visitante_activa_el_signo_2(self):
        partido = _partido(ajuste_revulsivo={
            "activo": True, "lado": "visitante", "etapa": "debut", "tecnico": "Aguirre",
        })
        senal = sv.senal_revulsivo(partido, "2")
        self.assertIsNotNone(senal)
        self.assertEqual(senal["tipo"], "revulsivo_fuera")

    def test_traza_en_casa_no_es_senal(self):
        partido = _partido(ajuste_revulsivo={"activo": True, "lado": "local", "etapa": "debut"})
        self.assertIsNone(sv.senal_revulsivo(partido, "2"))
        self.assertIsNone(sv.senal_revulsivo(partido, "1"))

    def test_reconstruccion_con_ceses_debut_fuera(self):
        ceses = [{"equipo": "Levante UD", "fecha_cese": "2026-10-01", "nuevo": "Tecnico X"}]
        senal = sv.senal_revulsivo(_partido(), "2", ceses=ceses, contador=lambda *a: 0)
        self.assertIsNotNone(senal)
        self.assertIn("debut", senal["texto"])

    def test_reconstruccion_efecto_agotado_no_es_senal(self):
        ceses = [{"equipo": "Levante UD", "fecha_cese": "2026-10-01", "nuevo": "Tecnico X"}]
        self.assertIsNone(sv.senal_revulsivo(_partido(), "2", ceses=ceses, contador=lambda *a: 2))

    def test_cese_del_local_no_activa_el_2(self):
        ceses = [{"equipo": "Cadiz CF", "fecha_cese": "2026-10-01", "nuevo": "Tecnico X"}]
        self.assertIsNone(sv.senal_revulsivo(_partido(), "2", ceses=ceses, contador=lambda *a: 0))


class SenalEmpatadorTests(unittest.TestCase):
    def test_empatador_historico_solo_en_x(self):
        estudio = _estudio_empatador(x_pct=36.0)
        self.assertIsNotNone(sv.senal_empatador(_partido(), "X", estudio))
        self.assertIsNone(sv.senal_empatador(_partido(), "1", estudio))

    def test_empatador_por_rol_casa(self):
        estudio = _estudio_empatador(x_pct=25.0, x_casa=45.0)
        senal = sv.senal_empatador(_partido(), "X", estudio)
        self.assertIsNotNone(senal)
        self.assertIn("en casa", senal["texto"])

    def test_por_debajo_de_umbrales_no_es_senal(self):
        estudio = _estudio_empatador(x_pct=25.0, x_casa=30.0, x_fuera=30.0)
        self.assertIsNone(sv.senal_empatador(_partido(), "X", estudio))

    def test_nemesis(self):
        estudio = {
            "equipos_empatadores": [],
            "fiabilidad_nuestra_por_equipo": [{
                "equipo": "cadiz", "apariciones": 7, "acierto_pct": 28.6, "fallos_por_x": 3,
            }],
        }
        senal = sv.senal_empatador(_partido(), "X", estudio)
        self.assertIsNotNone(senal)
        self.assertEqual(senal["tipo"], "nemesis")


class SenalH2hTests(unittest.TestCase):
    def _historial(self, tasa=60.0, casos=3):
        clave = clave_par_equipos_h2h("Cadiz CF", "Levante UD")
        return {"enfrentamientos": {clave: {
            "casos_con_cuotas": casos, "tasa_sorpresa_historica": tasa,
        }}}

    def test_tasa_alta_es_senal(self):
        self.assertIsNotNone(sv.senal_h2h(_partido(), self._historial()))

    def test_tasa_baja_o_pocos_casos_no(self):
        self.assertIsNone(sv.senal_h2h(_partido(), self._historial(tasa=40.0)))
        self.assertIsNone(sv.senal_h2h(_partido(), self._historial(casos=1)))


class SenalSobrecompraTests(unittest.TestCase):
    def test_overreaction_sobre_el_favorito(self):
        partido = _partido(probs={"1": 55.0, "X": 25.0, "2": 20.0})
        masa = {"1": 70.0, "X": 18.0, "2": 12.0}  # masa juega el 1 a +15
        sorpresas = {"cadiz": [True, True, False]}
        senal = sv.senal_sobrecompra(partido, "X", masa, sorpresas)
        self.assertIsNotNone(senal)
        self.assertEqual(senal["tipo"], "sobrecompra_publico")

    def test_sin_overreaction_de_masa_no(self):
        partido = _partido(probs={"1": 55.0, "X": 25.0, "2": 20.0})
        masa = {"1": 60.0, "X": 25.0, "2": 15.0}  # solo +5
        self.assertIsNone(sv.senal_sobrecompra(partido, "X", masa, {"cadiz": [True, True]}))

    def test_sin_racha_de_sorpresas_no(self):
        partido = _partido(probs={"1": 55.0, "X": 25.0, "2": 20.0})
        masa = {"1": 70.0, "X": 18.0, "2": 12.0}
        self.assertIsNone(sv.senal_sobrecompra(partido, "X", masa, {"cadiz": [True, False, False]}))


class SorpresasPorEquipoTests(unittest.TestCase):
    def test_solo_jornadas_validas_y_anteriores(self):
        detalle = [
            # J75 de otra temporada (numeracion reiniciada): fuera
            {"jornada": 75, "partido": "Cadiz CF - Levante UD", "signo_real": "1",
             "probabilidades_usadas": {"1": 20.0, "X": 30.0, "2": 50.0}},
            # J2: Cadiz gana sin ser favorito -> sorpresa positiva
            {"jornada": 2, "partido": "Cadiz CF - Levante UD", "signo_real": "1",
             "probabilidades_usadas": {"1": 25.0, "X": 30.0, "2": 45.0}},
            # J3: Cadiz gana siendo favorito -> NO sorpresa
            {"jornada": 3, "partido": "Cadiz CF - Getafe CF", "signo_real": "1",
             "probabilidades_usadas": {"1": 55.0, "X": 25.0, "2": 20.0}},
            # J5: posterior al limite -> fuera
            {"jornada": 5, "partido": "Cadiz CF - Elche CF", "signo_real": "1",
             "probabilidades_usadas": {"1": 20.0, "X": 30.0, "2": 50.0}},
        ]
        resultado = sv.sorpresas_por_equipo(detalle, {2, 3, 4}, jornada_limite=5)
        self.assertEqual(resultado.get("cadiz"), [True, False])


class ElegirValienteTests(unittest.TestCase):
    def _partidos(self):
        return [
            _partido(num=1, probs={"1": 45.0, "X": 33.0, "2": 22.0}),
            _partido(num=2, local="Getafe CF", visitante="Elche CF",
                     probs={"1": 60.0, "X": 25.0, "2": 15.0}),
        ]

    def test_elige_la_candidata_con_senal_y_filtro(self):
        masa = {1: {"1": 55.0, "X": 20.0, "2": 25.0}, 2: {"1": 70.0, "X": 20.0, "2": 10.0}}
        fuentes = _fuentes(estudio_x=_estudio_empatador())
        eleccion, evaluados, vetados, _c = sv.elegir_valiente(self._partidos(), masa, fuentes)
        self.assertIsNotNone(eleccion)
        self.assertEqual((eleccion["num"], eleccion["signo"]), (1, "X"))
        self.assertEqual(eleccion["ventaja_sobre_masa"], 13.0)
        self.assertEqual(evaluados, 4)
        self.assertEqual(vetados, [])

    def test_sin_senal_no_hay_valiente(self):
        masa = {1: {"1": 55.0, "X": 20.0, "2": 25.0}, 2: {"1": 70.0, "X": 20.0, "2": 10.0}}
        eleccion, _, _, _c = sv.elegir_valiente(self._partidos(), masa, _fuentes())
        self.assertIsNone(eleccion)

    def test_filtro_de_pago_descarta_masa_alta(self):
        # la masa ya juega la X del partido 1 (33 - 8 = 25 > 27 no cumple)
        masa = {1: {"1": 48.0, "X": 27.0, "2": 25.0}, 2: {"1": 70.0, "X": 20.0, "2": 10.0}}
        eleccion, _, _, _c = sv.elegir_valiente(self._partidos(), masa, _fuentes(estudio_x=_estudio_empatador()))
        self.assertIsNone(eleccion)

    def test_prob_fuera_de_rango_descartada(self):
        partidos = [_partido(num=1, probs={"1": 30.0, "X": 52.0, "2": 18.0})]
        masa = {1: {"1": 50.0, "X": 25.0, "2": 25.0}}
        # X es favorita (no candidata) y 1 esta en rango pero sin senal; con
        # senal empatadora la X seguiria fuera por ser favorita del motor
        eleccion, _, _, _c = sv.elegir_valiente(partidos, masa, _fuentes(estudio_x=_estudio_empatador()))
        self.assertIsNone(eleccion)

    def test_gana_la_mayor_ventaja_sobre_la_masa(self):
        partidos = [
            _partido(num=1, probs={"1": 45.0, "X": 33.0, "2": 22.0}),
            _partido(num=2, local="Malaga CF", visitante="Getafe CF",
                     probs={"1": 45.0, "X": 36.0, "2": 19.0}),
        ]
        masa = {1: {"1": 55.0, "X": 20.0, "2": 25.0}, 2: {"1": 60.0, "X": 15.0, "2": 25.0}}
        estudio = {
            "equipos_empatadores": [
                {"equipo": "cadiz", "pj": 100, "x_pct": 36.0, "x_casa_pct": 30.0, "x_fuera_pct": 30.0},
                {"equipo": "malaga", "pj": 100, "x_pct": 34.0, "x_casa_pct": 30.0, "x_fuera_pct": 30.0},
            ],
            "fiabilidad_nuestra_por_equipo": [],
        }
        eleccion, _, _, _c = sv.elegir_valiente(partidos, masa, _fuentes(estudio_x=estudio))
        self.assertEqual(eleccion["num"], 2)  # ventaja 21 > 13


class VetosV2Tests(unittest.TestCase):
    """Vetos del prerregistro v2 (14/10/2026): probados y NO desplegados -su
    backtest empeoro el criterio vivo (ratio 1,30 -> 1,05)- pero el codigo
    queda testeado y reproducible por si un futuro backtest los reivindica."""

    def _estudio_madrid(self):
        return {
            "equipos_empatadores": [
                {"equipo": "madrid", "pj": 122, "x_pct": 15.6,
                 "x_casa_pct": 14.0, "x_fuera_pct": 17.0},
            ],
            "fiabilidad_nuestra_por_equipo": [],
        }

    def test_veto_grande_favorito(self):
        partido = _partido(local="Real Madrid CF", visitante="Malaga CF",
                           probs={"1": 53.5, "X": 33.2, "2": 13.3})
        vetos = sv.vetos_partido(partido, self._estudio_madrid())
        self.assertEqual([v["tipo"] for v in vetos], ["grande_favorito"])

    def test_veto_favorito_claro(self):
        partido = _partido(local="Real Betis Balompie", visitante="CA Osasuna",
                           probs={"1": 58.0, "X": 29.6, "2": 12.4})
        vetos = sv.vetos_partido(partido, {"equipos_empatadores": []})
        self.assertEqual([v["tipo"] for v in vetos], ["favorito_claro"])

    def test_partido_parejo_sin_vetos(self):
        partido = _partido(probs={"1": 45.0, "X": 33.0, "2": 22.0})
        self.assertEqual(sv.vetos_partido(partido, self._estudio_madrid()), [])

    def test_grande_no_favorito_no_veta(self):
        # el grande juega pero el favorito del motor es el OTRO equipo
        partido = _partido(local="Real Madrid CF", visitante="FC Barcelona",
                           probs={"1": 30.0, "X": 25.0, "2": 45.0})
        vetos = sv.vetos_partido(partido, self._estudio_madrid())
        self.assertEqual(vetos, [])

    def test_casos_reales_j3_y_j12_quedarian_vetados(self):
        # Con los datos REALES del repo: Madrid-Malaga (J3) y Betis-Osasuna
        # (J12), los dos fallos que señalo Marc, caen cada uno por su veto.
        estudio = json.loads(
            (ROOT / "data" / "memoria_ia" / "equipos_x_fiabilidad.json").read_text(encoding="utf-8-sig"))
        j3 = _partido(local="Real Madrid CF", visitante="Malaga CF",
                      probs={"1": 53.5, "X": 33.2, "2": 13.3})
        j12 = _partido(local="Real Betis Balompie", visitante="CA Osasuna",
                       probs={"1": 58.0, "X": 29.6, "2": 12.4})
        self.assertIn("grande_favorito", [v["tipo"] for v in sv.vetos_partido(j3, estudio)])
        self.assertIn("favorito_claro", [v["tipo"] for v in sv.vetos_partido(j12, estudio)])

    def test_elegir_con_vetos_salta_el_partido(self):
        partidos = [_partido(num=1, local="Real Madrid CF", visitante="Malaga CF",
                             probs={"1": 53.5, "X": 33.2, "2": 13.3})]
        masa = {1: {"1": 70.0, "X": 5.0, "2": 25.0}}
        estudio = self._estudio_madrid()
        estudio["equipos_empatadores"].append(
            {"equipo": "malaga", "pj": 92, "x_pct": 33.7, "x_casa_pct": 37.0, "x_fuera_pct": 30.4})
        eleccion, _, vetados, _c = sv.elegir_valiente(
            partidos, masa, _fuentes(estudio_x=estudio), aplicar_vetos=True)
        self.assertIsNone(eleccion)
        self.assertEqual(vetados[0]["vetos"], ["grande_favorito"])

    def test_por_defecto_los_vetos_no_se_aplican(self):
        # prerregistro v2 fallido: VETOS_V2_ACTIVOS debe seguir en False y la
        # seleccion por defecto NO veta (criterio vivo = v1)
        self.assertFalse(sv.VETOS_V2_ACTIVOS)
        partidos = [_partido(num=1, local="Real Madrid CF", visitante="Malaga CF",
                             probs={"1": 53.5, "X": 33.2, "2": 13.3})]
        masa = {1: {"1": 70.0, "X": 5.0, "2": 25.0}}
        estudio = self._estudio_madrid()
        estudio["equipos_empatadores"].append(
            {"equipo": "malaga", "pj": 92, "x_pct": 33.7, "x_casa_pct": 37.0, "x_fuera_pct": 30.4})
        eleccion, _, vetados, _c = sv.elegir_valiente(partidos, masa, _fuentes(estudio_x=estudio))
        self.assertIsNotNone(eleccion)
        self.assertEqual(vetados, [])

    def test_experimento_v2_documentado_en_el_backtest(self):
        datos = json.loads(
            (ROOT / "data" / "memoria_ia" / "backtest_valiente.json").read_text(encoding="utf-8"))
        exp = datos["experimento_vetos_v2"]
        self.assertIn("decision", exp)
        self.assertIn("ratio_v1", exp)
        self.assertIn("ratio_v2", exp)
        self.assertIn("veredicto", exp["resumen"])


class BloqueValienteTests(unittest.TestCase):
    def _prediccion(self, jornada=99, n=14, probs=None):
        return {
            "jornada": jornada,
            "partidos": [
                _partido(num=i, local=f"LOCAL{i}", visitante=f"VISITANTE{i}",
                         probs=dict(probs or {"1": 45.0, "X": 33.0, "2": 22.0}))
                for i in range(1, n + 1)
            ],
        }

    def _losilla(self, jornada=99, lae=None):
        lae = lae or {"1": 55, "X": 20, "2": 25}
        return {"probabilidades": {"jornada": jornada, "partidos": [
            {"numero": i, "fuentes_detalle": {"lae": dict(lae)},
             "probabilidades_signo": {"1": 45.0, "X": 33.0, "2": 22.0}}
            for i in range(1, 15)
        ]}}

    def test_sin_14_partidos_no_disponible(self):
        bloque = sv.construir_bloque_valiente(self._prediccion(n=10), self._losilla(), _fuentes())
        self.assertEqual(bloque["estado"], "no_disponible")

    def test_sin_masa_no_disponible(self):
        bloque = sv.construir_bloque_valiente(self._prediccion(jornada=98), self._losilla(jornada=97), _fuentes())
        self.assertEqual(bloque["estado"], "no_disponible")
        self.assertIn("masa", bloque["motivo"])

    def test_sin_candidatas_declara_sin_valiente(self):
        bloque = sv.construir_bloque_valiente(self._prediccion(), self._losilla(), _fuentes())
        self.assertEqual(bloque["estado"], "sin_valiente")
        self.assertEqual(bloque["modo"], "sombra")
        self.assertIn("parte del diseño", bloque["motivo"])

    def test_con_senal_y_filtro_sale_la_valiente(self):
        fuentes = _fuentes(h2h={"enfrentamientos": {
            clave_par_equipos_h2h("LOCAL3", "VISITANTE3"): {
                "casos_con_cuotas": 3, "tasa_sorpresa_historica": 66.7,
            },
        }})
        bloque = sv.construir_bloque_valiente(self._prediccion(), self._losilla(), fuentes)
        self.assertEqual(bloque["estado"], "ok")
        self.assertEqual(bloque["modo"], "sombra")
        self.assertEqual(bloque["num"], 3)
        self.assertEqual(bloque["signo"], "X")
        self.assertEqual(bloque["prob_motor"], 33.0)
        self.assertEqual(bloque["masa_pct"], 20.0)
        self.assertTrue(bloque["senales"])
        self.assertIn("sombra", bloque["aviso"].lower())


class MarcadorValienteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.dir_pred = base / "predicciones"
        self.dir_jorn = base / "jornadas"
        self.ruta = base / "marcador_valiente.json"
        self.dir_pred.mkdir()
        self.dir_jorn.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _escribir(self, jornada=20, signo_oficial="X", local="Cadiz CF",
                  visitante="Levante UD", local_fixture=None, visitante_fixture=None):
        bloque = {
            "estado": "ok", "modo": "sombra", "jornada": jornada, "num": 5,
            "local": local, "visitante": visitante, "signo": "X",
            "prob_motor": 32.0, "masa_pct": 16.0,
            "senales": [{"tipo": "empatador", "texto": "..."}],
        }
        (self.dir_pred / f"jornada_{jornada}.json").write_text(
            json.dumps({"jornada": jornada, "valiente": bloque}), encoding="utf-8")
        (self.dir_jorn / f"jornada_{jornada}.json").write_text(json.dumps({
            "jornada": jornada,
            "partidos": [{"num": 5, "local": local_fixture or local,
                          "visitante": visitante_fixture or visitante,
                          "signo_oficial": signo_oficial}],
        }), encoding="utf-8")

    def _actualizar(self):
        return sv.actualizar_marcador_valiente(
            dir_predicciones=self.dir_pred, dir_jornadas=self.dir_jorn,
            ruta_marcador=self.ruta, etiqueta="2026_2027")

    def test_registra_acierto_con_pago_hipotetico(self):
        self._escribir(signo_oficial="X")
        resultado = self._actualizar()
        self.assertEqual(resultado["nuevas"], 1)
        marcador = json.loads(self.ruta.read_text(encoding="utf-8"))
        v = marcador["valientes"][0]
        self.assertTrue(v["acierto"])
        self.assertEqual(v["pago_hipotetico_eur"], 6.25)  # 100/16
        self.assertEqual(marcador["resumen"]["aciertos"], 1)
        self.assertIn("Prerregistrado", marcador["criterio_graduacion"])

    def test_es_idempotente_por_temporada_y_jornada(self):
        self._escribir()
        self._actualizar()
        resultado = self._actualizar()
        self.assertEqual(resultado["nuevas"], 0)
        marcador = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.assertEqual(len(marcador["valientes"]), 1)

    def test_jornada_abierta_no_se_registra(self):
        self._escribir(signo_oficial="Pendiente")
        self.assertEqual(self._actualizar()["nuevas"], 0)

    def test_nombres_de_otra_temporada_no_puntuan(self):
        # mismo num y jornada pero NINGUN nombre casa: fixture de otra epoca
        self._escribir(local_fixture="Real Zaragoza", visitante_fixture="SD Huesca")
        self.assertEqual(self._actualizar()["nuevas"], 0)

    def test_fallo_registra_pago_cero(self):
        self._escribir(signo_oficial="1")
        self._actualizar()
        marcador = json.loads(self.ruta.read_text(encoding="utf-8"))
        v = marcador["valientes"][0]
        self.assertFalse(v["acierto"])
        self.assertEqual(v["pago_hipotetico_eur"], 0.0)


class GraduacionTests(unittest.TestCase):
    def _valientes(self, n, aciertos, prob=30.0):
        return [{"acierto": i < aciertos, "prob_declarada": prob,
                 "pago_hipotetico_eur": 5.0 if i < aciertos else 0.0}
                for i in range(n)]

    def test_menos_de_12_sigue_en_sombra(self):
        resumen = sv._resumen_marcador(self._valientes(11, aciertos=8))
        self.assertEqual(resumen["estado"], "en_sombra")

    def test_candidata_a_dinero(self):
        # 12 valientes al 30% declarado = 3,6 esperados; 4 aciertos (>=3) gradua
        resumen = sv._resumen_marcador(self._valientes(12, aciertos=4))
        self.assertEqual(resumen["estado"], "candidata_a_dinero")
        self.assertTrue(resumen["avisar_a_marc"])

    def test_suspendida_por_debajo_del_60_pct(self):
        # 12 valientes al 30% = 3,6 esperados; 1 acierto < 2,16 suspende
        resumen = sv._resumen_marcador(self._valientes(12, aciertos=1))
        self.assertEqual(resumen["estado"], "suspendida")

    def test_zona_intermedia_sigue_en_sombra(self):
        # 3 aciertos con 3,6 esperados: ni gradua ni suspende
        resumen = sv._resumen_marcador(self._valientes(12, aciertos=3))
        self.assertEqual(resumen["estado"], "en_sombra")


class PipelineTests(unittest.TestCase):
    def test_cableado_en_el_pipeline(self):
        import actualizar_todo
        self.assertIn("senal_valiente.py", actualizar_todo.SCRIPTS_ACTIVOS)
        self.assertIn("senal_valiente.py", actualizar_todo.SCRIPTS_NO_CRITICOS_RED)
        activos = actualizar_todo.SCRIPTS_ACTIVOS
        # corre justo despues del optimizador EV: misma prediccion corregida
        self.assertEqual(
            activos.index("senal_valiente.py"),
            activos.index("optimizador_ev_premio.py") + 1,
        )

    def test_limpiar_prediccion_bloqueada_retira_el_bloque(self):
        import limpiar_prediccion_bloqueada
        self.assertIn("valiente", limpiar_prediccion_bloqueada.CAMPOS_RAIZ_PREDICTIVOS)

    def test_marcador_enganchado_al_ciclo_de_aprendizaje(self):
        import generar_artefactos_compuerta_aprendizaje as gen
        self.assertTrue(hasattr(gen, "actualizar_marcador_valiente_seguro"))

    def test_backtest_prerregistrado_documentado(self):
        datos = json.loads(
            (ROOT / "data" / "memoria_ia" / "backtest_valiente.json").read_text(encoding="utf-8"))
        self.assertIn("criterios_prerregistrados", datos)
        resumen = datos["resumen"]
        for campo in ("valientes", "aciertos", "esperados", "veredicto"):
            self.assertIn(campo, resumen)


if __name__ == "__main__":
    unittest.main()


class SenalFavoritoMercadoTests(unittest.TestCase):
    def test_dispara_cuando_el_mercado_prefiere_el_signo_candidato(self):
        partido = _partido(probs={"1": 40.0, "X": 30.0, "2": 30.0},
                           mercado_losilla={"1": 30.0, "X": 25.0, "2": 45.0})
        senal = sv.senal_favorito_mercado(partido, "2")
        self.assertIsNotNone(senal)
        self.assertEqual(senal["tipo"], "favorito_distinto_mercado")

    def test_no_dispara_si_mercado_y_motor_coinciden(self):
        partido = _partido(probs={"1": 40.0, "X": 30.0, "2": 30.0},
                           mercado_losilla={"1": 50.0, "X": 25.0, "2": 25.0})
        self.assertIsNone(sv.senal_favorito_mercado(partido, "2"))

    def test_no_dispara_para_otro_signo_ni_sin_mercado(self):
        partido = _partido(probs={"1": 40.0, "X": 30.0, "2": 30.0},
                           mercado_losilla={"1": 30.0, "X": 25.0, "2": 45.0})
        self.assertIsNone(sv.senal_favorito_mercado(partido, "X"))
        self.assertIsNone(sv.senal_favorito_mercado(_partido(), "2"))


class PalpitosV3Tests(unittest.TestCase):
    def test_h2h_retirada_en_el_criterio_vivo(self):
        self.assertIn("h2h_caotico", sv.SENALES_RETIRADAS)
        # con la señal en suspendidas (como hace el bloque vivo), un candidato
        # cuyo unico apoyo era el h2h ya no es valiente
        partido = _partido(probs={"1": 45.0, "X": 30.0, "2": 25.0})
        fuentes = _fuentes(h2h={
            "enfrentamientos": {
                clave_par_equipos_h2h("Cadiz CF", "Levante UD"): {
                    "casos_con_cuotas": 3, "tasa_sorpresa_historica": 60.0,
                }
            }
        }, senales_suspendidas={"h2h_caotico"})
        masa = {1: {"1": 40.0, "X": 10.0, "2": 50.0}}
        eleccion, _, _, _c = sv.elegir_valiente([partido], masa, fuentes)
        self.assertIsNone(eleccion)

    def test_palpitos_ordenados_y_el_primero_es_la_valiente(self):
        partidos = [
            _partido(num=1, probs={"1": 45.0, "X": 36.0, "2": 19.0}),
            _partido(num=2, local="Cadiz CF", visitante="Getafe CF",
                     probs={"1": 45.0, "X": 36.0, "2": 19.0}),
        ]
        estudio = _estudio_empatador(x_pct=36.0)
        masa = {1: {"1": 60.0, "X": 10.0, "2": 30.0}, 2: {"1": 55.0, "X": 20.0, "2": 25.0}}
        prediccion = {
            "jornada": 99,
            "partidos": partidos + [
                _partido(num=n, probs={"1": 70.0, "X": 20.0, "2": 10.0}) for n in range(3, 15)
            ],
        }
        masa_completa = {n: {"1": 70.0, "X": 20.0, "2": 10.0} for n in range(3, 15)}
        masa_completa.update(masa)
        import optimizador_ev_premio as ev
        original = ev.porcentajes_masa
        ev_pm = lambda jornada, fl: (masa_completa, "test")
        try:
            import senal_valiente as mod
            mod_pm = mod.porcentajes_masa
            mod.porcentajes_masa = ev_pm
            bloque = mod.construir_bloque_valiente(
                prediccion, {}, fuentes=_fuentes(
                    estudio_x=estudio, senales_suspendidas=set()))
        finally:
            mod.porcentajes_masa = mod_pm
        self.assertEqual(bloque.get("estado"), "ok")
        palpitos = bloque.get("palpitos") or []
        self.assertGreaterEqual(len(palpitos), 2)
        self.assertLessEqual(len(palpitos), sv.PALPITOS_MAX)
        self.assertTrue(palpitos[0]["es_la_valiente"])
        self.assertEqual(palpitos[0]["num"], bloque["num"])
        self.assertGreaterEqual(palpitos[0]["ventaja_sobre_masa"],
                                palpitos[1]["ventaja_sobre_masa"])
        for i, p in enumerate(palpitos, start=1):
            self.assertEqual(p["orden"], i)
