"""Estudio del efecto revulsivo del cambio de entrenador (peticion de Marc,
16/09/2026, tras el 3-2 del Valencia en Mendizorroza con interino debutante
que nos costo el P2 de la J7 por recortar su triple a doble).

Cruza los ceses de entrenador a mitad de temporada (1a y 2a, temporadas
2023/24-2025/26, compilados de Wikipedia/prensa en
data/memoria_ia/ceses_entrenadores.json) con el historico real de partidos
y cuotas (data/memoria_ia/historico_ligas_espana.json) y mide:

 - puntos/partido en los 5 partidos ANTES del cese
 - resultado de los primeros 1, 2 y 3 partidos DESPUES
 - lo importante para la Quiniela: en el PRIMER partido post-cese, cuantas
   veces el equipo puntua (no pierde), gana, y cuantas veces el resultado
   fue MEJOR de lo que decia el mercado (cuotas) -eso es el revulsivo puro,
   separado de "jugaba contra un rival facil".

Salida: data/memoria_ia/efecto_revulsivo.json + resumen por pantalla.
No forma parte del pipeline (estudio bajo demanda); si el efecto medido
resulta accionable, la integracion en el motor ira con backtest previo
como manda el metodo.
"""
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HISTORICO = ROOT / "data" / "memoria_ia" / "historico_ligas_espana.json"
CESES = ROOT / "data" / "memoria_ia" / "ceses_entrenadores.json"
SALIDA = ROOT / "data" / "memoria_ia" / "efecto_revulsivo.json"


def normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(cd|cf|fc|ud|sd|rc|rcd|ca|ce|ad|cp|real|club|deportivo|de|la|el|los|las)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


# football-data usa nombres cortos ("Vallecano", "Sociedad"); mapeo de apoyo
ALIAS = {
    "rayo vallecano": "vallecano",
    "sociedad futbol": "sociedad",
    "athletic bilbao": "ath bilbao",
    "athletic": "ath bilbao",
    "atletico madrid": "ath madrid",
    "sporting gijon": "sp gijon",
    "racing santander": "santander",
    "racing ferrol": "ferrol",
}


def mismo_equipo(nombre_cese, nombre_historico):
    a = normalizar(nombre_cese)
    b = normalizar(nombre_historico)
    if not a or not b:
        return False
    a = ALIAS.get(a, a)
    if a == b:
        return True
    return (a in b or b in a) and min(len(a), len(b)) >= 4


def prob_desde_cuotas(p):
    try:
        inv = {s: 1.0 / float(p[f"cuota_{s.lower()}"]) for s in ("1", "X", "2")}
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    total = sum(inv.values())
    return {s: v / total for s, v in inv.items()}


def puntos_de(partido, equipo):
    es_local = mismo_equipo(equipo, partido["local"])
    signo = partido.get("signo")
    if signo == "X":
        return 1
    if (signo == "1" and es_local) or (signo == "2" and not es_local):
        return 3
    return 0


def puntos_esperados(partido, equipo):
    probs = prob_desde_cuotas(partido)
    if not probs:
        return None
    es_local = mismo_equipo(equipo, partido["local"])
    pg = probs["1"] if es_local else probs["2"]
    return 3 * pg + probs["X"]


def analizar():
    historico = json.loads(HISTORICO.read_text(encoding="utf-8"))
    ceses = json.loads(CESES.read_text(encoding="utf-8"))["ceses"]

    partidos_por_liga = {}
    for liga in ("primera", "segunda"):
        todos = []
        for temporada in historico["ligas"][liga]["temporadas"].values():
            todos.extend(temporada["partidos"])
        todos.sort(key=lambda p: p["fecha"])
        partidos_por_liga[liga] = todos

    casos = []
    sin_match = []
    for cese in ceses:
        equipo = cese["equipo"]
        fecha = str(cese["fecha_cese"])[:10]
        if len(fecha) < 10:  # fecha aproximada (YYYY-MM): usar dia 15
            fecha = fecha[:7] + "-15"
        liga = cese.get("liga") or ("primera" if cese.get("division") == 1 else "segunda")
        pool = [p for p in partidos_por_liga.get(liga, [])
                if str(p["temporada"])[:4] == str(cese["temporada"])[:4]
                and (mismo_equipo(equipo, p["local"]) or mismo_equipo(equipo, p["visitante"]))]
        if not pool:
            sin_match.append(f"{equipo} ({cese['temporada']})")
            continue
        antes = [p for p in pool if p["fecha"] < fecha][-5:]
        despues = [p for p in pool if p["fecha"] >= fecha][:3]
        if not despues or len(antes) < 3:
            sin_match.append(f"{equipo} ({cese['temporada']}) [sin ventana completa]")
            continue
        caso = {
            "equipo": equipo,
            "temporada": cese["temporada"],
            "liga": liga,
            "fecha_cese": fecha,
            "ppg_antes_5": round(sum(puntos_de(p, equipo) for p in antes) / len(antes), 2),
            "pts_post_1": puntos_de(despues[0], equipo),
            "pts_post_3": sum(puntos_de(p, equipo) for p in despues),
            "n_post": len(despues),
            "primer_partido": {
                "fecha": despues[0]["fecha"],
                "local": despues[0]["local"],
                "visitante": despues[0]["visitante"],
                "resultado": despues[0]["resultado"],
                "signo": despues[0]["signo"],
                "es_local": mismo_equipo(equipo, despues[0]["local"]),
            },
        }
        esp = puntos_esperados(despues[0], equipo)
        if esp is not None:
            caso["pts_esperados_post_1"] = round(esp, 2)
            caso["sorpresa_vs_mercado"] = round(caso["pts_post_1"] - esp, 2)
        casos.append(caso)

    def resumen_de(subcasos, etiqueta):
        n = len(subcasos)
        if not n:
            return {"casos": 0}
        con_mercado = [c for c in subcasos if "pts_esperados_post_1" in c]
        return {
            "etiqueta": etiqueta,
            "casos": n,
            "ppg_antes_5_media": round(sum(c["ppg_antes_5"] for c in subcasos) / n, 2),
            "ppg_post_1_media": round(sum(c["pts_post_1"] for c in subcasos) / n, 2),
            "ppg_post_3_media": round(sum(c["pts_post_3"] / c["n_post"] for c in subcasos) / n, 2),
            "primer_partido_no_pierde_pct": round(100 * sum(1 for c in subcasos if c["pts_post_1"] > 0) / n, 1),
            "primer_partido_gana_pct": round(100 * sum(1 for c in subcasos if c["pts_post_1"] == 3) / n, 1),
            "sorpresa_vs_mercado_media": round(
                sum(c["sorpresa_vs_mercado"] for c in con_mercado) / len(con_mercado), 2
            ) if con_mercado else None,
            "supera_al_mercado_pct": round(
                100 * sum(1 for c in con_mercado if c["sorpresa_vs_mercado"] > 0) / len(con_mercado), 1
            ) if con_mercado else None,
        }

    salida = {
        "version": 1,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": "Efecto del cambio de entrenador a mitad de temporada, 1a y 2a, 2023/24-2025/26, medido contra resultados y cuotas reales.",
        "resumen": {
            "global": resumen_de(casos, "todas"),
            "primera": resumen_de([c for c in casos if c["liga"] == "primera"], "primera"),
            "segunda": resumen_de([c for c in casos if c["liga"] == "segunda"], "segunda"),
            "primer_partido_en_casa": resumen_de([c for c in casos if c["primer_partido"]["es_local"]], "post-cese en casa"),
            "primer_partido_fuera": resumen_de([c for c in casos if not c["primer_partido"]["es_local"]], "post-cese fuera"),
        },
        "casos": casos,
        "ceses_sin_cruce": sin_match,
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return salida


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    s = analizar()
    print(f"Casos cruzados: {s['resumen']['global']['casos']} | sin cruce: {len(s['ceses_sin_cruce'])}")
    for clave in ("global", "primera", "segunda", "primer_partido_en_casa", "primer_partido_fuera"):
        r = s["resumen"][clave]
        if not r.get("casos"):
            continue
        print(f"\n[{clave}] n={r['casos']}")
        print(f"  ppg antes (5 partidos): {r['ppg_antes_5_media']} -> 1er partido despues: {r['ppg_post_1_media']} -> 3 primeros: {r['ppg_post_3_media']}")
        print(f"  1er partido: no pierde {r['primer_partido_no_pierde_pct']}% | gana {r['primer_partido_gana_pct']}%")
        print(f"  vs mercado: {r['sorpresa_vs_mercado_media']} pts sobre lo esperado | supera cuotas {r['supera_al_mercado_pct']}%")
    print("\nGuardado en", SALIDA)
