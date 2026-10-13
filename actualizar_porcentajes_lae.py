"""Captura por jornada del % de apostantes LAE por signo y partido.

La Quiniela es pari-mutuel: para estimar el premio hay que saber que juega la
masa. eduardolosilla.es publica en su pagina de boletos los porcentajes
oficiales LAE de apuestas por signo, y actualizar_fuente_losilla.py ya los
guarda en data/memoria_ia/fuente_losilla.json (fuentes_detalle.lae por
partido) -pero ese archivo se sobreescribe cada ciclo con la jornada activa.
Este script los versiona por jornada en
data/memoria_ia/porcentajes_lae/<temporada>/jornada_N.json para que el
optimizador de EV del premio y sus backtests puedan reconstruir cualquier
jornada pasada. El subdirectorio de temporada evita la colision de numeros
de jornada entre temporadas (la numeracion de La Quiniela se reinicia).

Ademas, para jornadas ya cerradas, captura el ESCRUTINIO real de
eduardolosilla.es (recaudacion, bote y acertantes/premio por categoria), que
es la referencia contra la que se calibra el modelo de reparto.

Entrada manual de respaldo: si quiniela15.com/eduardolosilla no fueran
scrapeables, se puede crear a mano el JSON de la jornada con
"fuente": "manual" -este script NUNCA sobreescribe un archivo manual.

Modo --reconstruir-git: reconstruye los porcentajes de jornadas pasadas
desde el historial git de fuente_losilla.json, usando solo commits
ANTERIORES al primer partido de cada jornada (sin fuga de futuro).
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
FUENTE_LOSILLA = DATA / "memoria_ia" / "fuente_losilla.json"
SALIDA_BASE = DATA / "memoria_ia" / "porcentajes_lae"
JORNADAS = DATA / "jornadas"
RUTA_GIT_LOSILLA = "data/memoria_ia/fuente_losilla.json"

URL_ESCRUTINIO = "https://www.eduardolosilla.es/quiniela/ayudas/escrutinio/jornada_{jornada}"
HEADERS_WEB = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9",
}

SIGNOS = ("1", "X", "2")


def cargar_json(path, defecto=None):
    if not path.exists():
        return defecto if defecto is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return defecto if defecto is not None else {}


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def temporada_etiqueta(fecha):
    """"2026_2027" para cualquier fecha de esa temporada (julio corta)."""
    if fecha.month >= 7:
        return f"{fecha.year}_{fecha.year + 1}"
    return f"{fecha.year - 1}_{fecha.year}"


def ruta_porcentajes(jornada, etiqueta_temporada):
    return SALIDA_BASE / etiqueta_temporada / f"jornada_{int(jornada)}.json"


def porcentajes_desde_losilla(fuente_losilla):
    """Extrae {jornada, partidos:[{numero, local, visitante, porcentajes}]}
    del bloque de probabilidades de fuente_losilla.json (columna "lae" =
    porcentajes oficiales de apostantes). None si no hay datos LAE."""
    prob = (fuente_losilla or {}).get("probabilidades") or {}
    jornada = prob.get("jornada")
    if not isinstance(jornada, int):
        return None
    partidos = []
    for partido in prob.get("partidos") or []:
        numero = partido.get("numero")
        lae = (partido.get("fuentes_detalle") or {}).get("lae") or {}
        valores = {s: lae.get(s) for s in SIGNOS}
        if not isinstance(numero, int) or not (1 <= numero <= 14):
            continue
        if any(valores[s] is None for s in SIGNOS):
            continue
        partidos.append({
            "numero": numero,
            "local": partido.get("local"),
            "visitante": partido.get("visitante"),
            "porcentajes": {s: float(valores[s]) for s in SIGNOS},
        })
    if len(partidos) < 14:
        return None
    return {"jornada": jornada, "partidos": sorted(partidos, key=lambda p: p["numero"])}


def _numero_es(texto):
    """"3.500.149,50" -> 3500149.5 ; "1.033" -> 1033.0 ; None si no parsea."""
    limpio = re.sub(r"[^0-9,.]", "", str(texto or ""))
    if not limpio:
        return None
    limpio = limpio.replace(".", "").replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return None


def parsear_escrutinio_html(html):
    """Extrae recaudacion, bote y {categoria: {acertantes, premio_eur}} de la
    pagina de escrutinio de eduardolosilla.es. None si no encuentra la tabla."""
    soup = BeautifulSoup(html, "html.parser")
    texto = soup.get_text(" ", strip=True)
    categorias = {}
    for tr in soup.find_all("tr"):
        celdas = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(celdas) < 3:
            continue
        m = re.match(r"^\s*(1[0-5])\s+Acierto", celdas[0], re.IGNORECASE)
        if not m:
            continue
        acertantes = _numero_es(celdas[1])
        premio = _numero_es(celdas[2])
        if acertantes is None or premio is None:
            continue
        categorias[m.group(1)] = {
            "acertantes": int(acertantes),
            "premio_eur": round(premio, 2),
        }
    if len(categorias) < 5:
        return None
    resultado = {"categorias": categorias}
    m = re.search(r"Recaudaci[oó]n\s+([\d.,]+)\s*€?", texto, re.IGNORECASE)
    if m:
        resultado["recaudacion_eur"] = _numero_es(m.group(1))
    m = re.search(r"Bote\s+([\d.,]+)\s*€?", texto, re.IGNORECASE)
    if m:
        resultado["bote_eur"] = _numero_es(m.group(1))
    return resultado


def descargar_escrutinio(jornada):
    url = URL_ESCRUTINIO.format(jornada=int(jornada))
    try:
        r = requests.get(url, headers=HEADERS_WEB, timeout=25)
        if r.status_code != 200 or not r.text:
            print(f"Escrutinio J{jornada}: {url} devolvio {r.status_code}")
            return None
    except Exception as exc:
        print(f"Escrutinio J{jornada}: error consultando {url}: {exc}")
        return None
    datos = parsear_escrutinio_html(r.text)
    if datos:
        datos["fuente"] = "eduardolosilla.es/escrutinio"
        datos["capturado_en"] = datetime.now(timezone.utc).isoformat()
    return datos


def jornada_cerrada(jornada):
    data = cargar_json(JORNADAS / f"jornada_{int(jornada)}.json", {})
    partidos = [p for p in data.get("partidos") or [] if 1 <= int(p.get("num") or 0) <= 14]
    return len(partidos) == 14 and all(
        str(p.get("signo_oficial") or "").upper() in SIGNOS for p in partidos
    )


def fecha_primer_partido(jornada):
    data = cargar_json(JORNADAS / f"jornada_{int(jornada)}.json", {})
    fechas = []
    for p in data.get("partidos") or []:
        fecha = str(p.get("fecha") or "")
        if not re.match(r"^\d{4}-\d{2}-\d{2}", fecha):
            continue
        hora = str(p.get("hora") or "12:00")
        try:
            fechas.append(datetime.strptime(f"{fecha[:10]} {hora[:5]}", "%Y-%m-%d %H:%M"))
        except ValueError:
            fechas.append(datetime.strptime(fecha[:10], "%Y-%m-%d"))
    return min(fechas) if fechas else None


def guardar_porcentajes_jornada(captura, etiqueta_temporada, fuente, extra=None):
    """Escribe/actualiza el archivo de la jornada sin pisar entradas manuales.
    Devuelve True si escribio algo."""
    destino = ruta_porcentajes(captura["jornada"], etiqueta_temporada)
    existente = cargar_json(destino, {})
    if str(existente.get("fuente") or "") == "manual":
        return False
    registro = {
        "version": 1,
        "jornada": captura["jornada"],
        "temporada": etiqueta_temporada,
        "fuente": fuente,
        "actualizado_en": datetime.now(timezone.utc).isoformat(),
        "partidos": captura["partidos"],
    }
    if existente.get("escrutinio"):
        registro["escrutinio"] = existente["escrutinio"]
    if extra:
        registro.update(extra)
    guardar_json(destino, registro)
    return True


def capturar_jornada_activa():
    fuente = cargar_json(FUENTE_LOSILLA, {})
    captura = porcentajes_desde_losilla(fuente)
    if not captura:
        print("Sin porcentajes LAE completos en fuente_losilla.json; no se captura nada.")
        return None
    etiqueta = temporada_etiqueta(datetime.now())
    if guardar_porcentajes_jornada(captura, etiqueta, "eduardolosilla.es (columna LAE)"):
        print(f"Porcentajes LAE de la J{captura['jornada']} guardados en {etiqueta}.")
    else:
        print(f"J{captura['jornada']}: archivo manual existente, no se toca.")
    return captura["jornada"], etiqueta


def completar_escrutinios(etiqueta_temporada, maximo_descargas=4):
    """Para jornadas con porcentajes ya capturados y cerradas en
    data/jornadas, baja el escrutinio real si aun falta."""
    carpeta = SALIDA_BASE / etiqueta_temporada
    if not carpeta.exists():
        return
    descargas = 0
    for path in sorted(carpeta.glob("jornada_*.json")):
        if descargas >= maximo_descargas:
            break
        registro = cargar_json(path, {})
        jornada = registro.get("jornada")
        if not isinstance(jornada, int) or registro.get("escrutinio"):
            continue
        if not jornada_cerrada(jornada):
            continue
        escrutinio = descargar_escrutinio(jornada)
        descargas += 1
        if not escrutinio:
            continue
        registro["escrutinio"] = escrutinio
        guardar_json(path, registro)
        print(f"Escrutinio real de la J{jornada} capturado "
              f"(recaudacion={escrutinio.get('recaudacion_eur')}).")


def _git_show(commit, ruta):
    r = subprocess.run(
        ["git", "show", f"{commit}:{ruta}"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    return r.stdout if r.returncode == 0 else None


def reconstruir_desde_git(jornadas_objetivo=None):
    """Reconstruye porcentajes LAE de jornadas pasadas desde el historial git
    de fuente_losilla.json: para cada jornada, el ULTIMO commit anterior al
    primer partido (margen de 2h por husos horarios) -sin fuga de futuro."""
    log = subprocess.run(
        ["git", "log", "--format=%H %cI", "--", RUTA_GIT_LOSILLA],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    ).stdout.splitlines()
    commits = []
    for linea in log:
        trozos = linea.split()
        if len(trozos) == 2:
            commits.append((trozos[0], datetime.fromisoformat(trozos[1])))

    hechas = set()
    for commit, fecha_commit in commits:  # de mas nuevo a mas viejo
        raw = _git_show(commit, RUTA_GIT_LOSILLA)
        if not raw:
            continue
        try:
            datos = json.loads(raw.lstrip("﻿"))
        except Exception:
            continue
        captura = porcentajes_desde_losilla(datos)
        if not captura:
            continue
        jornada = captura["jornada"]
        if jornada in hechas:
            continue
        if jornadas_objetivo and jornada not in jornadas_objetivo:
            if jornadas_objetivo and jornada < min(jornadas_objetivo):
                break
            continue
        primer_partido = fecha_primer_partido(jornada)
        if primer_partido is None:
            continue
        # cierre aproximado: primer partido (hora local ES) tratado como UTC
        # menos 2h de margen -siempre anterior al cierre real de LAE.
        cierre = (primer_partido - timedelta(hours=2)).replace(tzinfo=timezone.utc)
        if fecha_commit > cierre:
            continue  # commit posterior al cierre: seguir hacia atras
        etiqueta = temporada_etiqueta(primer_partido)
        if guardar_porcentajes_jornada(
            captura, etiqueta, "git:fuente_losilla.json (columna LAE)",
            extra={"commit": commit[:12], "fecha_commit": fecha_commit.isoformat()},
        ):
            print(f"J{jornada} reconstruida desde {commit[:12]} ({fecha_commit:%Y-%m-%d %H:%M}).")
        hechas.add(jornada)
        if jornadas_objetivo and hechas >= set(jornadas_objetivo):
            break


def main():
    if "--reconstruir-git" in sys.argv:
        objetivo = None
        for arg in sys.argv[1:]:
            if re.match(r"^\d+(,\d+)*$", arg):
                objetivo = {int(x) for x in arg.split(",")}
        reconstruir_desde_git(objetivo)
        etiqueta = temporada_etiqueta(datetime.now())
        completar_escrutinios(etiqueta, maximo_descargas=20)
        return
    resultado = capturar_jornada_activa()
    etiqueta = resultado[1] if resultado else temporada_etiqueta(datetime.now())
    completar_escrutinios(etiqueta)


if __name__ == "__main__":
    main()
