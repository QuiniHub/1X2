import json
import re
from pathlib import Path
from collections import Counter

DATA = Path("data")
OUT_DIR = DATA / "quinielas_ia"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ANALISIS_IA = DATA / "analisis_ia.json"
CLASIFICACIONES = Path("clasificaciones.json")
HISTORICO_QUINIELAS = Path("historico_quinielas.csv")
JORNADAS_DIR = DATA / "jornadas"

PRECIO_APUESTA = 0.75
IMPORTE_MINIMO = 1.50


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def normalizar(txt):
    txt = str(txt or "").lower()
    for a, b in {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n",
        "fc": "", "cf": "", "cd": "", "sd": "", "ud": "", "rcd": "", "rc": "",
        "real": "", "club": "", "de": "", "la": "", "el": "",
    }.items():
        txt = txt.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", txt).strip()


def leer_historico_quinielas():
    if not HISTORICO_QUINIELAS.exists():
        return {
            "disponible": False,
            "frecuencias": {"1": 0.45, "X": 0.28, "2": 0.27},
            "media_unos": 7,
            "media_equis": 4,
            "media_doses": 4,
        }

    texto = HISTORICO_QUINIELAS.read_text(encoding="utf-8", errors="ignore").upper()
    signos = [s for s in re.findall(r"[12X]", texto) if s in ("1", "X", "2")]

    if not signos:
        return {
            "disponible": False,
            "frecuencias": {"1": 0.45, "X": 0.28, "2": 0.27},
            "media_unos": 7,
            "media_equis": 4,
            "media_doses": 4,
        }

    c = Counter(signos)
    total = sum(c.values())
    return {
        "disponible": True,
        "total_signos": total,
        "frecuencias": {
            "1": c["1"] / total,
            "X": c["X"] / total,
            "2": c["2"] / total,
        },
        "media_unos": round(c["1"] / total * 14),
        "media_equis": round(c["X"] / total * 14),
        "media_doses": round(c["2"] / total * 14),
    }


def normalizar_probs(p):
    p = {k: max(float(p.get(k, 1)), 1.0) for k in ("1", "X", "2")}
    total = p["1"] + p["X"] + p["2"]
    return {k: round(v / total * 100, 1) for k, v in p.items()}


def buscar_analisis_partido(analisis, local, visitante):
    nl = normalizar(local)
    nv = normalizar(visitante)

    candidatos = []
    for liga in ("primera", "segunda"):
        candidatos += analisis.get("ligas", {}).get(liga, {}).get("proximos_partidos", [])

    for a in candidatos:
        al = normalizar(a.get("local"))
        av = normalizar(a.get("visitante"))
        if (al in nl or nl in al) and (av in nv or nv in av):
            return a
    return None


def mapa_clasificaciones(clasificaciones):
    mapa = {}
    for liga, equipos in clasificaciones.items():
        for e in equipos:
            nombre = e.get("equipo") or e.get("nombre") or e.get("team") or ""
            mapa[normalizar(nombre)] = e | {"liga": liga}
    return mapa


def buscar_clasificacion(mapa, nombre):
    n = normalizar(nombre)
    for k, e in mapa.items():
        if k in n or n in k:
            return e
    return None


def puntos(e):
    if not e:
        return 0.0
    return float(e.get("puntos") or e.get("pts") or e.get("points") or 0)


def posicion(e):
    if not e:
        return 99
    return int(e.get("posicion") or e.get("pos") or 99)


def ajustar_por_clasificacion(probs, local_cls, visitante_cls):
    p = probs.copy()
    pos_l = posicion(local_cls)
    pos_v = posicion(visitante_cls)
    pts_l = puntos(local_cls)
    pts_v = puntos(visitante_cls)

    ajuste = max(min((pos_v - pos_l) * 0.8 + (pts_l - pts_v) * 0.25, 12), -12)
    p["1"] += ajuste
    p["2"] -= ajuste

    if abs(pos_l - pos_v) <= 3:
        p["X"] += 3

    return normalizar_probs(p)


def ajustar_por_historico(probs, historico):
    f = historico["frecuencias"]
    p = probs.copy()
    p["1"] = p["1"] * 0.92 + f["1"] * 100 * 0.08
    p["X"] = p["X"] * 0.92 + f["X"] * 100 * 0.08
    p["2"] = p["2"] * 0.92 + f["2"] * 100 * 0.08
    return normalizar_probs(p)


def incertidumbre(probs, analisis):
    orden = sorted(probs.values(), reverse=True)
    diferencia = orden[0] - orden[1]
    riesgo = str((analisis or {}).get("riesgo_sorpresa", "Medio")).lower()
    bonus = 12 if "alto" in riesgo else 6 if "medio" in riesgo else 0
    return round((100 - diferencia) + probs["X"] * 0.35 + bonus, 2)


def signo_top(probs):
    return sorted(probs.items(), key=lambda x: x[1], reverse=True)[0][0]


def doble_top(probs):
    orden = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:2]
    signos = {orden[0][0], orden[1][0]}
    return "".join(s for s in ["1", "X", "2"] if s in signos)


def cargar_partidos_jornada(jornada):
    path = JORNADAS_DIR / f"jornada_{jornada}.json"
    data = cargar_json(path, {})
    partidos = data.get("partidos", [])

    salida = []
    for i, p in enumerate(partidos, 1):
        salida.append({
            "num": int(p.get("num") or p.get("numero") or i),
            "local": p.get("local") or p.get("equipo_local") or "",
            "visitante": p.get("visitante") or p.get("equipo_visitante") or "",
        })
    return salida


def aplicar_dobles_triples(partidos, num_dobles, num_triples):
    partidos = [p.copy() for p in partidos]

    por_riesgo = sorted(partidos, key=lambda p: p["incertidumbre"], reverse=True)
    triples = {p["num"] for p in por_riesgo[:num_triples]}

    restantes = [p for p in por_riesgo if p["num"] not in triples]
    dobles = {p["num"] for p in restantes[:num_dobles]}

    for p in partidos:
        if p["num"] in triples:
            p["signo_final"] = "1X2"
        elif p["num"] in dobles:
            p["signo_final"] = doble_top(p["probabilidades"])
        else:
            p["signo_final"] = signo_top(p["probabilidades"])

    return sorted(partidos, key=lambda p: p["num"])


def coste(num_dobles, num_triples):
    apuestas = (2 ** num_dobles) * (3 ** num_triples)
    return apuestas, round(max(apuestas * PRECIO_APUESTA, IMPORTE_MINIMO), 2)


def generar_quiniela(jornada, num_dobles=0, num_triples=0):
    analisis = cargar_json(ANALISIS_IA, {})
    clasificaciones = cargar_json(CLASIFICACIONES, {})
    historico = leer_historico_quinielas()
    clasif = mapa_clasificaciones(clasificaciones)

    partidos_base = cargar_partidos_jornada(jornada)
    if not partidos_base:
        raise SystemExit(f"No encuentro data/jornadas/jornada_{jornada}.json o no tiene partidos.")

    evaluados = []

    for p in partidos_base:
        a = buscar_analisis_partido(analisis, p["local"], p["visitante"])
        if a:
            probs = a.get("probabilidades", {"1": 33.3, "X": 33.3, "2": 33.3})
            explicacion = a.get("explicacion", "")
            confianza = a.get("confianza", "Media")
            riesgo = a.get("riesgo_sorpresa", "Medio")
        else:
            probs = {"1": 37, "X": 31, "2": 32}
            explicacion = "Sin coincidencia exacta en analisis_ia; ajustado con clasificacion e historico."
            confianza = "Baja"
            riesgo = "Alto"

        local_cls = buscar_clasificacion(clasif, p["local"])
        visitante_cls = buscar_clasificacion(clasif, p["visitante"])

        probs = ajustar_por_clasificacion(probs, local_cls, visitante_cls)
        probs = ajustar_por_historico(probs, historico)

        evaluados.append({
            "num": p["num"],
            "local": p["local"],
            "visitante": p["visitante"],
            "probabilidades": probs,
            "confianza": confianza,
            "riesgo_sorpresa": riesgo,
            "incertidumbre": incertidumbre(probs, a),
            "clasificacion_local": {"posicion": posicion(local_cls), "puntos": puntos(local_cls)},
            "clasificacion_visitante": {"posicion": posicion(visitante_cls), "puntos": puntos(visitante_cls)},
            "explicacion": explicacion,
        })

    boleto = aplicar_dobles_triples(evaluados, num_dobles, num_triples)
    apuestas, importe = coste(num_dobles, num_triples)

    salida = {
        "jornada": jornada,
        "dobles": num_dobles,
        "triples": num_triples,
        "apuestas": apuestas,
        "importe": importe,
        "motor": "QuiniHub IA v2",
        "usa": [
            "data/analisis_ia.json",
            "clasificaciones.json",
            "historico_quinielas.csv",
            f"data/jornadas/jornada_{jornada}.json",
        ],
        "historico_quinielas": historico,
        "partidos": boleto,
        "resumen": {
            "fijos": sum(1 for p in boleto if len(p["signo_final"]) == 1),
            "dobles": sum(1 for p in boleto if len(p["signo_final"]) == 2),
            "triples": sum(1 for p in boleto if len(p["signo_final"]) == 3),
        },
    }

    out = OUT_DIR / f"jornada_{jornada}_d{num_dobles}_t{num_triples}.json"
    out.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT_DIR / "ultima.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Quiniela IA generada: {out}")
    print(f"Apuestas: {apuestas} | Importe: {importe} EUR")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--jornada", type=int, required=True)
    parser.add_argument("--dobles", type=int, default=0)
    parser.add_argument("--triples", type=int, default=0)
    args = parser.parse_args()
    generar_quiniela(args.jornada, args.dobles, args.triples)


if __name__ == "__main__":
    main()
