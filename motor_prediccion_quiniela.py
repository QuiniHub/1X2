import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia" / "aprendizaje_global.json"
JORNADAS = DATA / "jornadas"
PREDICCIONES = DATA / "predicciones"
JUGADAS = DATA / "quinielas_jugadas"

PRECIO_APUESTA = 0.75
IMPORTE_MINIMO = 1.50
PRECIO_ELIGE8 = 0.50


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|sad|club|real|de|del|la|el)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def detectar_jornada_activa():
    candidatas = []
    for path in JORNADAS.glob("jornada_*.json"):
        data = cargar_json(path, {})
        numero = data.get("jornada")
        if not isinstance(numero, int):
            m = re.search(r"(\d+)", path.stem)
            numero = int(m.group(1)) if m else 0
        pendientes = sum(1 for p in data.get("partidos", []) if str(p.get("signo_oficial", "")).lower() == "pendiente")
        if pendientes:
            candidatas.append(numero)
    if candidatas:
        return max(candidatas)
    jornadas = [int(re.search(r"(\d+)", p.stem).group(1)) for p in JORNADAS.glob("jornada_*.json")]
    return max(jornadas) if jornadas else 61


def equipos_memoria(memoria):
    equipos = []
    for liga in ("primera", "segunda"):
        equipos.extend(memoria.get("ligas", {}).get(liga, {}).get("equipos", []))
    return equipos


def buscar_equipo(memoria, nombre):
    n = normalizar(nombre)
    mejor = None
    mejor_score = 0
    for equipo in equipos_memoria(memoria):
        e = normalizar(equipo.get("equipo", ""))
        if not e:
            continue
        score = 0
        if e == n:
            score = 100
        elif e in n or n in e:
            score = 80
        else:
            comunes = set(e.split()) & set(n.split())
            score = len(comunes) * 20
        if score > mejor_score:
            mejor = equipo
            mejor_score = score
    return mejor if mejor_score >= 20 else None


def fuerza(equipo, condicion):
    if not equipo:
        return 0.0
    pj = max(float(equipo.get("pj") or 0), 1.0)
    cond = equipo.get(condicion, {})
    cond_pj = max(float(cond.get("pj") or 0), 1.0)
    tendencias = equipo.get("tendencias", {})
    ppg = float(equipo.get("pts") or 0) / pj
    dg = float(equipo.get("dg") or 0) / pj
    cond_ppg = float(cond.get("pts") or 0) / cond_pj
    forma_5 = float(tendencias.get("forma_5_pts") or 0) / 5.0
    empates = float(tendencias.get("empates_pct") or 0)
    return ppg * 34 + dg * 12 + cond_ppg * 22 + forma_5 * 20 + empates * 0.08


def normalizar_probs(probs):
    probs = {k: max(float(probs.get(k, 1)), 1.0) for k in ("1", "X", "2")}
    total = sum(probs.values()) or 1
    return {k: round(v / total * 100, 1) for k, v in probs.items()}


def aplicar_patron_posicion(probs, memoria, posicion):
    perfil = memoria.get("quiniela", {}).get("historico_csv", {}).get("perfil_por_posicion", {}).get(str(posicion), {})
    if not perfil:
        return probs
    return normalizar_probs({
        "1": probs["1"] * 0.88 + float(perfil.get("1", 33.3)) * 0.12,
        "X": probs["X"] * 0.88 + float(perfil.get("X", 33.3)) * 0.12,
        "2": probs["2"] * 0.88 + float(perfil.get("2", 33.3)) * 0.12,
    })


def calcular_probabilidades(memoria, partido):
    local = buscar_equipo(memoria, partido.get("local", ""))
    visitante = buscar_equipo(memoria, partido.get("visitante", ""))
    fl = fuerza(local, "local")
    fv = fuerza(visitante, "visitante")
    diff = fl - fv

    probs = {
        "1": 37 + max(min(diff * 0.52, 24), -20),
        "X": 29 + max(0, 10 - abs(diff) * 0.20),
        "2": 34 + max(min(-diff * 0.52, 24), -20),
    }

    if local and visitante:
        emp_l = float(local.get("tendencias", {}).get("empates_pct") or 0)
        emp_v = float(visitante.get("tendencias", {}).get("empates_pct") or 0)
        if (emp_l + emp_v) / 2 >= 28:
            probs["X"] += 5
        if float(local.get("gc") or 0) / max(float(local.get("pj") or 1), 1) > 1.35:
            probs["2"] += 3
        if float(visitante.get("gc") or 0) / max(float(visitante.get("pj") or 1), 1) > 1.35:
            probs["1"] += 3

    probs = normalizar_probs(probs)
    probs = aplicar_patron_posicion(probs, memoria, partido.get("num"))
    return probs, local, visitante, round(diff, 2)


def signo_top(probs):
    return sorted(probs.items(), key=lambda x: x[1], reverse=True)[0][0]


def doble_top(probs):
    top2 = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:2]
    signos = {s for s, _ in top2}
    return "".join(s for s in ("1", "X", "2") if s in signos)


def incertidumbre(probs, local, visitante, diff):
    orden = sorted(probs.values(), reverse=True)
    margen = orden[0] - orden[1]
    puntos = 100 - margen + probs["X"] * 0.35
    if abs(diff) < 8:
        puntos += 8
    if local and local.get("racha_actual", {}).get("sin_ganar", 0) >= 3:
        puntos += 4
    if visitante and visitante.get("racha_actual", {}).get("sin_perder", 0) >= 3:
        puntos += 4
    return round(puntos, 2)


def explicar(partido, probs, signo, local, visitante, diff, tipo):
    razones = []
    razones.append(f"Probabilidades IA: 1={probs['1']}%, X={probs['X']}%, 2={probs['2']}%.")
    if local:
        t = local.get("tendencias", {})
        razones.append(
            f"{partido.get('local')} llega con {local.get('pts', 0)} puntos, "
            f"{t.get('forma_5_pts', 0)} puntos en los ultimos 5 y "
            f"{t.get('goles_favor_por_partido', 0)} goles a favor por partido."
        )
    if visitante:
        t = visitante.get("tendencias", {})
        razones.append(
            f"{partido.get('visitante')} llega con {visitante.get('pts', 0)} puntos, "
            f"{t.get('forma_5_pts', 0)} puntos en los ultimos 5 y "
            f"{t.get('goles_contra_por_partido', 0)} goles encajados por partido."
        )
    if abs(diff) < 8:
        razones.append("El partido queda equilibrado por fuerza reciente, asi que sube el riesgo de empate o sorpresa.")
    if tipo == "TRIPLE":
        razones.append("Se protege con triple porque es de los partidos con mas incertidumbre del boleto.")
    elif tipo == "DOBLE":
        razones.append("Se protege con doble porque el segundo signo tiene peso suficiente para cubrir una desviacion razonable.")
    else:
        razones.append("Se deja como fijo porque el signo principal tiene mejor relacion entre probabilidad y riesgo.")
    razones.append(f"Decision final: {signo}.")
    return " ".join(razones)


def coste(dobles, triples, elige8):
    apuestas = 2 ** dobles * 3 ** triples
    importe_quiniela = max(apuestas * PRECIO_APUESTA, IMPORTE_MINIMO)
    importe_elige8 = PRECIO_ELIGE8 if elige8 else 0.0
    return {
        "apuestas": apuestas,
        "importe_quiniela": round(importe_quiniela, 2),
        "importe_elige8": round(importe_elige8, 2),
        "importe_total": round(importe_quiniela + importe_elige8, 2),
    }


def predecir(jornada=None, dobles=0, triples=0, elige8=False, validar=False):
    memoria = cargar_json(MEMORIA, {})
    jornada = jornada or detectar_jornada_activa()
    data = cargar_json(JORNADAS / f"jornada_{jornada}.json", {})
    partidos_base = [p for p in data.get("partidos", []) if int(p.get("num", 0)) <= 14]
    if not partidos_base:
        raise SystemExit(f"No hay partidos para jornada {jornada}")

    evaluados = []
    for partido in partidos_base:
        probs, local, visitante, diff = calcular_probabilidades(memoria, partido)
        evaluados.append({
            **partido,
            "probabilidades": probs,
            "signo_base": signo_top(probs),
            "incertidumbre": incertidumbre(probs, local, visitante, diff),
            "_local": local,
            "_visitante": visitante,
            "_diff": diff,
        })

    por_riesgo = sorted(evaluados, key=lambda p: p["incertidumbre"], reverse=True)
    triples_set = {p["num"] for p in por_riesgo[:triples]}
    dobles_set = {p["num"] for p in por_riesgo if p["num"] not in triples_set}
    dobles_set = set(list(dobles_set)[:dobles])

    elige8_set = set()
    if elige8:
        elige8_set = {p["num"] for p in sorted(evaluados, key=lambda p: p["incertidumbre"])[:8]}

    partidos = []
    for partido in sorted(evaluados, key=lambda p: p["num"]):
        if partido["num"] in triples_set:
            signo = "1X2"
            tipo = "TRIPLE"
        elif partido["num"] in dobles_set:
            signo = doble_top(partido["probabilidades"])
            tipo = "DOBLE"
        else:
            signo = partido["signo_base"]
            tipo = "FIJO"

        partidos.append({
            "num": partido["num"],
            "local": partido.get("local"),
            "visitante": partido.get("visitante"),
            "probabilidades": partido["probabilidades"],
            "signo_base": partido["signo_base"],
            "signo_final": signo,
            "tipo": tipo,
            "incertidumbre": partido["incertidumbre"],
            "elige8": partido["num"] in elige8_set,
            "razonamiento": explicar(
                partido,
                partido["probabilidades"],
                signo,
                partido["_local"],
                partido["_visitante"],
                partido["_diff"],
                tipo,
            ),
        })

    salida = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "jornada": jornada,
        "temporada_base": memoria.get("temporada", "2025/2026"),
        "estado": "validada" if validar else "prediccion_no_validada",
        "configuracion": {
            "dobles": dobles,
            "triples": triples,
            "elige8": elige8,
        },
        "coste": coste(dobles, triples, elige8),
        "partidos": partidos,
        "pleno15": data.get("pleno15"),
        "resumen": {
            "fijos": sum(1 for p in partidos if p["tipo"] == "FIJO"),
            "dobles": sum(1 for p in partidos if p["tipo"] == "DOBLE"),
            "triples": sum(1 for p in partidos if p["tipo"] == "TRIPLE"),
            "elige8_seleccionados": sum(1 for p in partidos if p["elige8"]),
        },
    }

    destino = (JUGADAS if validar else PREDICCIONES) / f"jornada_{jornada}.json"
    guardar_json(destino, salida)
    if validar:
        guardar_json(JUGADAS / "ultima_validada.json", salida)
    else:
        guardar_json(PREDICCIONES / "ultima_prediccion.json", salida)
    print(destino)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jornada", type=int, default=None)
    parser.add_argument("--dobles", type=int, default=0)
    parser.add_argument("--triples", type=int, default=0)
    parser.add_argument("--elige8", action="store_true")
    parser.add_argument("--validar", action="store_true")
    args = parser.parse_args()
    predecir(args.jornada, args.dobles, args.triples, args.elige8, args.validar)


if __name__ == "__main__":
    main()
