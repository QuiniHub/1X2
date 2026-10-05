"""Estudio: que equipos empatan mas (y donde) + con que equipos acertamos
y fallamos mas nosotros (peticion de Marc, 05/10/2026, tras la tercera
jornada seguida de 'X vecinas').

Parte A - EQUIPOS EMPATADORES: % de empates por equipo con los partidos
reales de 1a y 2a (3 temporadas completas + la 26/27 en curso, mismos datos
que entrenan el Dixon-Coles), total y separado casa/fuera, y la version
"solo 26/27" para ver el perfil de ESTA temporada.

Parte B - NUESTRA FIABILIDAD POR EQUIPO: con el diario de aprendizaje real
(todos los boletos jugados), % de acierto en los partidos donde aparece
cada equipo, y cuantos de nuestros fallos con ese equipo fueron por X.

Salida: data/memoria_ia/equipos_x_fiabilidad.json + resumen por pantalla.
Estudio bajo demanda (no entra en el pipeline), patron de la casa.
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from modelo_dixon_coles import cargar_partidos, clave_equipo

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SALIDA = DATA / "memoria_ia" / "equipos_x_fiabilidad.json"

MIN_PARTIDOS = 30      # para el ranking historico
MIN_PARTIDOS_2627 = 5  # para el perfil de esta temporada
MIN_NUESTROS = 4       # minimo de apariciones en nuestros boletos


def parte_a():
    partidos = cargar_partidos()
    corte_2627 = datetime(2026, 8, 1)
    stats = defaultdict(lambda: {"pj": 0, "x": 0, "pj_casa": 0, "x_casa": 0,
                                 "pj_fuera": 0, "x_fuera": 0, "pj_26": 0, "x_26": 0})
    for p in partidos:
        es_x = p["gl"] == p["gv"]
        reciente = p["fecha"] >= corte_2627
        for equipo, en_casa in ((p["local"], True), (p["visitante"], False)):
            s = stats[equipo]
            s["pj"] += 1
            s["x"] += es_x
            if en_casa:
                s["pj_casa"] += 1
                s["x_casa"] += es_x
            else:
                s["pj_fuera"] += 1
                s["x_fuera"] += es_x
            if reciente:
                s["pj_26"] += 1
                s["x_26"] += es_x
    filas = []
    for equipo, s in stats.items():
        if s["pj"] < MIN_PARTIDOS:
            continue
        filas.append({
            "equipo": equipo,
            "pj": s["pj"],
            "x_pct": round(100 * s["x"] / s["pj"], 1),
            "x_casa_pct": round(100 * s["x_casa"] / max(s["pj_casa"], 1), 1),
            "x_fuera_pct": round(100 * s["x_fuera"] / max(s["pj_fuera"], 1), 1),
            "pj_2627": s["pj_26"],
            "x_2627_pct": round(100 * s["x_26"] / s["pj_26"], 1) if s["pj_26"] >= MIN_PARTIDOS_2627 else None,
        })
    filas.sort(key=lambda f: -f["x_pct"])
    return filas


def parte_b():
    diario = json.loads((DATA / "memoria_ia" / "diario_aprendizaje.json").read_text(encoding="utf-8"))
    stats = defaultdict(lambda: {"n": 0, "aciertos": 0, "fallos_x": 0, "fallos": 0})
    for e in diario.get("entradas", []):
        if e.get("acierto") not in (True, False):
            continue
        partido = re.sub(r"^\s*\d+\.\s*", "", str(e.get("partido") or ""))
        trozos = re.split(r"\s+-\s+", partido, maxsplit=1)
        if len(trozos) != 2:
            continue
        real = str(e.get("signo_real") or "").upper()
        for nombre in trozos:
            eq = clave_equipo(nombre)
            if not eq:
                continue
            s = stats[eq]
            s["n"] += 1
            if e["acierto"]:
                s["aciertos"] += 1
            else:
                s["fallos"] += 1
                if real == "X":
                    s["fallos_x"] += 1
    filas = []
    for eq, s in stats.items():
        if s["n"] < MIN_NUESTROS:
            continue
        filas.append({
            "equipo": eq,
            "apariciones": s["n"],
            "acierto_pct": round(100 * s["aciertos"] / s["n"], 1),
            "fallos": s["fallos"],
            "fallos_por_x": s["fallos_x"],
        })
    filas.sort(key=lambda f: f["acierto_pct"])
    return filas


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = parte_a()
    b = parte_b()
    print("== A) EQUIPOS MAS EMPATADORES (historico 3 temp + 26/27, min 30 pj) ==")
    for f in a[:12]:
        extra = f" | 26/27: {f['x_2627_pct']}%" if f["x_2627_pct"] is not None else ""
        print(f"  {f['equipo']:22s} X {f['x_pct']:4.1f}% (casa {f['x_casa_pct']:4.1f} / fuera {f['x_fuera_pct']:4.1f}) pj{f['pj']}{extra}")
    print("\n== A2) MENOS empatadores ==")
    for f in a[-6:]:
        print(f"  {f['equipo']:22s} X {f['x_pct']:4.1f}% pj{f['pj']}")
    print("\n== A3) Los mas empatadores SOLO en la 26/27 (min 5 pj) ==")
    s26 = sorted([f for f in a if f["x_2627_pct"] is not None], key=lambda f: -f["x_2627_pct"])
    for f in s26[:8]:
        print(f"  {f['equipo']:22s} X 26/27 {f['x_2627_pct']:4.1f}% ({f['pj_2627']} pj) | historico {f['x_pct']}%")
    print("\n== B) NUESTRA FIABILIDAD POR EQUIPO (peor acierto primero, min 4 apariciones) ==")
    for f in b[:12]:
        print(f"  {f['equipo']:22s} acierto {f['acierto_pct']:5.1f}% en {f['apariciones']:>2} | fallos {f['fallos']} (por X: {f['fallos_por_x']})")
    print("\n== B2) Nuestros talismanes (mejor acierto) ==")
    for f in sorted(b, key=lambda f: -f["acierto_pct"])[:8]:
        print(f"  {f['equipo']:22s} acierto {f['acierto_pct']:5.1f}% en {f['apariciones']:>2}")
    SALIDA.write_text(json.dumps({
        "version": 1,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": "Equipos mas/menos empatadores (historico y 26/27) y fiabilidad de nuestros boletos por equipo.",
        "equipos_empatadores": a,
        "fiabilidad_nuestra_por_equipo": sorted(b, key=lambda f: f["acierto_pct"]),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nGuardado en", SALIDA)
