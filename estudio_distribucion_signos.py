"""Estudio de la distribucion de signos (1/X/2) por jornada quinielistica
(peticion de Marc, 01/10/2026: "cuantos 1, cuantas X y cuantos 2 salen en
cada jornada... y si hay algun patron, o todo es azar puro de futbol").

Fuente: data/memoria_ia/historico_quinielas_lae.json (jornadas reales LAE
con los 14 signos oficiales y, ademas, el % de apostantes por signo).

Mide, por temporada y en global:
 - reparto de signos (cuantos 1/X/2 salen, % y media por jornada)
 - histograma del numero de X (y de 1 y 2) por jornada
 - TEST DE AZAR: la varianza real del numero de X por jornada contra la
   varianza binomial que tendria si cada partido fuera independiente
   (ratio ~1 = azar puro; >>1 = existen "jornadas de empates" correladas)
 - persistencia: P(jornada con 4+ X | la anterior tuvo 4+ X) vs base
 - sesgo del publico: % medio apostado a cada signo vs frecuencia real
   (cierra el estudio pendiente de la Regla 15: el pago de la X)

Salida: data/memoria_ia/distribucion_signos.json + resumen por pantalla.
No forma parte del pipeline (estudio bajo demanda, como el del revulsivo).
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HISTORICO = ROOT / "data" / "memoria_ia" / "historico_quinielas_lae.json"
SALIDA = ROOT / "data" / "memoria_ia" / "distribucion_signos.json"

SIGNOS = ("1", "X", "2")


def jornadas_completas(data):
    for temporada, bloque in (data.get("temporadas") or {}).items():
        for jornada in bloque.get("jornadas") or []:
            partidos = [p for p in jornada.get("partidos") or []
                        if 1 <= int(p.get("num") or 0) <= 14
                        and str(p.get("signo_oficial") or "").upper() in SIGNOS]
            if len(partidos) == 14:
                yield temporada, jornada, partidos


def analizar():
    data = json.loads(HISTORICO.read_text(encoding="utf-8"))
    por_temporada = {}
    conteos = []          # (temporada, jornada_num, n1, nX, n2)
    publico = {s: [] for s in SIGNOS}   # % apostado al signo que SALIO, por signo
    publico_medio = {s: [] for s in SIGNOS}  # % apostado a cada signo en todos los partidos

    for temporada, jornada, partidos in jornadas_completas(data):
        n = {s: 0 for s in SIGNOS}
        for p in partidos:
            real = str(p["signo_oficial"]).upper()
            n[real] += 1
            porc = {"1": p.get("porc1"), "X": p.get("porcX"), "2": p.get("porc2")}
            for s in SIGNOS:
                if isinstance(porc[s], (int, float)):
                    publico_medio[s].append(float(porc[s]))
            if isinstance(porc[real], (int, float)):
                publico[real].append(float(porc[real]))
        conteos.append((temporada, jornada.get("jornada"), n["1"], n["X"], n["2"]))
        t = por_temporada.setdefault(temporada, {s: 0 for s in SIGNOS} | {"jornadas": 0})
        for s in SIGNOS:
            t[s] += n[s]
        t["jornadas"] += 1

    total_j = len(conteos)
    total_p = total_j * 14
    tot = {s: sum(c[2 + i] for c in conteos) for i, s in enumerate(SIGNOS)}

    def stats_signo(idx, signo):
        vals = [c[2 + idx] for c in conteos]
        media = sum(vals) / total_j
        var = sum((v - media) ** 2 for v in vals) / (total_j - 1)
        p = tot[signo] / total_p
        var_binomial = 14 * p * (1 - p)
        hist = {}
        for v in vals:
            hist[str(v)] = hist.get(str(v), 0) + 1
        return {
            "media_por_jornada": round(media, 2),
            "desviacion": round(var ** 0.5, 2),
            "varianza_real": round(var, 2),
            "varianza_si_fuera_azar_independiente": round(var_binomial, 2),
            "ratio_dispersion": round(var / var_binomial, 2),
            "histograma": dict(sorted(hist.items(), key=lambda kv: int(kv[0]))),
            "maximo": max(vals),
            "minimo": min(vals),
        }

    # persistencia de jornadas carga de X (4 o mas), en orden cronologico de archivo
    xs = [c[3] for c in conteos]
    altas = [v >= 4 for v in xs]
    seguidas = sum(1 for i in range(1, len(altas)) if altas[i] and altas[i - 1])
    tras_alta = sum(1 for i in range(1, len(altas)) if altas[i - 1])
    base_alta = sum(altas) / len(altas)

    salida = {
        "version": 1,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": "Distribucion real de 1/X/2 por jornada LAE y test de azar vs patron.",
        "jornadas_analizadas": total_j,
        "reparto_global": {s: {"total": tot[s], "porcentaje": round(100 * tot[s] / total_p, 1)} for s in SIGNOS},
        "por_temporada": {
            temp: {s: {"total": v[s], "media_jornada": round(v[s] / v["jornadas"], 2)} for s in SIGNOS}
            | {"jornadas": v["jornadas"]}
            for temp, v in por_temporada.items()
        },
        "por_signo": {s: stats_signo(i, s) for i, s in enumerate(SIGNOS)},
        "persistencia_X": {
            "base_pct_jornadas_con_4X_o_mas": round(100 * base_alta, 1),
            "pct_tras_una_jornada_de_4X_o_mas": round(100 * seguidas / tras_alta, 1) if tras_alta else None,
        },
        "publico_vs_realidad": {
            s: {
                "pct_medio_apostado": round(sum(publico_medio[s]) / len(publico_medio[s]), 1),
                "frecuencia_real_pct": round(100 * tot[s] / total_p, 1),
                "sesgo_puntos": round(sum(publico_medio[s]) / len(publico_medio[s]) - 100 * tot[s] / total_p, 1),
            }
            for s in SIGNOS if publico_medio[s]
        },
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return salida


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    s = analizar()
    print(f"Jornadas completas analizadas: {s['jornadas_analizadas']}")
    print("Reparto global:", {k: v["porcentaje"] for k, v in s["reparto_global"].items()})
    for temp, v in s["por_temporada"].items():
        print(f"  {temp}: jornadas {v['jornadas']} | medias 1={v['1']['media_jornada']} X={v['X']['media_jornada']} 2={v['2']['media_jornada']}")
    for signo in SIGNOS:
        st = s["por_signo"][signo]
        print(f"[{signo}] media {st['media_por_jornada']}/jornada ± {st['desviacion']} | dispersion vs azar {st['ratio_dispersion']} | rango {st['minimo']}-{st['maximo']}")
        print(f"     histograma: {st['histograma']}")
    print("Persistencia X:", s["persistencia_X"])
    print("Publico vs realidad:", s["publico_vs_realidad"])
    print("Guardado en", SALIDA)
