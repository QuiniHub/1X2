import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
TEMPORADA = "2025_2026"
TEMPORADA_LABEL = "2025/2026"

CALENDARIOS = {
    "primera": DATA / "calendario_primera.json",
    "segunda": DATA / "calendario_segunda.json",
}

JORNADAS_QUINIELA = DATA / "jornadas"
QUINIELAS_JUGADAS = DATA / "quinielas_jugadas.json"
HISTORICO_QUINIELAS = ROOT / "historico_quinielas.csv"
OUT_TEMPORADA = DATA / "temporadas" / TEMPORADA
OUT_MEMORIA = DATA / "memoria_ia"


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def limpiar_nombre(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|sad|club|real|de|del|la|el)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def parse_resultado(resultado):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(resultado or ""))
    if not m:
        return None
    goles = int(m.group(1)), int(m.group(2))
    if max(goles) > 15:
        return None
    return goles


def signo_resultado(resultado):
    res = parse_resultado(resultado)
    if not res:
        return None
    gl, gv = res
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def equipo_base(nombre):
    return {
        "equipo": nombre,
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
        "racha_actual": {},
        "tendencias": {},
    }


def asegurar(stats, nombre):
    key = limpiar_nombre(nombre)
    if key not in stats:
        stats[key] = equipo_base(nombre)
    return stats[key]


def puntos_por_signo(signo):
    return 3 if signo == "G" else 1 if signo == "E" else 0


def fuerza_previa(equipo, condicion):
    pj = max(equipo["pj"], 1)
    ultimos = equipo["ultimos"][-5:]
    forma = sum(puntos_por_signo(x["r"]) for x in ultimos) / max(len(ultimos), 1)
    condicion_stats = equipo[condicion]
    condicion_pj = max(condicion_stats["pj"], 1)
    ppg = equipo["pts"] / pj
    dg_pp = (equipo["gf"] - equipo["gc"]) / pj
    cond_ppg = condicion_stats["pts"] / condicion_pj
    cond_dg = (condicion_stats["gf"] - condicion_stats["gc"]) / condicion_pj
    return round(ppg * 34 + forma * 28 + dg_pp * 12 + cond_ppg * 18 + cond_dg * 8, 4)


def signo_esperado(local, visitante):
    fl = fuerza_previa(local, "local")
    fv = fuerza_previa(visitante, "visitante")
    diff = fl - fv
    if diff > 8:
        return "1", round(diff, 2)
    if diff < -8:
        return "2", round(abs(diff), 2)
    return "X", round(abs(diff), 2)


def aplicar_resultado(stats, local_nombre, visitante_nombre, resultado):
    local = asegurar(stats, local_nombre)
    visitante = asegurar(stats, visitante_nombre)
    gl, gv = parse_resultado(resultado)

    local["pj"] += 1
    visitante["pj"] += 1
    local["gf"] += gl
    local["gc"] += gv
    visitante["gf"] += gv
    visitante["gc"] += gl

    local["local"]["pj"] += 1
    visitante["visitante"]["pj"] += 1
    local["local"]["gf"] += gl
    local["local"]["gc"] += gv
    visitante["visitante"]["gf"] += gv
    visitante["visitante"]["gc"] += gl

    if gl > gv:
        rl, rv = "G", "P"
        local["g"] += 1
        visitante["p"] += 1
        local["pts"] += 3
        local["local"]["g"] += 1
        visitante["visitante"]["p"] += 1
        local["local"]["pts"] += 3
    elif gl < gv:
        rl, rv = "P", "G"
        local["p"] += 1
        visitante["g"] += 1
        visitante["pts"] += 3
        local["local"]["p"] += 1
        visitante["visitante"]["g"] += 1
        visitante["visitante"]["pts"] += 3
    else:
        rl = rv = "E"
        local["e"] += 1
        visitante["e"] += 1
        local["pts"] += 1
        visitante["pts"] += 1
        local["local"]["e"] += 1
        visitante["visitante"]["e"] += 1
        local["local"]["pts"] += 1
        visitante["visitante"]["pts"] += 1

    local["ultimos"].append({"r": rl, "gf": gl, "gc": gv, "condicion": "local"})
    visitante["ultimos"].append({"r": rv, "gf": gv, "gc": gl, "condicion": "visitante"})


def completar_equipo(equipo):
    equipo["dg"] = equipo["gf"] - equipo["gc"]
    ultimos = equipo["ultimos"]

    def contar_racha(valor):
        total = 0
        for item in reversed(ultimos):
            if item["r"] == valor:
                total += 1
            else:
                break
        return total

    sin_ganar = 0
    sin_perder = 0
    for item in reversed(ultimos):
        if item["r"] != "G":
            sin_ganar += 1
        else:
            break
    for item in reversed(ultimos):
        if item["r"] != "P":
            sin_perder += 1
        else:
            break

    forma_5 = ultimos[-5:]
    forma_10 = ultimos[-10:]
    equipo["racha_actual"] = {
        "victorias": contar_racha("G"),
        "empates": contar_racha("E"),
        "derrotas": contar_racha("P"),
        "sin_ganar": sin_ganar,
        "sin_perder": sin_perder,
    }
    equipo["tendencias"] = {
        "puntos_por_partido": round(equipo["pts"] / max(equipo["pj"], 1), 3),
        "goles_favor_por_partido": round(equipo["gf"] / max(equipo["pj"], 1), 3),
        "goles_contra_por_partido": round(equipo["gc"] / max(equipo["pj"], 1), 3),
        "empates_pct": round(equipo["e"] / max(equipo["pj"], 1) * 100, 2),
        "forma_5_pts": sum(puntos_por_signo(x["r"]) for x in forma_5),
        "forma_10_pts": sum(puntos_por_signo(x["r"]) for x in forma_10),
    }
    return equipo


def analizar_liga(nombre_liga, path):
    data = cargar_json(path, {})
    stats = {}
    signos = Counter()
    sorpresas = []
    partidos_jugados = 0
    partidos_pendientes = 0

    for jornada in data.get("jornadas", []):
        for partido in jornada.get("partidos", []):
            resultado = partido.get("resultado")
            signo = signo_resultado(resultado)
            local_nombre = partido.get("local", "")
            visitante_nombre = partido.get("visitante", "")

            if not signo:
                partidos_pendientes += 1
                continue

            local_pre = asegurar(stats, local_nombre)
            visitante_pre = asegurar(stats, visitante_nombre)
            esperado, margen = signo_esperado(local_pre, visitante_pre)
            if esperado != signo and margen >= 10 and local_pre["pj"] >= 4 and visitante_pre["pj"] >= 4:
                sorpresas.append({
                    "jornada_liga": jornada.get("jornada"),
                    "local": local_nombre,
                    "visitante": visitante_nombre,
                    "resultado": resultado,
                    "signo_real": signo,
                    "signo_esperado": esperado,
                    "margen_previo": margen,
                    "lectura": "Resultado contrario al modelo previo de fuerza, forma y casa/fuera.",
                })

            signos[signo] += 1
            partidos_jugados += 1
            aplicar_resultado(stats, local_nombre, visitante_nombre, resultado)

    equipos = [completar_equipo(e) for e in stats.values()]
    equipos.sort(key=lambda e: (e["pts"], e["dg"], e["gf"]), reverse=True)
    for idx, equipo in enumerate(equipos, 1):
        equipo["posicion"] = idx

    total_signos = sum(signos.values()) or 1
    return {
        "competicion": nombre_liga,
        "partidos_jugados": partidos_jugados,
        "partidos_pendientes": partidos_pendientes,
        "frecuencias_signos": {k: round(signos[k] / total_signos * 100, 2) for k in ("1", "X", "2")},
        "equipos": equipos,
        "sorpresas_detectadas": sorpresas[-100:],
        "resumen_sorpresas": {
            "total": len(sorpresas),
            "ultimas": len(sorpresas[-10:]),
        },
    }


def leer_historico_quinielas_csv():
    if not HISTORICO_QUINIELAS.exists():
        return []
    with HISTORICO_QUINIELAS.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def analizar_historico_quiniela():
    filas = leer_historico_quinielas_csv()
    signos_globales = Counter()
    por_posicion = {str(i): Counter() for i in range(1, 15)}
    jornadas = []

    for fila in filas:
        bruto = (fila.get("resultado_oficial") or "").upper()
        signos = [s for s in re.findall(r"[12X]", bruto.split("|")[0]) if s in ("1", "X", "2")]
        if len(signos) >= 14:
            signos = signos[:14]
            for i, signo in enumerate(signos, 1):
                signos_globales[signo] += 1
                por_posicion[str(i)][signo] += 1
            jornadas.append({
                "jornada": fila.get("jornada"),
                "fecha": fila.get("fecha"),
                "signos": "".join(signos),
                "unos": signos.count("1"),
                "equis": signos.count("X"),
                "doses": signos.count("2"),
            })

    total = sum(signos_globales.values()) or 1
    perfiles_posicion = {}
    for pos, counter in por_posicion.items():
        subtotal = sum(counter.values()) or 1
        perfiles_posicion[pos] = {k: round(counter[k] / subtotal * 100, 2) for k in ("1", "X", "2")}

    return {
        "jornadas_analizadas": len(jornadas),
        "frecuencia_global": {k: round(signos_globales[k] / total * 100, 2) for k in ("1", "X", "2")},
        "perfil_por_posicion": perfiles_posicion,
        "ultimas_jornadas": jornadas[-20:],
        "patrones": {
            "media_unos": round(sum(j["unos"] for j in jornadas) / max(len(jornadas), 1), 2),
            "media_equis": round(sum(j["equis"] for j in jornadas) / max(len(jornadas), 1), 2),
            "media_doses": round(sum(j["doses"] for j in jornadas) / max(len(jornadas), 1), 2),
            "jornadas_con_5_o_mas_equis": sum(1 for j in jornadas if j["equis"] >= 5),
            "jornadas_con_5_o_mas_doses": sum(1 for j in jornadas if j["doses"] >= 5),
        },
    }


def analizar_jornadas_oficiales():
    resumen = []
    signos = Counter()
    jugadas_nuestras = 0
    aciertos = 0
    fallos = 0

    for path in sorted(JORNADAS_QUINIELA.glob("jornada_*.json"), key=lambda p: int(re.search(r"(\d+)", p.stem).group(1))):
        data = cargar_json(path, {})
        jornada_signos = []
        jornada_nuestra = []
        for partido in data.get("partidos", []):
            oficial = str(partido.get("signo_oficial") or "").strip().upper()
            nuestro = str(partido.get("signo_nuestro") or "").strip().upper()
            if oficial in ("1", "X", "2"):
                signos[oficial] += 1
                jornada_signos.append(oficial)
            if oficial in ("1", "X", "2") and nuestro and "NO JUGADA" not in nuestro:
                jugadas_nuestras += 1
                if oficial in nuestro:
                    aciertos += 1
                else:
                    fallos += 1
                jornada_nuestra.append({"oficial": oficial, "nuestro": nuestro, "acierto": oficial in nuestro})

        resumen.append({
            "jornada": data.get("jornada"),
            "fecha": data.get("fecha"),
            "partidos_con_resultado": len(jornada_signos),
            "signos": "".join(jornada_signos),
            "unos": jornada_signos.count("1"),
            "equis": jornada_signos.count("X"),
            "doses": jornada_signos.count("2"),
            "partidos_jugados_por_nosotros": len(jornada_nuestra),
        })

    total = sum(signos.values()) or 1
    return {
        "jornadas_disponibles": len(resumen),
        "frecuencia_oficial": {k: round(signos[k] / total * 100, 2) for k in ("1", "X", "2")},
        "nuestras_jugadas": {
            "partidos_validados": jugadas_nuestras,
            "aciertos": aciertos,
            "fallos": fallos,
            "precision": round(aciertos / max(jugadas_nuestras, 1) * 100, 2),
        },
        "resumen_jornadas": resumen,
    }


def cargar_quinielas_jugadas():
    data = cargar_json(QUINIELAS_JUGADAS, {"jugadas": []})
    jugadas = {}
    for jugada in data.get("jugadas", []):
        jornada = jugada.get("jornada")
        signos = jugada.get("signos") or []
        if isinstance(signos, str):
            signos = signos.split()
        if isinstance(jornada, int) and signos:
            jugadas[jornada] = {
                "signos": [str(s).strip().upper() for s in signos][:14],
                "elige8": [int(x) for x in jugada.get("elige8", []) if str(x).isdigit()],
                "pleno15": str(jugada.get("pleno15") or jugada.get("pleno15_nuestro") or "").strip(),
                "validado_en": jugada.get("validado_en") or "",
                "origen": jugada.get("origen") or "data/quinielas_jugadas.json",
            }
    return jugadas


def analizar_nuestras_quinielas():
    jugadas = cargar_quinielas_jugadas()
    resumen = []
    total_partidos = 0
    aciertos = 0
    fallos = 0
    elige8_total = 0
    elige8_aciertos = 0
    pleno_total = 0
    pleno_aciertos = 0

    for jornada, jugada in sorted(jugadas.items()):
        path = JORNADAS_QUINIELA / f"jornada_{jornada}.json"
        data = cargar_json(path, {})
        detalle = []
        jornada_aciertos = 0
        jornada_fallos = 0
        for idx, partido in enumerate(data.get("partidos", [])):
            oficial = str(partido.get("signo_oficial") or "").strip().upper()
            nuestro = str(jugada["signos"][idx] if idx < len(jugada["signos"]) else "").strip().upper()
            if oficial not in ("1", "X", "2") or not nuestro:
                continue
            acierto = oficial in nuestro
            total_partidos += 1
            if acierto:
                aciertos += 1
                jornada_aciertos += 1
            else:
                fallos += 1
                jornada_fallos += 1
            if partido.get("num") in jugada["elige8"]:
                elige8_total += 1
                if acierto:
                    elige8_aciertos += 1
            detalle.append({
                "num": partido.get("num"),
                "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
                "oficial": oficial,
                "nuestro": nuestro,
                "acierto": acierto,
                "elige8": partido.get("num") in jugada["elige8"],
            })

        pleno_oficial = str((data.get("pleno15") or {}).get("resultado") or (data.get("pleno15") or {}).get("signo_oficial") or "").strip()
        pleno_nuestro = jugada.get("pleno15", "")
        pleno_acierto = None
        if pleno_oficial and pleno_oficial.lower() != "pendiente" and pleno_nuestro:
            pleno_total += 1
            pleno_acierto = pleno_nuestro == pleno_oficial
            if pleno_acierto:
                pleno_aciertos += 1

        resumen.append({
            "jornada": jornada,
            "aciertos": jornada_aciertos,
            "fallos": jornada_fallos,
            "partidos_analizados": jornada_aciertos + jornada_fallos,
            "pleno15_oficial": pleno_oficial or "Pendiente",
            "pleno15_nuestro": pleno_nuestro or "No validado",
            "pleno15_acierto": pleno_acierto,
            "detalle": detalle,
        })

    return {
        "jornadas_validadas": len(jugadas),
        "partidos_validados": total_partidos,
        "aciertos": aciertos,
        "fallos": fallos,
        "precision": round(aciertos / max(total_partidos, 1) * 100, 2),
        "elige8": {
            "selecciones": elige8_total,
            "aciertos": elige8_aciertos,
            "precision": round(elige8_aciertos / max(elige8_total, 1) * 100, 2),
        },
        "pleno15": {
            "jugados": pleno_total,
            "aciertos": pleno_aciertos,
            "precision": round(pleno_aciertos / max(pleno_total, 1) * 100, 2),
        },
        "resumen": resumen,
    }


def pesos_recomendados(ligas, quiniela):
    equis = quiniela["historico_csv"]["frecuencia_global"].get("X", 28)
    doses = quiniela["historico_csv"]["frecuencia_global"].get("2", 27)
    sorpresas = sum(liga["resumen_sorpresas"]["total"] for liga in ligas.values())

    return {
        "forma_reciente": 0.24,
        "casa_fuera": 0.18,
        "clasificacion_y_puntos": 0.18,
        "goles_favor_contra": 0.14,
        "tendencia_empate": 0.10 if equis < 30 else 0.14,
        "patron_quinielistico_posicion": 0.10,
        "riesgo_sorpresa": 0.06 if sorpresas < 50 else 0.10,
        "nota": "Pesos iniciales aprendidos desde 2025/2026; se ajustan al validar quinielas propias.",
        "alertas": {
            "frecuencia_x_historica": equis,
            "frecuencia_2_historica": doses,
            "sorpresas_liga_detectadas": sorpresas,
        },
    }


def equipo_para_clasificacion(equipo):
    return {
        "posicion": equipo["posicion"],
        "equipo": equipo["equipo"],
        "pj": equipo["pj"],
        "g": equipo["g"],
        "e": equipo["e"],
        "p": equipo["p"],
        "gf": equipo["gf"],
        "gc": equipo["gc"],
        "dg": equipo["dg"],
        "puntos": equipo["pts"],
        "pts": equipo["pts"],
        "racha_actual": equipo["racha_actual"],
        "tendencias": equipo["tendencias"],
    }


def construir_clasificaciones(ligas):
    return {
        "primera": [equipo_para_clasificacion(e) for e in ligas["primera"]["equipos"]],
        "segunda": [equipo_para_clasificacion(e) for e in ligas["segunda"]["equipos"]],
    }


def main():
    ligas = {nombre: analizar_liga(nombre, path) for nombre, path in CALENDARIOS.items()}
    quiniela = {
        "historico_csv": analizar_historico_quiniela(),
        "jornadas_oficiales": analizar_jornadas_oficiales(),
        "nuestras_quinielas": analizar_nuestras_quinielas(),
    }

    memoria = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "temporada": TEMPORADA_LABEL,
        "estado": "base_real_en_construccion",
        "ligas": ligas,
        "quiniela": quiniela,
        "pesos_recomendados": pesos_recomendados(ligas, quiniela),
        "preparacion_2026_2027": {
            "estado": "preparada_para_reiniciar_con_equipos_actualizados",
            "requiere": [
                "detectar ascensos y descensos",
                "crear calendarios 2026/2027 cuando se publiquen",
                "mantener memoria 2025/2026 como aprendizaje historico",
                "reiniciar estadisticas de temporada sin borrar memoria global",
            ],
        },
    }

    guardar_json(OUT_TEMPORADA / "resumen_temporada.json", memoria)
    guardar_json(OUT_MEMORIA / "aprendizaje_global.json", memoria)
    guardar_json(ROOT / "clasificaciones.json", construir_clasificaciones(ligas))
    print(f"Memoria IA construida: {OUT_MEMORIA / 'aprendizaje_global.json'}")


if __name__ == "__main__":
    main()
