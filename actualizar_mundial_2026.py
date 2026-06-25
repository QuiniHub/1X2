"""Actualiza resultados y memoria de forma del Mundial 2026.

Fuentes priorizadas:
- data/jornadas/jornada_X.json ya actualizado por el flujo de resultados.
- Fuentes publicas usadas por el proyecto: quinielafutbol.info, quiniela15 y dondeverlo.

El script no borra resultados confirmados existentes. Solo anade resultados nuevos o
completa partidos pendientes. Tambien regenera data/memoria_ia/mundial_2026_forma.json
con la forma reciente de cada seleccion.
"""

import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

from sincronizar_mundial_jornadas import sincronizar_jornadas_desde_mundial

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
PREDICCIONES = DATA / "predicciones"
RESULTADOS = DATA / "mundial_2026_resultados.json"
MEMORIA = DATA / "memoria_ia" / "mundial_2026_forma.json"

FUENTES = [
    "https://www.quinielafutbol.info/proximas-jornadas-de-la-quiniela.html",
    "https://www.quiniela15.com/resultados-quiniela",
    "https://dondeverlo.es/quiniela/directo/",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

ALIAS = {
    "eeuu": "estados unidos",
    "ee uu": "estados unidos",
    "usa": "estados unidos",
    "united states": "estados unidos",
    "estados unidos": "estados unidos",
    "paises bajos": "paises bajos",
    "holanda": "paises bajos",
    "japon": "japon",
    "costa marfil": "costa de marfil",
    "costa de marfil": "costa de marfil",
    "ivory coast": "costa de marfil",
    "cote divoire": "costa de marfil",
    "curacao": "curazao",
    "curazao": "curazao",
    "curaçao": "curazao",
    "arabia saudi": "arabia saudi",
    "turkiye": "turquia",
    "turkey": "turquia",
    "belgica": "belgica",
    "tunez": "tunez",
    "espana": "espana",
    "mexico": "mexico",
}


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


def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


def normalizar(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = " ".join(texto.split()).strip()
    return ALIAS.get(texto, texto)


def variantes_equipo(nombre):
    base = normalizar(nombre)
    variantes = {base}
    for alias, canonico in ALIAS.items():
        if canonico == base:
            variantes.add(alias)
    if base == "estados unidos":
        variantes.update({"eeuu", "ee uu", "usa", "united states"})
    if base == "paises bajos":
        variantes.update({"holanda", "netherlands"})
    if base == "costa de marfil":
        variantes.update({"costa marfil", "ivory coast", "cote divoire"})
    if base == "curazao":
        variantes.update({"curacao", "curaçao"})
    return {v for v in variantes if v}


def contiene_equipo(texto, equipo):
    base = normalizar(texto)
    return any(v in base for v in variantes_equipo(equipo))


def resultado_valido(resultado):
    return re.match(r"^\s*\d{1,2}\s*-\s*\d{1,2}\s*$", str(resultado or "")) is not None


def normalizar_resultado(resultado):
    m = re.match(r"^\s*(\d{1,2})\s*-\s*(\d{1,2})\s*$", str(resultado or ""))
    if not m:
        return ""
    return f"{int(m.group(1))}-{int(m.group(2))}"


def clave_partido(partido):
    fecha = str(partido.get("fecha") or "").strip()
    local = normalizar(partido.get("local"))
    visitante = normalizar(partido.get("visitante"))
    return (fecha, local, visitante)


def clave_partido_sin_fecha(partido):
    return (normalizar(partido.get("local")), normalizar(partido.get("visitante")))


def es_partido_mundial_o_selecciones(partido):
    texto = " ".join(str(partido.get(campo) or "") for campo in (
        "competicion_resuelta",
        "modelo_datos_recomendado",
        "fuente_equipos",
    )).lower()
    if "mundial" in texto or "selecciones" in texto:
        return True
    resolucion = partido.get("resolucion_competicion") or {}
    texto_resolucion = " ".join(str(resolucion.get(campo) or "") for campo in (
        "competicion",
        "modelo_recomendado",
        "lectura",
    )).lower()
    return "mundial" in texto_resolucion or "selecciones" in texto_resolucion


def signo_resultado(resultado):
    gl, gv = [int(x) for x in normalizar_resultado(resultado).split("-")]
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def descargar_html(url):
    if requests:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as response:
        raw = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def html_a_texto(html):
    if BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return " ".join(soup.get_text(" ").split())
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    return " ".join(unescape(html).split())


def descargar_fuentes():
    textos = []
    for url in FUENTES:
        try:
            texto = html_a_texto(descargar_html(url))
            textos.append((url, texto))
            print(f"Fuente Mundial OK: {url}")
        except Exception as exc:
            print(f"No se pudo consultar {url}: {exc}")
    return textos


def buscar_resultado_en_texto(texto, local, visitante):
    patrones = [
        r"(?P<a>\d{1,2})\s*[-]\s*(?P<b>\d{1,2})",
        r"(?P<a>\d{1,2})\s+a\s+(?P<b>\d{1,2})",
    ]
    for patron in patrones:
        for match in re.finditer(patron, texto, re.I):
            frag = texto[max(0, match.start() - 220): min(len(texto), match.end() + 220)]
            if not (contiene_equipo(frag, local) and contiene_equipo(frag, visitante)):
                continue
            if re.search(r"\b(descanso|1t|2t|min\.?|minuto|en juego|pend|pr[oó]ximo|previa)\b", frag, re.I):
                continue
            return f"{int(match.group('a'))}-{int(match.group('b'))}"
    return ""


def resultados_desde_jornadas():
    resultados = []
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = cargar_json(path, {})
        for partido in data.get("partidos", []):
            if not es_partido_mundial_o_selecciones(partido):
                continue
            resultado = normalizar_resultado(partido.get("resultado"))
            if not resultado:
                continue
            resultados.append({
                "fecha": partido.get("fecha") or "",
                "grupo": partido.get("grupo") or "",
                "local": partido.get("local") or "",
                "visitante": partido.get("visitante") or "",
                "resultado": resultado,
                "fuente": partido.get("fuente_resultado") or str(path.relative_to(ROOT)),
                "confianza": "confirmado",
            })
    return resultados


def candidatos_desde_datos_existentes(data):
    candidatos = []
    for partido in data.get("resultados", []):
        candidatos.append(dict(partido))
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        jornada = cargar_json(path, {})
        for partido in jornada.get("partidos", []):
            if es_partido_mundial_o_selecciones(partido):
                candidatos.append({
                    "fecha": partido.get("fecha") or "",
                    "grupo": partido.get("grupo") or "",
                    "local": partido.get("local") or "",
                    "visitante": partido.get("visitante") or "",
                    "resultado": normalizar_resultado(partido.get("resultado")) or "",
                    "fuente": str(path.relative_to(ROOT)),
                    "confianza": "confirmado" if resultado_valido(partido.get("resultado")) else "pendiente",
                })
    for path in sorted(PREDICCIONES.glob("jornada_*.json")):
        pred = cargar_json(path, {})
        for partido in pred.get("partidos", []):
            if es_partido_mundial_o_selecciones(partido):
                candidatos.append({
                    "fecha": partido.get("fecha") or "",
                    "grupo": partido.get("grupo") or "",
                    "local": partido.get("local") or "",
                    "visitante": partido.get("visitante") or "",
                    "resultado": normalizar_resultado(partido.get("resultado")) or "",
                    "fuente": str(path.relative_to(ROOT)),
                    "confianza": "pendiente",
                })
    return candidatos


def resultados_desde_fuentes(candidatos, fuentes):
    nuevos = []
    for candidato in candidatos:
        if resultado_valido(candidato.get("resultado")):
            continue
        local = candidato.get("local") or ""
        visitante = candidato.get("visitante") or ""
        if not local or not visitante:
            continue
        for url, texto in fuentes:
            resultado = buscar_resultado_en_texto(texto, local, visitante)
            if resultado:
                item = dict(candidato)
                item["resultado"] = resultado
                item["fuente"] = url
                item["confianza"] = "confirmado"
                nuevos.append(item)
                break
    return nuevos


def fusionar_resultados(data, nuevos):
    existentes = list(data.get("resultados", []))
    por_clave = {clave_partido(p): dict(p) for p in existentes if clave_partido(p)[1] and clave_partido(p)[2]}
    por_equipos = {clave_partido_sin_fecha(p): clave_partido(p) for p in existentes if clave_partido_sin_fecha(p)[0] and clave_partido_sin_fecha(p)[1]}
    cambios = 0

    for nuevo in nuevos:
        if not resultado_valido(nuevo.get("resultado")):
            continue
        clave = clave_partido(nuevo)
        if not clave[1] or not clave[2]:
            continue
        if not clave[0] and clave_partido_sin_fecha(nuevo) in por_equipos:
            clave = por_equipos[clave_partido_sin_fecha(nuevo)]
        actual = por_clave.get(clave)
        if actual and resultado_valido(actual.get("resultado")) and actual.get("confianza") == "confirmado":
            continue
        limpio = {
            "fecha": nuevo.get("fecha") or (actual or {}).get("fecha") or "",
            "grupo": nuevo.get("grupo") or (actual or {}).get("grupo") or "",
            "local": nuevo.get("local") or (actual or {}).get("local") or "",
            "visitante": nuevo.get("visitante") or (actual or {}).get("visitante") or "",
            "resultado": normalizar_resultado(nuevo.get("resultado")),
            "fuente": nuevo.get("fuente") or (actual or {}).get("fuente") or "",
            "confianza": "confirmado",
        }
        por_clave[clave] = limpio
        por_equipos[clave_partido_sin_fecha(limpio)] = clave
        cambios += 1

    data["version"] = data.get("version") or "1.0"
    data.pop("actualizado_manual_en", None)
    data["actualizado_en"] = ahora_iso()
    data["nota"] = "Resultados del Mundial 2026 actualizados automaticamente desde fuentes publicas y jornadas del sistema. Los confirmados no se sobrescriben."
    data["resultados"] = sorted(por_clave.values(), key=lambda p: (p.get("fecha") or "9999-99-99", normalizar(p.get("local")), normalizar(p.get("visitante"))))
    return data, cambios


def crear_registro(equipo):
    return {"equipo": equipo, "pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0, "dg": 0, "pts": 0, "partidos": [], "fuentes": []}


def anadir_partido(tabla, equipo, rival, gf, gc, fecha, grupo, fuente, condicion):
    reg = tabla[equipo]
    reg["equipo"] = equipo
    reg["pj"] += 1
    reg["gf"] += gf
    reg["gc"] += gc
    reg["dg"] = reg["gf"] - reg["gc"]
    if gf > gc:
        reg["g"] += 1
        puntos, signo = 3, "G"
    elif gf == gc:
        reg["e"] += 1
        puntos, signo = 1, "E"
    else:
        reg["p"] += 1
        puntos, signo = 0, "P"
    reg["pts"] += puntos
    if fuente and fuente not in reg["fuentes"]:
        reg["fuentes"].append(fuente)
    reg["partidos"].append({"fecha": fecha, "grupo": grupo, "rival": rival, "condicion": condicion, "resultado": f"{gf}-{gc}", "signo_equipo": signo, "puntos": puntos})


def construir_memoria(data):
    tabla = defaultdict(lambda: crear_registro(""))
    descartados = []
    for partido in data.get("resultados", []):
        resultado = normalizar_resultado(partido.get("resultado"))
        if not resultado:
            descartados.append(partido)
            continue
        local = normalizar(partido.get("local"))
        visitante = normalizar(partido.get("visitante"))
        if not local or not visitante:
            descartados.append(partido)
            continue
        gl, gv = [int(x) for x in resultado.split("-")]
        fecha = partido.get("fecha") or ""
        grupo = partido.get("grupo") or ""
        fuente = partido.get("fuente") or ""
        anadir_partido(tabla, local, visitante, gl, gv, fecha, grupo, fuente, "neutral_local")
        anadir_partido(tabla, visitante, local, gv, gl, fecha, grupo, fuente, "neutral_visitante")

    equipos = {}
    for clave, reg in sorted(tabla.items()):
        reg["partidos"] = sorted(reg["partidos"], key=lambda p: p.get("fecha") or "")
        pj = max(int(reg["pj"]), 1)
        reg["tendencias"] = {
            "forma_5_pts": sum(p.get("puntos", 0) for p in reg["partidos"][-5:]),
            "forma_10_pts": sum(p.get("puntos", 0) for p in reg["partidos"][-10:]),
            "empates_pct": round(reg["e"] / pj * 100, 2),
            "goles_favor_por_partido": round(reg["gf"] / pj, 2),
            "goles_contra_por_partido": round(reg["gc"] / pj, 2),
            "puntos_por_partido": round(reg["pts"] / pj, 2),
        }
        reg["local"] = {"pj": pj, "pts": reg["pts"]}
        reg["visitante"] = {"pj": pj, "pts": reg["pts"]}
        reg["calidad"] = "media" if pj == 1 else "alta"
        reg["muestra_partidos"] = pj
        equipos[clave] = reg
    return {
        "version": "1.0",
        "generado_en": ahora_iso(),
        "total_resultados": len(data.get("resultados", [])),
        "total_equipos": len(equipos),
        "equipos": equipos,
        "descartados": descartados,
        "criterio_critico": "Sin memoria del Mundial 2026 no se deben presentar porcentajes como plenamente estudiados.",
    }


def main():
    data = cargar_json(RESULTADOS, {"version": "1.0", "resultados": []})
    candidatos = candidatos_desde_datos_existentes(data)
    fuentes = descargar_fuentes()
    nuevos = resultados_desde_jornadas() + resultados_desde_fuentes(candidatos, fuentes)
    actualizado, cambios = fusionar_resultados(data, nuevos)
    guardar_json(RESULTADOS, actualizado)
    cambios_jornadas, detalles_jornadas = sincronizar_jornadas_desde_mundial()
    memoria = construir_memoria(actualizado)
    guardar_json(MEMORIA, memoria)
    print(f"Mundial 2026 actualizado: {cambios} resultado(s) nuevo(s).")
    print(f"Jornadas sincronizadas desde Mundial 2026: {cambios_jornadas} cambio(s).")
    if detalles_jornadas:
        print("Detalles sincronizados: " + json.dumps(detalles_jornadas, ensure_ascii=False))
    print(f"Memoria Mundial 2026 actualizada: {memoria['total_equipos']} equipos, {memoria['total_resultados']} resultados.")


if __name__ == "__main__":
    main()
