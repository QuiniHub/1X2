"""Descarga el historial completo de jornadas de La Quiniela LAE.

Fuente: webprincipal.com/quiniela/estadisticas/ (sin autenticacion, datos LAE oficiales)
  - leerresultadosanterioresquiniela.php  -> lista de jornadas por temporada
  - partidosjornada.php                   -> JSON de cada jornada (equipos, resultado, signo, P15)

Temporadas descargadas: 2023/24, 2024/25, 2025/26
Salida: data/memoria_ia/historico_quinielas_lae.json
"""

import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT  = Path(__file__).resolve().parent
DATA  = ROOT / "data"
JORNADAS_DIR = DATA / "jornadas"
SALIDA = DATA / "memoria_ia" / "historico_quinielas_lae.json"

BASE = "https://www.webprincipal.com/quiniela/estadisticas/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0",
    "Referer":    "https://www.webprincipal.com/quiniela/resultadosanterioresquiniela.php",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "*/*",
}

# webprincipal usa el año de INICIO de la temporada
# 2023 = 2023/24 | 2024 = 2024/25 | 2025 = 2025/26
TEMPORADAS = {
    "2023": "2023/2024",
    "2024": "2024/2025",
    "2025": "2025/2026",
}


# ── HTTP ──────────────────────────────────────────────────────────────────────

def post(endpoint, data, retries=3):
    url = BASE + endpoint
    body = urllib.parse.urlencode(data).encode("utf-8")
    for intento in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers=HEADERS, method="POST")
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            if intento == retries - 1:
                raise
            time.sleep(1.5)


# ── Parsing ───────────────────────────────────────────────────────────────────

def ids_jornadas(temporada_key):
    """Devuelve lista de IDs de jornada para la temporada dada."""
    html = post("leerresultadosanterioresquiniela.php",
                {"temporadaresultados": temporada_key})
    # data-temporada="2024" data-jornada="5" (o sin comillas)
    pares = re.findall(
        r'data-temporada=["\']?(\d+)["\']?\s+data-jornada=["\']?(\d+)["\']?',
        html,
    )
    # Mantener orden original (el HTML los devuelve de mayor a menor, invertir)
    jornada_ids = [int(j) for t, j in pares if t == temporada_key]
    return list(reversed(jornada_ids))


def parsear_jornada(raw_json, temporada_key, jornada_id, nombre_temp):
    try:
        d = json.loads(raw_json)
    except Exception:
        return None
    partidos_raw = d.get("partidos", [])
    if not partidos_raw or len(partidos_raw) < 14:
        return None

    partidos = []
    for i, p in enumerate(partidos_raw[:15]):
        num = i + 1
        signo = (p.get("signoq") or "").strip().upper()
        resultado = (p.get("resultadoq") or "").strip()
        equipo1 = (p.get("equipo1") or "").strip()
        equipo2 = (p.get("equipo2") or "").strip()
        fecha_txt = re.sub(r"<[^>]+>", " ", p.get("fechapartido") or "").strip()

        partido = {
            "num": num,
            "local": equipo1,
            "visitante": equipo2,
            "resultado": resultado,
            "fecha": fecha_txt,
        }

        if num <= 14:
            if signo in ("1", "X", "2"):
                partido["signo_oficial"] = signo
            for k in ("porc1", "porcX", "porc2"):
                v = p.get(k)
                if v is not None:
                    try:
                        partido[k] = round(float(v), 1)
                    except (TypeError, ValueError):
                        pass
        else:
            # P15 — signogolesq tiene 2 chars: goles local + goles visitante
            goles = (p.get("signogolesq") or "").strip()
            if goles:
                partido["goles_local"]    = goles[0] if len(goles) > 0 else ""
                partido["goles_visitante"] = goles[1] if len(goles) > 1 else ""
                partido["signo_p15"] = goles
            if signo in ("1", "X", "2"):
                partido["signo_oficial"] = signo

        partidos.append(partido)

    signos_14 = "".join(
        p.get("signo_oficial", "?") for p in partidos[:14]
    )

    return {
        "jornada": int(d.get("jornada") or jornada_id),
        "temporada": nombre_temp,
        "temporada_key": temporada_key,
        "fecha": d.get("fecha") or "",
        "fuente": BASE + "partidosjornada.php",
        "partidos": partidos,
        "signos_14": signos_14,
    }


# ── Estadísticas ──────────────────────────────────────────────────────────────

def calcular_stats(jornadas):
    total_partidos = 0
    signos = {"1": 0, "X": 0, "2": 0}
    por_posicion = {str(i): {"1": 0, "X": 0, "2": 0} for i in range(1, 15)}

    for j in jornadas:
        for p in j.get("partidos", [])[:14]:
            s = p.get("signo_oficial", "")
            if s in signos:
                signos[s] += 1
                total_partidos += 1
                pos = str(p.get("num", ""))
                if pos in por_posicion:
                    por_posicion[pos][s] = por_posicion[pos].get(s, 0) + 1

    freq = {k: round(v / total_partidos * 100, 1) if total_partidos else 0
            for k, v in signos.items()}
    return {
        "jornadas": len(jornadas),
        "partidos_totales": total_partidos,
        "frecuencias_signos": freq,
        "frecuencias_por_posicion": por_posicion,
    }


# ── Complemento temporada actual desde archivos locales ─────────────────────

def cargar_jornadas_locales():
    """Carga las jornadas de 2025/26 ya guardadas en data/jornadas/."""
    jornadas = []
    for path in sorted(
        JORNADAS_DIR.glob("jornada_*.json"),
        key=lambda p: int(re.search(r"\d+", p.stem).group()),
    ):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        partidos_raw = d.get("partidos", [])
        partidos = []
        signos_str = ""
        for p in partidos_raw:
            oficial = str(p.get("signo_oficial") or "").strip().upper()
            num = p.get("num", len(partidos) + 1)
            partido = {
                "num": num,
                "local": p.get("local", ""),
                "visitante": p.get("visitante", ""),
                "resultado": p.get("resultado", ""),
                "fecha": p.get("fecha", ""),
            }
            if oficial in ("1", "X", "2"):
                partido["signo_oficial"] = oficial
            partidos.append(partido)
        if len(partidos) < 10:
            continue
        signos_str = "".join(
            p.get("signo_oficial", "?") for p in partidos[:14]
        )
        jornadas.append({
            "jornada": int(d.get("jornada") or re.search(r"\d+", path.stem).group()),
            "temporada": "2025/2026",
            "temporada_key": "2025",
            "fecha": d.get("fecha", ""),
            "fuente": d.get("fuente", str(path)),
            "partidos": partidos,
            "signos_14": signos_str,
        })
    return jornadas


# ── Main ─────────────────────────────────────────────────────────────────────

def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    print("=== Historial La Quiniela LAE — 3 temporadas ===\n")

    historico = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "fuente": "webprincipal.com + data/jornadas/ (local)",
        "temporadas": {},
    }

    # ── Temporadas historicas via webprincipal ────────────────────────────────
    for key, nombre in list(TEMPORADAS.items())[:-1]:  # 2023 y 2024
        print(f"Temporada {nombre} (webprincipal key={key}):")
        try:
            ids = ids_jornadas(key)
        except Exception as e:
            print(f"  ERROR obteniendo lista: {e}")
            continue
        print(f"  {len(ids)} jornadas encontradas")

        jornadas = []
        for jornada_id in ids:
            try:
                raw = post("partidosjornada.php",
                           {"temporada": key, "jornada": str(jornada_id)})
                j = parsear_jornada(raw, key, jornada_id, nombre)
                if j:
                    jornadas.append(j)
                    print(f"  J{jornada_id:>3}: {j['fecha']:<12} | {j['signos_14']}")
                else:
                    print(f"  J{jornada_id:>3}: sin datos suficientes")
            except Exception as e:
                print(f"  J{jornada_id:>3}: ERROR {e}")
            time.sleep(0.15)  # respetar rate-limit

        if jornadas:
            stats = calcular_stats(jornadas)
            historico["temporadas"][nombre] = {
                "temporada": nombre,
                "fuente": "webprincipal.com",
                "jornadas": jornadas,
                "estadisticas": stats,
            }
            f = stats["frecuencias_signos"]
            print(f"  -> {len(jornadas)} jornadas | 1={f['1']}% X={f['X']}% 2={f['2']}%\n")

    # ── Temporada actual: intentar webprincipal primero, luego local ──────────
    print("Temporada 2025/2026:")
    jornadas_2526 = []
    try:
        ids = ids_jornadas("2025")
        print(f"  {len(ids)} jornadas en webprincipal")
        for jornada_id in ids:
            try:
                raw = post("partidosjornada.php",
                           {"temporada": "2025", "jornada": str(jornada_id)})
                j = parsear_jornada(raw, "2025", jornada_id, "2025/2026")
                if j:
                    jornadas_2526.append(j)
                    print(f"  J{jornada_id:>3}: {j['fecha']:<12} | {j['signos_14']}")
            except Exception as e:
                print(f"  J{jornada_id:>3}: ERROR {e}")
            time.sleep(0.15)
    except Exception as e:
        print(f"  webprincipal error ({e}), usando archivos locales")
        jornadas_2526 = cargar_jornadas_locales()
        print(f"  {len(jornadas_2526)} jornadas desde data/jornadas/")

    # Complementar con locales si webprincipal dio menos
    if len(jornadas_2526) < len(list(JORNADAS_DIR.glob("jornada_*.json"))):
        locales = cargar_jornadas_locales()
        ids_web = {j["jornada"] for j in jornadas_2526}
        for jl in locales:
            if jl["jornada"] not in ids_web:
                jornadas_2526.append(jl)
        jornadas_2526.sort(key=lambda x: x["jornada"])

    if jornadas_2526:
        stats = calcular_stats(jornadas_2526)
        historico["temporadas"]["2025/2026"] = {
            "temporada": "2025/2026",
            "fuente": "webprincipal.com + local",
            "jornadas": jornadas_2526,
            "estadisticas": stats,
        }
        f = stats["frecuencias_signos"]
        print(f"  -> {len(jornadas_2526)} jornadas | 1={f['1']}% X={f['X']}% 2={f['2']}%\n")

    guardar_json(SALIDA, historico)
    total = sum(len(t["jornadas"]) for t in historico["temporadas"].values())
    total_partidos = sum(
        t["estadisticas"]["partidos_totales"] for t in historico["temporadas"].values()
    )
    print(f"Guardado en {SALIDA}")
    print(f"Total jornadas: {total} | Total partidos con signo: {total_partidos}")


if __name__ == "__main__":
    main()
