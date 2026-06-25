"""Sincroniza resultados confirmados hacia jornadas abiertas.

Solucion permanente: antes de que la compuerta revise data/jornadas/jornada_X.json,
este script completa partidos pendientes si el resultado ya existe en otra fuente
estructurada del repo:
- data/mundial_2026_resultados.json
- data/historial_partidos_primera.json
- data/historial_partidos_segunda.json

Genera log en data/sincronizacion_resultados.json.
"""

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
MUNDIAL = DATA / "mundial_2026_resultados.json"
HISTORIAL_PRIMERA = DATA / "historial_partidos_primera.json"
HISTORIAL_SEGUNDA = DATA / "historial_partidos_segunda.json"
LOG = DATA / "sincronizacion_resultados.json"
SIGNOS = {"1", "X", "2"}

ALIAS = {
    "curacao": "curazao",
    "curaçao": "curazao",
    "curazao": "curazao",
    "costa marfil": "costa de marfil",
    "costa de marfil": "costa de marfil",
    "ivory coast": "costa de marfil",
    "cote divoire": "costa de marfil",
    "ath madrid": "atletico madrid",
    "at madrid": "atletico madrid",
    "atletico": "atletico madrid",
    "ath bilbao": "athletic bilbao",
    "athletic": "athletic bilbao",
    "sociedad": "real sociedad",
    "r sociedad": "real sociedad",
    "vallecano": "rayo vallecano",
    "santander": "racing santander",
    "sp gijon": "sporting gijon",
    "sporting": "sporting gijon",
    "alaves": "alaves",
    "deportivo alaves": "alaves",
    "barca": "barcelona",
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
        texto = path.read_text(encoding="utf-8").strip()
        if not texto:
            return defecto
        return json.loads(texto)
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


def clave_equipos(local, visitante):
    return normalizar(local), normalizar(visitante)


def resultado_valido(resultado):
    return re.match(r"^\s*\d{1,2}\s*-\s*\d{1,2}\s*$", str(resultado or "")) is not None


def normalizar_resultado(resultado):
    m = re.match(r"^\s*(\d{1,2})\s*-\s*(\d{1,2})\s*$", str(resultado or ""))
    if not m:
        return ""
    return f"{int(m.group(1))}-{int(m.group(2))}"


def resultado_desde_goles(item):
    gl = item.get("goles_local")
    gv = item.get("goles_visitante")
    if gl in (None, "") or gv in (None, ""):
        return ""
    try:
        return f"{int(float(gl))}-{int(float(gv))}"
    except (TypeError, ValueError):
        return ""


def signo_resultado(resultado):
    resultado = normalizar_resultado(resultado)
    if not resultado:
        return ""
    gl, gv = [int(x) for x in resultado.split("-")]
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def signo_pendiente(valor):
    return str(valor or "").strip().upper() not in SIGNOS


def fecha_cercana(fecha_jornada, fecha_fuente, tolerancia_dias=2):
    if not fecha_fuente:
        return True
    if not fecha_jornada:
        return True
    try:
        fj = datetime.fromisoformat(str(fecha_jornada)[:10]).date()
        ff = datetime.fromisoformat(str(fecha_fuente)[:10]).date()
    except ValueError:
        return True
    return abs((fj - ff).days) <= tolerancia_dias


def es_jornada_abierta(data):
    estado = str(data.get("estado") or "").lower()
    if estado in {"cerrada", "aprendida"}:
        return any(signo_pendiente(p.get("signo_oficial")) for p in data.get("partidos", []))
    return True


def cargar_fuentes_confirmadas():
    fuentes = []

    mundial = cargar_json(MUNDIAL, {"resultados": []})
    for item in mundial.get("resultados", []):
        if str(item.get("confianza") or "").lower() != "confirmado":
            continue
        resultado = normalizar_resultado(item.get("resultado"))
        if not resultado:
            continue
        fuentes.append({
            "origen": "mundial_2026_resultados",
            "archivo": str(MUNDIAL.relative_to(ROOT)),
            "fecha": item.get("fecha") or "",
            "local": item.get("local") or "",
            "visitante": item.get("visitante") or "",
            "resultado": resultado,
        })

    for archivo, origen in ((HISTORIAL_PRIMERA, "historial_partidos_primera"), (HISTORIAL_SEGUNDA, "historial_partidos_segunda")):
        data = cargar_json(archivo, {})
        if not isinstance(data, dict):
            continue
        for jornada, partidos in data.items():
            for item in partidos or []:
                resultado = normalizar_resultado(item.get("resultado")) or resultado_desde_goles(item)
                if not resultado:
                    continue
                estado = str(item.get("estado") or "").lower()
                if estado and estado not in {"jugado", "finalizado", "cerrado", "terminado"} and not resultado_valido(resultado):
                    continue
                fuentes.append({
                    "origen": origen,
                    "archivo": str(archivo.relative_to(ROOT)),
                    "jornada_fuente": jornada,
                    "fecha": item.get("fecha") or "",
                    "local": item.get("local") or "",
                    "visitante": item.get("visitante") or "",
                    "resultado": resultado,
                })
    return fuentes


def buscar_confirmado(partido, fuentes):
    local, visitante = clave_equipos(partido.get("local"), partido.get("visitante"))
    fecha = partido.get("fecha") or ""
    for item in fuentes:
        flocal, fvisitante = clave_equipos(item.get("local"), item.get("visitante"))
        if local == flocal and visitante == fvisitante and fecha_cercana(fecha, item.get("fecha")):
            return item
    return None


def sincronizar():
    fuentes = cargar_fuentes_confirmadas()
    log = cargar_json(LOG, {"version": "1.0", "actualizaciones": []})
    actualizaciones = []
    cambios = 0

    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = cargar_json(path, {})
        if not data or not es_jornada_abierta(data):
            continue
        cambios_archivo = 0
        for partido in data.get("partidos", []):
            if not signo_pendiente(partido.get("signo_oficial")):
                continue
            confirmado = buscar_confirmado(partido, fuentes)
            if not confirmado:
                continue
            resultado = normalizar_resultado(confirmado.get("resultado"))
            signo = signo_resultado(resultado)
            if not resultado or signo not in SIGNOS:
                continue
            partido["resultado"] = resultado
            partido["signo_oficial"] = signo
            partido["fuente_resultado"] = confirmado.get("origen")
            partido["actualizado_en"] = ahora_iso()
            cambios += 1
            cambios_archivo += 1
            actualizaciones.append({
                "actualizado_en": ahora_iso(),
                "jornada": data.get("jornada"),
                "archivo_jornada": str(path.relative_to(ROOT)),
                "num": partido.get("num"),
                "local": partido.get("local"),
                "visitante": partido.get("visitante"),
                "resultado": resultado,
                "signo_oficial": signo,
                "fuente": confirmado.get("archivo"),
                "origen": confirmado.get("origen"),
                "fecha_partido": partido.get("fecha") or "",
                "fecha_fuente": confirmado.get("fecha") or "",
            })
        if cambios_archivo:
            data["estado"] = "cerrada" if all(not signo_pendiente(p.get("signo_oficial")) for p in data.get("partidos", []) if int(p.get("num") or 0) <= 14) else "en_juego"
            data["actualizado_en"] = ahora_iso()
            data["sincronizacion_resultados_en"] = ahora_iso()
            guardar_json(path, data)

    log["version"] = "1.0"
    log["generado_en"] = ahora_iso()
    log["cambios_ultima_ejecucion"] = cambios
    log["actualizaciones_ultima_ejecucion"] = actualizaciones
    historico = log.get("actualizaciones") or []
    log["actualizaciones"] = (historico + actualizaciones)[-500:]
    guardar_json(LOG, log)
    return cambios, actualizaciones


def main():
    cambios, actualizaciones = sincronizar()
    print(json.dumps({
        "estado": "ok",
        "script": "sincronizar_resultados_jornada.py",
        "cambios": cambios,
        "actualizaciones": actualizaciones,
        "log": str(LOG.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
