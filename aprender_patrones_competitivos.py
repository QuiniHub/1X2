import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CALENDARIOS = {
    "primera": DATA / "calendario_primera.json",
    "segunda": DATA / "calendario_segunda.json",
}
CONTEXTO = DATA / "memoria_ia" / "contexto_competitivo.json"
MEMORIA = DATA / "memoria_ia" / "aprendizaje_global.json"
OUT = DATA / "memoria_ia" / "patrones_competitivos.json"


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


def signo_resultado(resultado):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(resultado or ""))
    if not m:
        return None
    gl, gv = int(m.group(1)), int(m.group(2))
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def equipos_contexto(contexto):
    equipos = []
    for liga in ("primera", "segunda"):
        for equipo in (contexto.get(liga) or {}).get("equipos", []):
            equipos.append({**equipo, "liga": liga})
    return equipos


def mapa_contexto(contexto):
    return {normalizar(e.get("equipo", "")): e for e in equipos_contexto(contexto)}


def buscar_equipo(mapa, nombre):
    objetivo = normalizar(nombre)
    if objetivo in mapa:
        return mapa[objetivo]
    mejor = None
    mejor_score = 0
    for clave, equipo in mapa.items():
        if not clave or not objetivo:
            continue
        if clave in objetivo or objetivo in clave:
            score = 80
        else:
            score = len(set(clave.split()) & set(objetivo.split())) * 20
        if score > mejor_score:
            mejor = equipo
            mejor_score = score
    return mejor if mejor_score >= 20 else None


def texto_competitivo(equipo):
    objetivos = " ".join(
        f"{o.get('objetivo', '')} {o.get('estado', '')} {o.get('lectura', '')}"
        for o in (equipo or {}).get("objetivos", [])
    )
    return f"{objetivos} {(equipo or {}).get('situacion_competitiva', '')} {(equipo or {}).get('motivacion_competitiva', '')}".lower()


def objetivo_cerrado(equipo):
    if not equipo:
        return False
    if equipo.get("objetivos_vivos"):
        return False
    texto = texto_competitivo(equipo)
    return any(
        clave in texto
        for clave in (
            "asegurado_matematicamente",
            "campeon_matematico",
            "salvado_matematicamente",
            "descendido_matematicamente",
            "sin_opciones_matematicas",
            "no se juega nada",
        )
    )


def necesidad_viva(equipo):
    if not equipo or objetivo_cerrado(equipo):
        return False
    texto = texto_competitivo(equipo)
    motivacion = str(equipo.get("motivacion_competitiva") or equipo.get("motivacion") or "").lower()
    return bool(equipo.get("objetivos_vivos")) or motivacion in {"alta", "maxima", "máxima"} or any(
        clave in texto
        for clave in (
            "riesgo_descenso",
            "en_descenso_con_opciones",
            "permanencia_por_cerrar",
            "defiende_plaza",
            "aspira_matematicamente",
            "aspira_por_desempate",
            "descenso",
            "permanencia",
            "playoff",
            "ascenso",
            "conference",
            "europa",
            "champions",
        )
    )


def descenso_vivo(equipo):
    return necesidad_viva(equipo) and any(c in texto_competitivo(equipo) for c in ("descenso", "permanencia", "salvarse"))


def puntos(equipo):
    try:
        return float((equipo or {}).get("puntos") or 0)
    except Exception:
        return 0.0


def resultado_lado(signo, lado):
    if lado == "local":
        if signo == "1":
            return "gana"
        if signo == "X":
            return "puntua"
        return "pierde"
    if signo == "2":
        return "gana"
    if signo == "X":
        return "puntua"
    return "pierde"


def base_patron():
    return {"casos": 0, "sorpresas": 0, "tasa_sorpresa": 0.0, "ejemplos": []}


def registrar(patrones, clave, sorpresa, ejemplo):
    patron = patrones[clave]
    patron["casos"] += 1
    if sorpresa:
        patron["sorpresas"] += 1
    if sorpresa or len(patron["ejemplos"]) < 8:
        patron["ejemplos"].append(ejemplo)
        patron["ejemplos"] = patron["ejemplos"][-12:]


def ejemplo(liga, jornada, partido, signo, lectura):
    return {
        "liga": liga,
        "jornada_liga": jornada.get("jornada"),
        "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
        "resultado": partido.get("resultado"),
        "signo_real": signo,
        "lectura": lectura,
    }


def analizar():
    contexto = cargar_json(CONTEXTO, {})
    mapa = mapa_contexto(contexto)
    patrones = defaultdict(base_patron)

    for liga, path in CALENDARIOS.items():
        calendario = cargar_json(path, {})
        for jornada in calendario.get("jornadas", []):
            for partido in jornada.get("partidos", []):
                signo = signo_resultado(partido.get("resultado"))
                if not signo:
                    continue
                local = buscar_equipo(mapa, partido.get("local", ""))
                visitante = buscar_equipo(mapa, partido.get("visitante", ""))
                if not local or not visitante:
                    continue

                local_cerrado = objetivo_cerrado(local)
                visitante_cerrado = objetivo_cerrado(visitante)
                local_necesita = necesidad_viva(local)
                visitante_necesita = necesidad_viva(visitante)
                local_descenso = descenso_vivo(local)
                visitante_descenso = descenso_vivo(visitante)
                local_favorito = puntos(local) >= puntos(visitante) + 5
                visitante_favorito = puntos(visitante) >= puntos(local) + 5

                if visitante_cerrado and local_necesita:
                    sorpresa = signo != "2"
                    registrar(
                        patrones,
                        "necesitado_local_vs_visitante_objetivo_cerrado",
                        sorpresa,
                        ejemplo(liga, jornada, partido, signo, "El local con objetivo vivo puntua o gana ante visitante con objetivo cerrado."),
                    )
                if local_cerrado and visitante_necesita:
                    sorpresa = signo != "1"
                    registrar(
                        patrones,
                        "visitante_necesitado_vs_local_objetivo_cerrado",
                        sorpresa,
                        ejemplo(liga, jornada, partido, signo, "El visitante con objetivo vivo puntua o gana ante local con objetivo cerrado."),
                    )
                if visitante_descenso and local_favorito:
                    sorpresa = signo != "1"
                    registrar(
                        patrones,
                        "visitante_descenso_vs_local_favorito",
                        sorpresa,
                        ejemplo(liga, jornada, partido, signo, "Visitante con urgencia de descenso/permanencia rompe o amenaza el 1 fijo."),
                    )
                if local_descenso and visitante_favorito:
                    sorpresa = signo != "2"
                    registrar(
                        patrones,
                        "local_descenso_vs_visitante_favorito",
                        sorpresa,
                        ejemplo(liga, jornada, partido, signo, "Local con urgencia de descenso/permanencia rompe o amenaza el 2 fijo."),
                    )
                if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
                    sorpresa = (local_necesita and signo != "2") or (visitante_necesita and signo != "1")
                    registrar(
                        patrones,
                        "equipo_necesitado_vs_equipo_sin_objetivo",
                        sorpresa,
                        ejemplo(liga, jornada, partido, signo, "Choque necesidad contra objetivo cerrado: no tratar al equipo sin objetivo como fijo limpio."),
                    )

    salida_patrones = {}
    for clave, patron in sorted(patrones.items()):
        casos = patron["casos"] or 1
        patron["tasa_sorpresa"] = round(patron["sorpresas"] / casos * 100, 1)
        if patron["casos"] >= 1:
            salida_patrones[clave] = dict(patron)

    salida = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": "Patrones aprendidos de resultados reales de 1a y 2a para no tratar como fijos tranquilos partidos con objetivos cerrados contra rivales necesitados.",
        "patrones": salida_patrones,
        "regla_uso": "Si un patron supera el 30% de sorpresa, sube incertidumbre; si supera el 45%, recomienda cobertura cuando haya dobles/triples.",
    }

    guardar_json(OUT, salida)

    memoria = cargar_json(MEMORIA, {})
    memoria["patrones_competitivos"] = salida
    guardar_json(MEMORIA, memoria)

    contexto["patrones_aprendidos"] = salida
    guardar_json(CONTEXTO, contexto)
    print(f"Patrones competitivos aprendidos: {OUT}")


if __name__ == "__main__":
    analizar()
