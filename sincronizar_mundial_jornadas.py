"""Sincroniza resultados confirmados del Mundial 2026 hacia jornadas de Quiniela.

Evita que una jornada quede bloqueada con partidos pendientes cuando el resultado ya
esta confirmado en data/mundial_2026_resultados.json.
"""

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
RESULTADOS_MUNDIAL = DATA / "mundial_2026_resultados.json"
SIGNOS = {"1", "X", "2"}

ALIAS = {
    "curacao": "curazao",
    "curaçao": "curazao",
    "curazao": "curazao",
    "costa marfil": "costa de marfil",
    "costa de marfil": "costa de marfil",
    "ivory coast": "costa de marfil",
    "cote divoire": "costa de marfil",
    "alemania": "alemania",
    "germany": "alemania",
    "ecuador": "ecuador",
}


def ahora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalizar(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|club|real|de|del|la|el|balompie|futbol)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = " ".join(texto.split()).strip()
    return ALIAS.get(texto, texto)


def resultado_valido(resultado):
    return re.match(r"^\s*\d{1,2}\s*-\s*\d{1,2}\s*$", str(resultado or "")) is not None


def normalizar_resultado(resultado):
    match = re.match(r"^\s*(\d{1,2})\s*-\s*(\d{1,2})\s*$", str(resultado or ""))
    if not match:
        return ""
    return f"{int(match.group(1))}-{int(match.group(2))}"


def signo_resultado(resultado):
    gl, gv = [int(x) for x in normalizar_resultado(resultado).split("-")]
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def signo_valido(valor):
    return str(valor or "").strip().upper() in SIGNOS


def indice_resultados_mundial():
    data = cargar_json(RESULTADOS_MUNDIAL, {"resultados": []})
    indice = {}
    for partido in data.get("resultados", []):
        if str(partido.get("confianza") or "").lower() != "confirmado":
            continue
        resultado = normalizar_resultado(partido.get("resultado"))
        if not resultado:
            continue
        local = normalizar(partido.get("local"))
        visitante = normalizar(partido.get("visitante"))
        if not local or not visitante:
            continue
        item = dict(partido)
        item["resultado"] = resultado
        indice[(local, visitante)] = item
    return indice


def es_candidato_mundial(partido):
    texto = " ".join(str(partido.get(campo) or "") for campo in (
        "competicion_resuelta",
        "modelo_datos_recomendado",
        "fuente_equipos",
    )).lower()
    resolucion = partido.get("resolucion_competicion") or {}
    texto += " " + " ".join(str(resolucion.get(campo) or "") for campo in (
        "competicion",
        "modelo_recomendado",
        "lectura",
    )).lower()
    return "mundial" in texto or "selecciones" in texto


def resultado_confirmado_para(partido, indice):
    clave = (normalizar(partido.get("local")), normalizar(partido.get("visitante")))
    return indice.get(clave)


def sincronizar_jornadas_desde_mundial():
    indice = indice_resultados_mundial()
    if not indice:
        return 0, []

    cambios = 0
    detalles = []
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = cargar_json(path, {})
        if not data:
            continue
        cambios_archivo = 0
        for partido in data.get("partidos", []):
            if not es_candidato_mundial(partido):
                continue
            confirmado = resultado_confirmado_para(partido, indice)
            if not confirmado:
                continue
            resultado = confirmado.get("resultado")
            signo = signo_resultado(resultado)
            if partido.get("resultado") == resultado and partido.get("signo_oficial") == signo:
                continue
            partido["resultado"] = resultado
            partido["signo_oficial"] = signo
            partido["fuente_resultado"] = "mundial_2026_resultados"
            partido["actualizado_en"] = ahora_iso()
            cambios += 1
            cambios_archivo += 1
            detalles.append({
                "jornada": data.get("jornada"),
                "num": partido.get("num"),
                "local": partido.get("local"),
                "visitante": partido.get("visitante"),
                "resultado": resultado,
                "signo": signo,
            })

        if cambios_archivo:
            data["estado"] = "cerrada" if all(signo_valido(p.get("signo_oficial")) for p in data.get("partidos", [])) else "en_juego"
            data["actualizado_en"] = ahora_iso()
            data["sincronizado_mundial_2026_en"] = ahora_iso()
            guardar_json(path, data)
    return cambios, detalles


def main():
    cambios, detalles = sincronizar_jornadas_desde_mundial()
    print(json.dumps({"cambios": cambios, "detalles": detalles}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
