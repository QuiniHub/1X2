"""Tests de la Sorpresa Nombrada (22/11/2026): señales sin fuga de futuro,
eleccion con desempate por hora y marcador de sombra."""
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import sorpresa_nombrada as sn
import test_aud_P4_sombra_snapshot_util as util


def _partidos_cal(tmp, *filas):
    """filas: (fecha, local, visitante, resultado)."""
    ruta = Path(tmp) / "cal.json"
    ruta.write_text(json.dumps({"jornadas": [{"jornada": 1, "partidos": [
        {"fecha": f, "local": l, "visitante": v, "resultado": r} for f, l, v, r in filas]}]}), encoding="utf-8")
    return sn.cargar_calendarios([ruta])


def _partido(num, local, visitante, probs, signo_final="1", mercado=None):
    return {"num": num, "local": local, "visitante": visitante, "probabilidades": probs,
            "signo_final": signo_final, "mercado_losilla": mercado or {}}


def _fuentes(cal):
    return {"ceses": [], "estudio_x": {}, "calendario": cal, "senales_suspendidas": set()}


class SenalesTests(unittest.TestCase):
    def test_especialista_de_rol_solo_cuenta_partidos_anteriores(self):
        with tempfile.TemporaryDirectory() as tmp:
            cal = _partidos_cal(
                tmp,
                ("2026-10-11", "Racing", "Valencia CF", "0-1"), ("2026-11-01", "Elche CF", "Valencia CF", "0-1"),
                ("2026-09-20", "Valencia CF", "Athletic Club", "0-0"), ("2026-10-05", "Valencia CF", "Getafe CF", "1-1"),
                ("2026-10-24", "Valencia CF", "Villarreal CF", "1-2"),
                ("2026-11-21", "Rayo Vallecano de Madrid", "Valencia CF", "0-1"),  # el partido de hoy: NO cuenta
                ("2026-12-05", "Valencia CF", "Sevilla FC", "3-0"),  # futuro: NO cuenta
            )
            p = _partido(2, "Rayo Vallecano de Madrid", "Valencia CF", {"1": 45, "X": 30, "2": 25})
            s = sn.senal_especialista_de_rol(p, "2", date(2026, 11, 21), cal)
            self.assertTrue(s and s["tipo"] == "especialista_de_rol")
            self.assertIn("2 victorias fuera", s["texto"])
            # con la victoria futura en casa ya contada, no habria señal
            self.assertIsNone(sn.senal_especialista_de_rol(p, "2", date(2026, 12, 20), cal))
            # signo 1 no aplica al visitante
            self.assertIsNone(sn.senal_especialista_de_rol(p, "1", date(2026, 11, 21), cal))

    def test_h2h_adverso_reciente_mismo_campo(self):
        with tempfile.TemporaryDirectory() as tmp:
            cal = _partidos_cal(
                tmp,
                ("2025-10-19", "Real Madrid CF", "RC Celta de Vigo", "0-2"),
                ("2026-03-01", "RC Celta de Vigo", "Real Madrid CF", "0-3"),
            )
            p = _partido(3, "Real Madrid CF", "RC Celta de Vigo", {"1": 70, "X": 18, "2": 12})
            s = sn.senal_h2h_adverso_reciente(p, "2", date(2026, 11, 21), cal)
            self.assertTrue(s and "0-2" in s["texto"])
            self.assertIsNone(sn.senal_h2h_adverso_reciente(p, "X", date(2026, 11, 21), cal))
            # antes de ese cruce no hay historial
            self.assertIsNone(sn.senal_h2h_adverso_reciente(p, "2", date(2025, 10, 1), cal))

    def test_banquillo_nuevo_exige_partidos_con_el_nuevo(self):
        with tempfile.TemporaryDirectory() as tmp:
            cal = _partidos_cal(
                tmp,
                ("2026-10-11", "Racing", "Valencia CF", "0-1"), ("2026-10-24", "Valencia CF", "Villarreal CF", "1-2"),
            )
            ceses = [{"equipo": "Valencia CF", "fecha_cese": "2026-09-13", "fecha_nuevo": "2026-09-23"}]
            p = _partido(2, "Rayo Vallecano de Madrid", "Valencia CF", {"1": 45, "X": 30, "2": 25})
            self.assertTrue(sn.senal_banquillo_nuevo(p, "2", date(2026, 11, 21), ceses, cal))
            self.assertIsNone(sn.senal_banquillo_nuevo(p, "2", date(2026, 10, 12), ceses, cal))  # solo 1 partido
            self.assertIsNone(sn.senal_banquillo_nuevo(p, "1", date(2026, 11, 21), ceses, cal))

    def test_mercado_mas_alto(self):
        p = _partido(8, "Tenerife", "RCD Mallorca", {"1": 33, "X": 38, "2": 28}, mercado={"1": 30, "X": 30, "2": 40})
        self.assertTrue(sn.senal_mercado_mas_alto(p, "2"))
        self.assertIsNone(sn.senal_mercado_mas_alto(p, "1"))


class EleccionTests(unittest.TestCase):
    def test_franja_y_desempate_por_hora(self):
        with tempfile.TemporaryDirectory() as tmp:
            cal = _partidos_cal(tmp, ("2026-05-01", "A", "B", "0-1"), ("2026-05-02", "C", "D", "0-1"))
            partidos = [
                _partido(1, "A", "B", {"1": 50, "X": 25, "2": 25}),  # h2h: 2
                _partido(2, "C", "D", {"1": 50, "X": 25, "2": 25}),  # h2h: 2, juega antes
                _partido(3, "E", "F", {"1": 85, "X": 8, "2": 7}),    # fuera de franja
            ] + [_partido(n, f"L{n}", f"V{n}", {"1": 60, "X": 22, "2": 18}) for n in range(4, 15)]
            fechas = {1: {"fecha": "2026-11-22", "hora": "14:00"}, 2: {"fecha": "2026-11-21", "hora": "16:15"}}
            nombrada, candidatas, _ = sn.elegir_sorpresa(partidos, fechas, _fuentes(cal))
            self.assertEqual(nombrada["num"], 2)
            self.assertEqual(nombrada["signo"], "2")
            self.assertEqual([c["num"] for c in candidatas], [2, 1])

    def test_mas_senales_gana_a_la_hora(self):
        with tempfile.TemporaryDirectory() as tmp:
            cal = _partidos_cal(tmp, ("2026-05-01", "A", "B", "0-1"))
            mercado = {"1": 40, "X": 25, "2": 35}
            partidos = [
                _partido(1, "A", "B", {"1": 50, "X": 25, "2": 25}, mercado=mercado),  # h2h + mercado
                _partido(2, "C", "D", {"1": 50, "X": 25, "2": 25}, mercado=mercado),  # mercado
            ] + [_partido(n, f"L{n}", f"V{n}", {"1": 60, "X": 22, "2": 18}) for n in range(3, 15)]
            fechas = {1: {"fecha": "2026-11-22", "hora": "21:00"}, 2: {"fecha": "2026-11-21", "hora": "14:00"}}
            nombrada, _, _ = sn.elegir_sorpresa(partidos, fechas, _fuentes(cal))
            self.assertEqual(nombrada["num"], 1)

    def test_bloque_sin_candidatas_lo_dice(self):
        partidos = [_partido(n, f"L{n}", f"V{n}", {"1": 60, "X": 22, "2": 18}) for n in range(1, 15)]
        bloque = sn.construir_bloque_sorpresa({"jornada": 30, "partidos": partidos}, fechas={}, fuentes=_fuentes([]))
        self.assertEqual(bloque["estado"], "sin_sorpresa_nombrada")
        self.assertEqual(bloque["modo"], "sombra")

    def test_cubierta_por_boleto(self):
        with tempfile.TemporaryDirectory() as tmp:
            cal = _partidos_cal(tmp, ("2026-05-01", "A", "B", "0-1"))
            partidos = [_partido(1, "A", "B", {"1": 50, "X": 25, "2": 25}, signo_final="12")] + \
                       [_partido(n, f"L{n}", f"V{n}", {"1": 60, "X": 22, "2": 18}) for n in range(2, 15)]
            bloque = sn.construir_bloque_sorpresa({"jornada": 30, "partidos": partidos},
                                                  fechas={1: {"fecha": "2026-11-22", "hora": "14:00"}}, fuentes=_fuentes(cal))
            self.assertEqual(bloque["estado"], "ok")
            self.assertTrue(bloque["cubierta_por_boleto"])


class MarcadorTests(unittest.TestCase):
    """Auditoria 26/11: el marcador lee el bloque del snapshot PRE-CIERRE."""

    def _bloque(self, num=2, signo="2"):
        local, visitante = util.EQUIPOS[num - 1]
        return {"estado": "ok", "jornada": 12, "num": num, "local": local, "visitante": visitante, "signo": signo,
                "prob_motor": 25.0, "senales": [{"tipo": "h2h_adverso_reciente"}], "cubierta_por_boleto": False,
                "fecha": "2026-11-21", "hora": "16:15"}

    def _montar(self, tmp, signo_oficial="2", bloques=None):
        tmp = Path(tmp)
        (tmp / "pred").mkdir()
        self.jor, self.snap = util.montar_cierre(
            tmp, 12, {"sorpresa_nombrada": self._bloque()} if bloques is None else bloques,
            signos={2: signo_oficial})
        return tmp

    def _actualizar(self, tmp, etiqueta="2026_2027"):
        ahora = datetime(2026, 11, 23, tzinfo=timezone.utc)
        return sn.actualizar_marcador(tmp / "pred", self.jor, tmp / "m.json", etiqueta=etiqueta, ahora=ahora,
                                      dir_snapshots=self.snap)

    def test_registra_y_es_idempotente(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._montar(tmp)
            r = self._actualizar(tmp)
            self.assertEqual(r["nuevas"], 1)
            self.assertEqual(r["resumen"]["aciertos"], 1)
            self.assertEqual(r["resumen"]["vistas_y_no_pagadas"], 1)
            self.assertEqual(r["resumen"]["veredicto"], "en_prueba")
            self.assertEqual(self._actualizar(tmp)["nuevas"], 0)
            # now() en julio de 2027 cambiaba la etiqueta y lo registraba otra vez
            self.assertEqual(self._actualizar(tmp, etiqueta="2027_2028")["nuevas"], 0)
            registros = json.loads((tmp / "m.json").read_text(encoding="utf-8"))["jornadas"]
            self.assertEqual([r["temporada"] for r in registros], ["2026_2027"])

    def test_jornada_abierta_no_se_registra(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._montar(tmp, signo_oficial="Pendiente")
            self.assertEqual(self._actualizar(tmp)["nuevas"], 0)

    def test_un_bloque_que_solo_esta_en_el_espejo_no_se_registra(self):
        # J23 real: el modulo nacio el 22/11, con el Rayo-Valencia ya jugado
        # (21/11), y el marcador apunto un "acierto" que nadie dijo antes del
        # cierre. Sin bloque en el snapshot pre-cierre no hay registro.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = self._montar(tmp, bloques={})
            (tmp / "pred" / "jornada_12.json").write_text(
                json.dumps({"jornada": 12, "sorpresa_nombrada": self._bloque()}), encoding="utf-8")
            self.assertEqual(self._actualizar(tmp)["nuevas"], 0)

    def test_signo_real_casa_equipos_femeninos_y_alias(self):
        # Auditoria 26/11: 'Hacken (F)' frente a 'Hacken W' no casaba.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            util.escribir_jornada(tmp, 22, nombres=[("Hacken W", "Manchester City W")] + util.EQUIPOS[1:],
                                  signos={1: "X"})
            bloque = {"jornada": 22, "num": 1, "local": "Hacken (F)", "visitante": "Manchester City (F)"}
            self.assertEqual(sn._signo_real(bloque, tmp), "X")
            ajeno = {"jornada": 22, "num": 1, "local": "Real Zaragoza", "visitante": "SD Huesca"}
            self.assertIsNone(sn._signo_real(ajeno, tmp))

    def test_freno_por_senal(self):
        regs = [{"estado": "nombrada", "acierto": False, "prob_declarada": 30.0, "senales": ["empatador"]} for _ in range(8)]
        resumen = sn.resumen_marcador(regs)
        self.assertEqual(resumen["senales_suspendidas"], ["empatador"])


if __name__ == "__main__":
    unittest.main()
