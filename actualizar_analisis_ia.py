import json
import re
from pathlib import Path

DATA_DIR = Path("data")
OUT = DATA_DIR / "analisis_ia.json"

CALENDARIOS = {
    "primera": DATA_DIR / "calendario_primera.json",
    "segunda": DATA_DIR / "calendario_segunda.json",
}

HISTORICO_QUINIELAS = Path("historico_quinielas.csv")


def cargar_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_resultado(resultado):
    resultado = str(resultado or "").strip().replace(" ", "")
    m = re.match(r"^(\d+)-(\d+)$", resultado)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def asegurar_equipo(stats, equipo):
    if equipo not in stats:
        stats[equipo] = {
            "equipo": equipo,
            "pj": 0,
            "g": 0,
            "e": 0,
            "p": 0,
            "gf": 0,
            "gc": 0,
            "dg": 0,
            "pts": 0,
            "local": {"pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0, "pts": 0},
            "visitante": {"pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0, "pts": 0},
            "ultimos": [],
            "rachas": {},
        }
    return stats[equipo]


def aplicar_partido(stats, local, visitante, gl, gv):
    el = asegurar_equipo(stats, local)
    ev = asegurar_equipo(stats, visitante)

    el["pj"] += 1
    ev["pj"] += 1
    el["gf"] += gl
    el["gc"] += gv
    ev["gf"] += gv
    ev["gc"] += gl

    el["local"]["pj"] += 1
    ev["visitante"]["pj"] += 1
    el["local"]["gf"] += gl
    el["local"]["gc"] += gv
    ev["visitante"]["gf"] += gv
    ev["visitante"]["gc"] += gl

    if gl > gv:
        res_l, res_v = "G", "P"
        el["g"] += 1
        ev["p"] += 1
        el["pts"] += 3
        el["local"]["g"] += 1
        ev["visitante"]["p"] += 1
        el["local"]["pts"] += 3
    elif gl < gv:
        res_l, res_v = "P", "G"
        ev["g"] += 1
        el["p"] += 1
        ev["pts"] += 3
        ev["visitante"]["g"] += 1
        el["local"]["p"] += 1
        ev["visitante"]["pts"] += 3
    else:
        res_l, res_v = "E", "E"
        el["e"] += 1
        ev["e"] += 1
        el["pts"] += 1
        ev["pts"] += 1
        el["local"]["e"] += 1
        ev["visitante"]["e"] += 1
        el["local"]["pts"] += 1
        ev["visitante"]["pts"] += 1

    el["ultimos"].append({"r": res_l, "gf": gl, "gc": gv, "condicion": "local"})
    ev["ultimos"].append({"r": res_v, "gf": gv, "gc": gl, "condicion": "visitante"})


def calcular_rachas(stats):
    for e in stats.values():
        e["dg"] = e["gf"] - e["gc"]
        ultimos = e["ultimos"]
        ultimos5 = ultimos[-5:]
        ultimos10 = ultimos[-10:]

        e["forma_5"] = {
            "pj": len(ultimos5),
            "pts": sum(3 if x["r"] == "G" else 1 if x["r"] == "E" else 0 for x in ultimos5),
            "gf": sum(x["gf"] for x in ultimos5),
            "gc": sum(x["gc"] for x in ultimos5),
            "resultados": [x["r"] for x in ultimos5],
        }

        e["forma_10"] = {
            "pj": len(ultimos10),
            "pts": sum(3 if x["r"] == "G" else 1 if x["r"] == "E" else 0 for x in ultimos10),
            "gf": sum(x["gf"] for x in ultimos10),
            "gc": sum(x["gc"] for x in ultimos10),
            "resultados": [x["r"] for x in ultimos10],
        }

        def contar_racha(valor):
            total = 0
            for x in reversed(ultimos):
                if x["r"] == valor:
                    total += 1
                else:
                    break
            return total

        sin_ganar = 0
        sin_perder = 0
        for x in reversed(ultimos):
            if x["r"] != "G":
                sin_ganar += 1
            else:
                break
        for x in reversed(ultimos):
            if x["r"] != "P":
                sin_perder += 1
            else:
                break

        e["rachas"] = {
            "victorias": contar_racha("G"),
            "empates": contar_racha("E"),
            "derrotas": contar_racha("P"),
            "sin_ganar": sin_ganar,
            "sin_perder": sin_perder,
        }


def puntuacion_equipo(e, condicion):
    pj = max(e.get("pj", 0), 1)
    pts_pp = e.get("pts", 0) / pj
    dg_pp = e.get("dg", 0) / pj
    forma = e.get("forma_5", {})
    forma_pts = forma.get("pts", 0) / max(forma.get("pj", 1), 1)

    casa_fuera = e.get(condicion, {})
    cf_pts = casa_fuera.get("pts", 0) / max(casa_fuera.get("pj", 1), 1)
    cf_gf = casa_fuera.get("gf", 0) / max(casa_fuera.get("pj", 1), 1)
    cf_gc = casa_fuera.get("gc", 0) / max(casa_fuera.get("pj", 1), 1)

    return pts_pp * 35 + forma_pts * 30 + dg_pp * 15 + cf_pts * 15 + (cf_gf - cf_gc) * 5


def normalizar_probabilidades(p1, px, p2):
    total = p1 + px + p2
    if total <= 0:
        return {"1": 33.3, "X": 33.3, "2": 33.3}
    return {"1": round(p1 / total * 100, 1), "X": round(px / total * 100, 1), "2": round(p2 / total * 100, 1)}


def analizar_partido(stats, local, visitante, jornada):
    el = stats.get(local)
    ev = stats.get(visitante)

    if not el or not ev:
        return {
            "jornada": jornada,
            "local": local,
            "visitante": visitante,
            "probabilidades": {"1": 33.3, "X": 33.3, "2": 33.3},
            "recomendacion": "1X2",
            "confianza": "Baja",
            "riesgo_sorpresa": "Alto",
            "explicacion": "Faltan datos suficientes para analizar el partido.",
        }

    score_l = puntuacion_equipo(el, "local")
    score_v = puntuacion_equipo(ev, "visitante")
    diferencia = score_l - score_v

    p1 = 36 + max(min(diferencia, 25), -25)
    p2 = 29 + max(min(-diferencia, 25), -25)
    px = 100 - p1 - p2

    empates_l = el.get("e", 0) / max(el.get("pj", 1), 1)
    empates_v = ev.get("e", 0) / max(ev.get("pj", 1), 1)
    if abs(diferencia) < 8:
        px += 8
    if empates_l > 0.32 or empates_v > 0.32:
        px += 6

    probs = normalizar_probabilidades(p1, px, p2)
    orden = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    signo_top, prob_top = orden[0]
    signo_2, _ = orden[1]

    if prob_top >= 50:
        recomendacion = signo_top
        confianza = "Alta"
    elif prob_top >= 42:
        recomendacion = signo_top + signo_2
        confianza = "Media"
    else:
        recomendacion = "1X2"
        confianza = "Baja"

    riesgo = "Bajo"
    if prob_top < 43:
        riesgo = "Alto"
    elif abs(probs["1"] - probs["2"]) < 8 or probs["X"] > 31:
        riesgo = "Medio"

    explicaciones = []
    if el["forma_5"]["pts"] > ev["forma_5"]["pts"]:
        explicaciones.append(f"{local} llega con mejor forma reciente.")
    elif el["forma_5"]["pts"] < ev["forma_5"]["pts"]:
        explicaciones.append(f"{visitante} llega con mejor forma reciente.")

    if el["local"]["pts"] / max(el["local"]["pj"], 1) > 1.8:
        explicaciones.append(f"{local} es fuerte en casa.")
    if ev["visitante"]["pts"] / max(ev["visitante"]["pj"], 1) > 1.6:
        explicaciones.append(f"{visitante} compite bien fuera.")
    if probs["X"] > 30:
        explicaciones.append("El empate tiene peso estadístico.")
    if riesgo != "Bajo":
        explicaciones.append("Partido candidato a doble o triple.")

    return {
        "jornada": jornada,
        "local": local,
        "visitante": visitante,
        "probabilidades": probs,
        "recomendacion": recomendacion,
        "confianza": confianza,
        "riesgo_sorpresa": riesgo,
        "score_local": round(score_l, 2),
        "score_visitante": round(score_v, 2),
        "explicacion": " ".join(explicaciones) or "Partido sin ventaja estadística clara.",
    }


def construir_stats_y_proximos(calendario):
    stats = {}
    proximos = []

    for jornada in calendario.get("jornadas", []):
        jnum = jornada.get("jornada")
        for p in jornada.get("partidos", []):
            local = p.get("local")
            visitante = p.get("visitante")
            resultado = parse_resultado(p.get("resultado"))

            if not local or not visitante:
                continue

            if resultado:
                aplicar_partido(stats, local, visitante, resultado[0], resultado[1])
            else:
                proximos.append({"jornada": jnum, "local": local, "visitante": visitante, "fecha": p.get("fecha", ""), "hora": p.get("hora", "")})

    calcular_rachas(stats)
    return stats, proximos


def analizar_historico_quinielas():
    if not HISTORICO_QUINIELAS.exists():
        return {"disponible": False}

    texto = HISTORICO_QUINIELAS.read_text(encoding="utf-8", errors="ignore")
    signos = re.findall(r"[12X]", texto)

    if not signos:
        return {"disponible": False}

    total = len(signos)
    return {
        "disponible": True,
        "total_signos_detectados": total,
        "porcentaje_1": round(signos.count("1") / total * 100, 1),
        "porcentaje_X": round(signos.count("X") / total * 100, 1),
        "porcentaje_2": round(signos.count("2") / total * 100, 1),
    }


def main():
    salida = {
        "version": "1.0",
        "descripcion": "Analisis IA local basado en calendarios, resultados, casa/fuera, rachas, goles y patrones de quiniela.",
        "ligas": {},
        "historico_quinielas": analizar_historico_quinielas(),
    }

    for liga, path in CALENDARIOS.items():
        calendario = cargar_json(path)
        stats, proximos = construir_stats_y_proximos(calendario)

        analisis_proximos = []
        for p in proximos[:30]:
            analisis = analizar_partido(stats, p["local"], p["visitante"], p["jornada"])
            analisis["fecha"] = p.get("fecha", "")
            analisis["hora"] = p.get("hora", "")
            analisis_proximos.append(analisis)

        equipos_ordenados = sorted(stats.values(), key=lambda e: (e["pts"], e["dg"], e["gf"]), reverse=True)

        salida["ligas"][liga] = {
            "equipos": equipos_ordenados,
            "proximos_partidos": analisis_proximos,
            "resumen": {
                "equipos_analizados": len(equipos_ordenados),
                "proximos_partidos_analizados": len(analisis_proximos),
            },
        }

    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Analisis IA generado: {OUT}")


if __name__ == "__main__":
    main()
