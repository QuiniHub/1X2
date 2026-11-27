"""Revisor de boleto: aplica las reglas aprendidas a CUALQUIER boleto (27/11/2026).

Marc, 27/11/2026: "llevo 6 meses diciendo que se debe aprender... y resulta
que se anota y no se aplica". Las reglas vivian como texto (memoria de
Claude, cuaderno, memoria del chat) y solo se aplicaban si alguien se
acordaba. Desde hoy viven en data/memoria_ia/reglas_boleto.json y este
modulo las comprueba:

- en el pipeline, sobre el boleto del motor (bloque "revision_boleto" en
  ultima_prediccion.json, tarjeta "Revisor de boleto" en la web);
- a mano, sobre el boleto que proponga Claude o el que vaya a sellar Marc:

    python revisar_boleto.py "1 2 2 1 1X 2 1X2 12 1 1X2 1X 1 1X2 1" --apuestas 24 --presupuesto 18 --bote 1100000

Los avisos no cambian el boleto: dicen que regla se incumple, con su dato,
y que cambio la cumpliria. Decidir sigue siendo de Marc.
"""
import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
PREDICCIONES_DIR = DATA / "predicciones"
REGLAS = DATA / "memoria_ia" / "reglas_boleto.json"
SIGNOS = ("1", "X", "2")
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
PRECIO_APUESTA = 0.75


def cargar_json(ruta, defecto=None):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(ruta, datos):
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def cargar_reglas(ruta=None):
    datos = cargar_json(ruta or REGLAS, {}) or {}
    return {r["id"]: r for r in datos.get("reglas", []) if r.get("activa", True)}


def normalizar_signos(texto_o_lista):
    """'1 2 1X2 X2 ...' o lista -> lista de 14 cadenas ordenadas como 1X2."""
    partes = texto_o_lista.replace(",", " ").split() if isinstance(texto_o_lista, str) else list(texto_o_lista)
    salida = []
    for p in partes:
        p = str(p).upper().replace("0", "X")
        sig = "".join(s for s in SIGNOS if s in p)
        if not sig:
            raise ValueError(f"signo no valido: {p!r}")
        salida.append(sig)
    if len(salida) != 14:
        raise ValueError(f"hacen falta 14 signos y hay {len(salida)}")
    return salida


def probs_mercado(partido):
    """Probabilidades (0-1) del mercado Losilla del partido; si no hay, las publicadas."""
    for clave in ("mercado_losilla", "probabilidades"):
        m = partido.get(clave) or {}
        try:
            total = sum(float(m.get(s) or 0) for s in SIGNOS)
        except (TypeError, ValueError):
            total = 0
        if total > 0:
            return {s: float(m.get(s) or 0) / total for s in SIGNOS}, clave
    return {s: 1 / 3 for s in SIGNOS}, "uniforme"


def _fecha(valor):
    try:
        return date.fromisoformat(str(valor)[:10])
    except (TypeError, ValueError):
        return None


def contexto_jornada(prediccion):
    """Fechas por partido (de data/jornadas) y si la jornada es europea."""
    jornada = prediccion.get("jornada")
    fechas, europea = {}, False
    try:
        import cronologia_jornadas as cj
        datos = cj.cargar_jornada(jornada) if isinstance(jornada, int) else None
    except Exception:
        datos = None
    datos = datos or cargar_json(DATA / "jornadas" / f"jornada_{jornada}.json", {}) or {}
    for p in datos.get("partidos") or []:
        f = _fecha(p.get("fecha"))
        if isinstance(p.get("num"), int) and f:
            fechas[p["num"]] = f
    try:
        from columna_valiente import es_jornada_europea
        europea = bool(es_jornada_europea([p for p in prediccion.get("partidos", []) if (p.get("num") or 99) <= 14])[0])
    except Exception:
        europea = False
    return fechas, europea


def forma_casa_fuera(equipo, lado, hasta, n=5, partidos=None):
    """Puntos por partido de los ultimos n partidos EN CASA (lado='casa') o
    FUERA (lado='fuera') antes de la fecha 'hasta', esta temporada."""
    try:
        from sorpresa_nombrada import cargar_calendarios
        from modelo_dixon_coles import clave_equipo
    except Exception:
        return None, 0
    partidos = partidos if partidos is not None else cargar_calendarios()
    clave = clave_equipo(equipo)
    inicio = date(hasta.year if hasta.month >= 8 else hasta.year - 1, 8, 1)
    sel = [p for p in partidos if inicio <= p["fecha"] < hasta
           and ((lado == "casa" and p["kl"] == clave) or (lado == "fuera" and p["kv"] == clave))][-n:]
    if not sel:
        return None, 0
    pts = 0
    for p in sel:
        g_propio, g_rival = (p["gl"], p["gv"]) if lado == "casa" else (p["gv"], p["gl"])
        pts += 3 if g_propio > g_rival else 1 if g_propio == g_rival else 0
    return pts / len(sel), len(sel)


def aviso(regla, severidad, mensaje, sugerencia="", partido=None):
    return {"regla": regla["id"], "titulo": regla["titulo"], "severidad": severidad,
            "partido": partido, "mensaje": mensaje, "sugerencia": sugerencia, "dato": regla.get("dato", "")}


def revisar(signos, prediccion, reglas=None, apuestas=None, presupuesto=None, bote=None,
            elige8=False, sorpresas_extra=None, fechas=None, europea=None, calendario=None):
    reglas = reglas if reglas is not None else cargar_reglas()
    signos = normalizar_signos(signos)
    partidos = {p["num"]: p for p in prediccion.get("partidos", []) if isinstance(p.get("num"), int) and p["num"] <= 14}
    if fechas is None or europea is None:
        f2, e2 = contexto_jornada(prediccion)
        fechas = f2 if fechas is None else fechas
        europea = e2 if europea is None else europea
    avisos = []
    nombre = lambda k: f"P{k} {partidos.get(k, {}).get('local', '?')} - {partidos.get(k, {}).get('visitante', '?')}"

    dobles_1x = []
    for k in range(1, 15):
        sig = signos[k - 1]
        p = partidos.get(k)
        if not p:
            continue
        q, fuente_q = probs_mercado(p)
        fav = max(SIGNOS, key=q.get)

        # R02 favorito del mercado fuera
        r = reglas.get("R02_favorito_mercado_fuera")
        if r and len(sig) < 3 and fav not in sig and fuente_q == "mercado_losilla":
            segundo = sorted(q.values(), reverse=True)[1]
            if (q[fav] - segundo) * 100 >= r["parametros"].get("margen_minimo_pts", 3):
                avisos.append(aviso(r, r["severidad"],
                                    f"{nombre(k)}: juegas {sig} y el favorito del mercado es el {fav} ({q[fav]*100:.0f}%).",
                                    f"incluir el {fav} (por ejemplo {''.join(s for s in SIGNOS if s in sig + fav)})", k))

        # R01 doble 1X por costumbre
        r = reglas.get("R01_doble_1x_por_costumbre")
        if r and sig == "1X":
            dobles_1x.append(k)
            f = r["parametros"].get("factor_2", 1.35)
            q2 = dict(q)
            q2["2"] *= f
            t = sum(q2.values())
            q2 = {s: v / t for s, v in q2.items()}
            if q2["1"] + q2["2"] > q2["1"] + q2["X"]:
                avisos.append(aviso(r, r["severidad"],
                                    f"{nombre(k)}: 1X cubre {(q2['1']+q2['X'])*100:.0f}% y 12 cubre {(q2['1']+q2['2'])*100:.0f}% con el 2 corregido.",
                                    "jugar 12", k))

        # R06 dobles 1X del sabado
        r = reglas.get("R06_dobles_del_sabado")
        if r and sig == "1X" and fechas.get(k) and fechas[k].weekday() == 5:
            avisos.append(aviso(r, r["severidad"],
                                f"{nombre(k)}: doble 1X en sabado; el 2 del visitante esta al {q['2']*100:.0f}% en el mercado.",
                                "comprobar si el compañero correcto es el 2", k))

        # R04 favorito local en racha en casa cubierto de mas / R05 racha fuera
        hasta = fechas.get(k)
        if hasta:
            r = reglas.get("R04_fijo_local_racha_casa")
            if r and len(sig) > 1 and fav == "1" and q["1"] * 100 >= r["parametros"].get("prob_minima", 55):
                ppp, n = forma_casa_fuera(p.get("local", ""), "casa", hasta, r["parametros"].get("ultimos", 5), calendario)
                if ppp is not None and n >= 3 and ppp >= r["parametros"].get("puntos_casa_minimos", 2.2):
                    avisos.append(aviso(r, r["severidad"],
                                        f"{nombre(k)}: el local es favorito ({q['1']*100:.0f}%) y suma {ppp:.1f} puntos por partido en sus ultimos {n} en casa; llevas {sig}.",
                                        "fijo 1 y usar esa cobertura en otro partido", k))
            r = reglas.get("R05_racha_fuera_no_es_senal")
            if r and "2" in sig and fav != "2" and len(sig) < 3:
                ppp, n = forma_casa_fuera(p.get("visitante", ""), "fuera", hasta, 5, calendario)
                if ppp is not None and n >= 3 and ppp >= r["parametros"].get("puntos_fuera", 2.2):
                    avisos.append(aviso(r, r["severidad"],
                                        f"{nombre(k)}: juegas el 2 de un visitante que no es favorito ({q['2']*100:.0f}%) y viene de {ppp:.1f} puntos fuera; esa racha no es señal.",
                                        "justificarlo con otra señal o quitar el 2", k))

    # R01 general: todos los dobles 1X
    r = reglas.get("R01_doble_1x_por_costumbre")
    dobles = [k for k in range(1, 15) if len(signos[k - 1]) == 2]
    if r and len(dobles) >= 2 and len(dobles_1x) == len(dobles):
        avisos.append(aviso(r, r["severidad"], f"Todos los dobles son 1X ({len(dobles)}): revisar al menos uno.",
                            "comprobar el 2 en cada doble"))

    # R03 cubrir lo que se nombra
    r = reglas.get("R03_cubrir_lo_que_se_nombra")
    if r:
        nombradas = []
        sn = prediccion.get("sorpresa_nombrada") or {}
        if sn.get("estado") == "ok" and isinstance(sn.get("num"), int):
            nombradas.append((sn["num"], sn.get("signo"), "Sorpresa Nombrada del motor"))
        for k, s in (sorpresas_extra or []):
            nombradas.append((k, s, "sorpresa nombrada en el analisis"))
        for k, s, origen in nombradas:
            if 1 <= k <= 14 and s and s not in signos[k - 1]:
                avisos.append(aviso(r, r["severidad"], f"{nombre(k)}: {origen} = {s} y el boleto no la cubre.",
                                    f"añadir el {s} en ese partido o decir en voz alta que se deja fuera por dinero", k))

    # R07 presupuesto y bote
    r = reglas.get("R07_presupuesto_y_bote")
    columnas = 1
    for s in signos:
        columnas *= len(s)
    apuestas = apuestas or columnas
    coste = apuestas * PRECIO_APUESTA + (0.5 if elige8 else 0)
    if r:
        pr = r["parametros"]
        if presupuesto is not None and coste > presupuesto + 1e-9:
            avisos.append(aviso(r, r["severidad"], f"Coste {coste:.2f} EUR por encima del presupuesto de {presupuesto:.2f} EUR.",
                                "reducir coberturas o usar una reducida a medida"))
        elif presupuesto is None and coste > pr.get("base_max_eur", 40) and (bote is None or bote < pr.get("bote_escalon_1", 2000000)):
            avisos.append(aviso(r, r["severidad"], f"Coste {coste:.2f} EUR por encima de la base ({pr.get('base_max_eur', 40)} EUR) sin bote de 2 M.",
                                "volver a la base o reservar el extra para semanas de bote"))

    # R08 Elige 8 en Europa
    r = reglas.get("R08_elige8_europa")
    if r and elige8 and europea:
        avisos.append(aviso(r, r["severidad"], "Elige 8 en jornada europea.", "no jugarlo esta semana"))

    # R09 X esperadas frente a cubiertas
    r = reglas.get("R09_x_cubiertas")
    if r:
        esperadas = sum(probs_mercado(partidos[k])[0]["X"] for k in partidos)
        cubiertas = sum(1 for k in partidos if "X" in signos[k - 1])
        if esperadas - cubiertas > r["parametros"].get("brecha_maxima", 2):
            avisos.append(aviso(r, r["severidad"], f"Se esperan {esperadas:.1f} X y el boleto cubre {cubiertas}.",
                                "recolocar algun doble para cubrir la X"))

    orden = {"alta": 0, "media": 1, "baja": 2}
    avisos.sort(key=lambda a: (orden.get(a["severidad"], 9), a.get("partido") or 0))
    return {
        "estado": "ok", "signos": signos, "apuestas": apuestas, "coste_eur": round(coste, 2),
        "avisos": avisos,
        "resumen": {s: sum(1 for a in avisos if a["severidad"] == s) for s in ("alta", "media", "baja")},
        "reglas_aplicadas": sorted(reglas.keys()),
        "recordatorios": [reglas[k]["titulo"] + ": " + reglas[k]["dato"] for k in ("R10_reducidas_losilla_a_medida",) if k in reglas],
    }


def boleto_del_motor(prediccion):
    return [str((p.get("signo_final") or "")).upper() for p in sorted(
        [p for p in prediccion.get("partidos", []) if isinstance(p.get("num"), int) and p["num"] <= 14], key=lambda p: p["num"])]


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Revisa un boleto contra las reglas aprendidas")
    ap.add_argument("signos", nargs="?", help="14 signos separados por espacios; sin el, revisa el boleto del motor y lo publica")
    ap.add_argument("--apuestas", type=int)
    ap.add_argument("--presupuesto", type=float)
    ap.add_argument("--bote", type=float, help="un unico acertante puede ganar (EUR)")
    ap.add_argument("--elige8", action="store_true")
    ap.add_argument("--sorpresa", action="append", default=[], help="sorpresa nombrada a mano, formato 8:2")
    args = ap.parse_args(argv)
    prediccion = cargar_json(PREDICCION, {}) or {}
    if not prediccion.get("partidos"):
        print("Sin ultima_prediccion.json; nada que revisar.")
        return
    extra = []
    for s in args.sorpresa:
        num, sig = s.split(":")
        extra.append((int(num), sig.strip().upper()))
    publicar = args.signos is None
    if publicar and (not prediccion.get("prediccion_disponible") or not prediccion.get("prediccion_permitida")):
        if prediccion.pop("revision_boleto", None) is not None:
            guardar_json(PREDICCION, prediccion)
        print("Prediccion bloqueada; bloque revision_boleto retirado.")
        return
    signos = args.signos or boleto_del_motor(prediccion)
    apuestas = args.apuestas or ((prediccion.get("coste") or {}).get("apuestas") if publicar else None)
    res = revisar(signos, prediccion, apuestas=apuestas, presupuesto=args.presupuesto, bote=args.bote,
                  elige8=args.elige8 or (publicar and bool((prediccion.get("configuracion") or {}).get("elige8"))),
                  sorpresas_extra=extra)
    res["jornada"] = prediccion.get("jornada")
    res["origen"] = "boleto del motor" if publicar else "boleto revisado a mano"
    res["generado_en"] = datetime.now(timezone.utc).isoformat()
    print(f"Revisor de boleto J{res['jornada']} ({res['origen']}): {' '.join(res['signos'])} | {res['apuestas']} apuestas, {res['coste_eur']:.2f} EUR")
    if not res["avisos"]:
        print("  Sin avisos: el boleto cumple las reglas aprendidas.")
    for a in res["avisos"]:
        print(f"  [{a['severidad'].upper()}] {a['regla']}: {a['mensaje']}" + (f" -> {a['sugerencia']}" if a["sugerencia"] else ""))
    for r in res["recordatorios"]:
        print(f"  Recordatorio: {r}")
    if publicar:
        prediccion["revision_boleto"] = res
        guardar_json(PREDICCION, prediccion)
        jornada = prediccion.get("jornada")
        espejo = PREDICCIONES_DIR / f"jornada_{jornada}.json"
        if isinstance(jornada, int) and espejo.exists():
            datos = cargar_json(espejo, {}) or {}
            if datos.get("jornada") == jornada:
                datos["revision_boleto"] = res
                guardar_json(espejo, datos)


if __name__ == "__main__":
    main()
