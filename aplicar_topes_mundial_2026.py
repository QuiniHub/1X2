import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
CLASIFICACIONES = DATA / "memoria_ia" / "clasificaciones_mundial_2026.json"
ELIMINADOS = {"turquia", "tunez", "jordania", "panama", "haiti"}
TOP = {"argentina", "brasil", "francia", "espana", "inglaterra", "alemania", "paises bajos", "portugal", "belgica"}
RANKING = {"francia": 1, "espana": 2, "argentina": 3, "inglaterra": 4, "portugal": 5, "brasil": 6, "paises bajos": 7, "belgica": 9, "alemania": 10, "turquia": 24, "panama": 36, "tunez": 49, "jordania": 68, "haiti": 83}
ALIAS = {"espana": "espana", "spain": "espana", "france": "francia", "england": "inglaterra", "germany": "alemania", "brazil": "brasil", "netherlands": "paises bajos", "holanda": "paises bajos", "belgium": "belgica", "turkey": "turquia", "turkiye": "turquia", "tunisia": "tunez", "jordan": "jordania"}


def norm(nombre):
    txt = str(nombre or "").strip().lower()
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    txt = re.sub(r"[^a-z0-9]+", " ", txt).strip()
    return ALIAS.get(txt, txt)


def cargar(path, defecto=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {} if defecto is None else defecto


def guardar(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm_probs(probs):
    p = {k: max(float(probs.get(k, 1.0)), 1.0) for k in ("1", "X", "2")}
    total = sum(p.values()) or 1.0
    out = {k: round(v / total * 100.0, 1) for k, v in p.items()}
    out[max(out, key=out.get)] = round(max(out.values()) + 100.0 - sum(out.values()), 1)
    return out


def actualizar_derivados(partido, nuevo, nota, metadata):
    orden = sorted(nuevo, key=nuevo.get, reverse=True)
    signo = orden[0]
    vals = sorted(nuevo.values(), reverse=True)
    partido["probabilidades"] = nuevo
    partido["signo_base"] = signo
    partido["probabilidad_top"] = vals[0]
    partido["margen_probabilidad"] = round(vals[0] - vals[1], 2)
    partido["tercera_probabilidad"] = vals[2]
    partido["favorito"] = signo if signo in {"1", "2"} else None
    partido["favorito_nombre"] = partido.get("local") if signo == "1" else partido.get("visitante") if signo == "2" else "Empate"
    partido.setdefault("lecturas_motivacion", []).append(nota)
    partido.setdefault("motivos_sorpresa", []).append(nota)
    partido.setdefault("trazabilidad_datos", {})["tope_ranking"] = metadata


def recortar_partido(partido):
    local, visitante = norm(partido.get("local")), norm(partido.get("visitante"))
    probs = partido.get("probabilidades") or {}
    if not all(k in probs for k in ("1", "X", "2")):
        return False

    pares = ((local, visitante, "1", "2"), (visitante, local, "2", "1"))
    for bajo, alto, signo_bajo, signo_alto in pares:
        if bajo not in RANKING or alto not in RANKING:
            continue
        diferencia = RANKING[bajo] - RANKING[alto]
        if diferencia <= 50:
            continue
        prob_bajo = float(probs.get(signo_bajo, 0.0))
        if prob_bajo <= 15.0:
            continue
        exceso = prob_bajo - 15.0
        nuevo = {k: float(probs[k]) for k in ("1", "X", "2")}
        nuevo[signo_bajo] = 15.0
        nuevo[signo_alto] += exceso * 0.70
        nuevo["X"] += exceso * 0.30
        nuevo = norm_probs(nuevo)
        nota = f"Regla ranking FIFA: {bajo} limitado al 15% frente a {alto}; exceso redistribuido 70% favorito y 30% empate."
        actualizar_derivados(
            partido,
            nuevo,
            nota,
            {
                "activo": True,
                "tipo": "tope_general_ranking_fifa",
                "equipo_debil": bajo,
                "equipo_fuerte": alto,
                "ranking_equipo_debil": RANKING[bajo],
                "ranking_equipo_fuerte": RANKING[alto],
                "diferencia_ranking": diferencia,
                "maximo_equipo_debil": 15.0,
                "redistribucion_exceso": {"favorito": 0.70, "empate": 0.30},
            },
        )
        return True
    return False


def reforzar_clasificaciones():
    data = cargar(CLASIFICACIONES, {})
    cambios = 0
    valores = {"situacion": "eliminada", "situacion_competitiva": "eliminada", "necesidad_resultado": "ninguna", "motivacion_competitiva": "baja", "objetivos_vivos": False, "rotacion_probable": True}
    filas = list((data.get("equipos") or {}).values())
    for grupo in (data.get("grupos") or {}).values():
        filas.extend(grupo.get("clasificacion", []))
    for equipo in filas:
        if norm(equipo.get("equipo")) in ELIMINADOS:
            for k, v in valores.items():
                if equipo.get(k) != v:
                    equipo[k] = v
                    cambios += 1
    if cambios:
        guardar(CLASIFICACIONES, data)
    return cambios


def aplicar_prediccion(path):
    data = cargar(path, {})
    cambios = sum(1 for p in data.get("partidos", []) if recortar_partido(p))
    if cambios:
        guardar(path, data)
    return cambios


def main():
    cambios_cls = reforzar_clasificaciones()
    ultima = PREDICCIONES / "ultima_prediccion.json"
    paths = [ultima]
    jornada = cargar(ultima, {}).get("jornada")
    if jornada:
        paths.append(PREDICCIONES / f"jornada_{jornada}.json")
    cambios_pred = sum(aplicar_prediccion(p) for p in dict.fromkeys(paths))
    print(f"Topes Mundial 2026 aplicados: clasificacion={cambios_cls}, partidos={cambios_pred}.")


if __name__ == "__main__":
    main()
