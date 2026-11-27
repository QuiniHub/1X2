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
CLASIFICACIONES_OFICIALES = DATA / "clasificaciones_oficiales.json"

# La Quiniela reinicia su numeracion cada temporada (J76 de 25/26 -> J1 de
# 26/27), asi que data/jornadas/jornada_1.json ya NO es la J1 de 2025/2026
# -es la J1 de la temporada que arranco este dia. cargar_jornadas_locales()
# etiquetaba TODO lo que hubiera en esa carpeta como "2025/2026" a pelo, asi
# que la J1 real de 26/27 se colaba mezclada bajo la temporada equivocada
# (o desaparecia del historial "Aprendizaje" tal cual lo ve Marc en la web).
FECHA_INICIO_TEMPORADA_ACTUAL = "2026-08-15"

_MESES_ES = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
}


def _sin_acentos(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def fecha_iso_desde_texto(texto):
    """Extrae una fecha "D de MES de AAAA" (en español, con o sin acentos)
    del texto libre que trae el campo "fecha" de jornada_N.json y la
    devuelve en ISO (AAAA-MM-DD). None si no encuentra nada reconocible."""
    m = re.search(r"(\d{1,2})\s+de\s+([A-Za-zÀ-ÿ]+)\s+de\s+(\d{4})", texto or "")
    if not m:
        return None
    dia, mes, anio = m.groups()
    mes_num = _MESES_ES.get(_sin_acentos(mes).lower())
    if not mes_num:
        return None
    return f"{anio}-{mes_num}-{int(dia):02d}"


def temporada_de_jornada_local(datos, numero):
    """Temporada ('2026/2027') de un jornada_N.json por su FECHA real.

    Auditoria 26/11 (hallazgo 62): se comparaba con una fecha escrita a mano
    (FECHA_INICIO_TEMPORADA_ACTUAL = '2026-08-15'), que en la 27/28 habria
    metido dos temporadas bajo la misma etiqueta. Ahora se usa el modulo comun
    cronologia_jornadas. Sin fecha reconocible -> None.
    """
    import cronologia_jornadas

    fecha = cronologia_jornadas.fecha_real_jornada(datos) if isinstance(datos, dict) else None
    if fecha is None:
        return None
    etiqueta = cronologia_jornadas.temporada_de_fecha(fecha, numero)
    return etiqueta.replace("_", "/") if etiqueta else None


def temporada_actual_detectada():
    try:
        datos = json.loads(CLASIFICACIONES_OFICIALES.read_text(encoding="utf-8"))
    except Exception:
        return "2026/2027"
    return datos.get("temporada_detectada") or "2026/2027"

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
    """Carga las jornadas ya guardadas en data/jornadas/, etiquetando cada
    una con su temporada REAL (por fecha, no a pelo) -ver comentario junto
    a FECHA_INICIO_TEMPORADA_ACTUAL."""
    temporada_nueva = temporada_actual_detectada()
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

        # El Pleno al 15 vive en un campo separado (d["pleno15"]) en los
        # archivos de data/jornadas/*.json, NO dentro de "partidos" -sin
        # esto, cargar_jornadas_locales() nunca lo veia (confirmado: 0
        # partidos con num=15 en todo historico_quinielas_lae.json pese a
        # que parsear_jornada() -la otra fuente, webprincipal.com- si lo
        # soporta). El resultado real del Pleno es el marcador ("1-0"),
        # no un signo 1/X/2, igual que ya guarda parsear_jornada().
        pleno15 = d.get("pleno15") or {}
        if pleno15.get("local") and pleno15.get("visitante"):
            entrada_p15 = {
                "num": 15,
                "local": pleno15.get("local", ""),
                "visitante": pleno15.get("visitante", ""),
                "resultado": pleno15.get("resultado", ""),
                "fecha": pleno15.get("fecha", ""),
            }
            signo_p15 = str(pleno15.get("signo_oficial") or "").strip()
            if signo_p15 and signo_p15 != "Pendiente":
                entrada_p15["signo_oficial"] = signo_p15
            partidos.append(entrada_p15)

        signos_str = "".join(
            p.get("signo_oficial", "?") for p in partidos[:14]
        )
        fecha_texto = d.get("fecha", "")
        numero_jornada = int(d.get("jornada") or re.search(r"\d+", path.stem).group())
        # Sin fecha reconocible cae en 2025/2026 por seguridad (ficheros antiguos).
        temporada = temporada_de_jornada_local(d, numero_jornada) or "2025/2026"
        es_temporada_nueva = temporada > "2025/2026"
        jornadas.append({
            "jornada": numero_jornada,
            "temporada": temporada,
            "temporada_key": "actual" if es_temporada_nueva else "2025",
            "fecha": fecha_texto,
            "fuente": d.get("fuente", str(path)),
            "partidos": partidos,
            "signos_14": signos_str,
        })
    return jornadas


# ── Main ─────────────────────────────────────────────────────────────────────

def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# Una temporada completa de La Quiniela tiene 60-76 jornadas; con menos de
# este minimo el bloque guardado no se da por completo y se vuelve a descargar.
MIN_JORNADAS_TEMPORADA_CERRADA = 50


def cargar_previo(path=None):
    """Historico ya guardado ({} si no existe o no se puede leer)."""
    path = Path(path or SALIDA)
    try:
        datos = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return datos if isinstance(datos, dict) else {}


def jornadas_previas(previo, nombre):
    bloque = ((previo or {}).get("temporadas") or {}).get(nombre)
    if isinstance(bloque, dict) and isinstance(bloque.get("jornadas"), list):
        return bloque["jornadas"]
    return []


def temporada_cerrada_en_cache(previo, nombre):
    """Una temporada ya terminada no cambia: si esta guardada completa no hay
    que volver a pedirla (eran ~225 POST a webprincipal en CADA ciclo)."""
    return len(jornadas_previas(previo, nombre)) >= MIN_JORNADAS_TEMPORADA_CERRADA


def main():
    print("=== Historial La Quiniela LAE — 3 temporadas ===\n")

    # Auditoria 26/11 (hallazgos 34 y 63): las temporadas cerradas se leen del
    # fichero ya guardado (sin red) y, si una descarga falla, se conserva lo que
    # habia: nunca se pierde una temporada por un fallo de webprincipal.
    previo = cargar_previo()

    historico = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "fuente": "webprincipal.com + data/jornadas/ (local)",
        "temporadas": {},
    }

    # ── Temporadas historicas via webprincipal ────────────────────────────────
    for key, nombre in list(TEMPORADAS.items())[:-1]:  # 2023 y 2024
        print(f"Temporada {nombre} (webprincipal key={key}):")
        if temporada_cerrada_en_cache(previo, nombre):
            historico["temporadas"][nombre] = previo["temporadas"][nombre]
            print(f"  en cache ({len(jornadas_previas(previo, nombre))} jornadas): no se descarga\n")
            continue
        try:
            ids = ids_jornadas(key)
        except Exception as e:
            print(f"  ERROR obteniendo lista: {e}")
            if jornadas_previas(previo, nombre):
                historico["temporadas"][nombre] = previo["temporadas"][nombre]
                print("  se conserva el dato previo")
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

        if len(jornadas) < len(jornadas_previas(previo, nombre)):
            # Descarga parcial (errores de red a media lista): vale mas lo previo.
            historico["temporadas"][nombre] = previo["temporadas"][nombre]
            print(f"  descarga incompleta ({len(jornadas)} jornadas): se conserva el dato previo\n")
            continue

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

    # ── Temporada 2025/2026: intentar webprincipal primero, luego local ───────
    print("Temporada 2025/2026:")
    jornadas_2526 = []
    try:
        if temporada_cerrada_en_cache(previo, "2025/2026"):
            # Temporada terminada y ya guardada: base = lo guardado, sin red.
            # (Los ficheros locales de 25/26 se siguen fusionando mas abajo.)
            jornadas_2526 = list(jornadas_previas(previo, "2025/2026"))
            print(f"  en cache ({len(jornadas_2526)} jornadas): no se descarga")
            ids = []
        else:
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

    # webprincipal solo conoce temporadas ya cerradas -no tiene ni idea de
    # la temporada en curso. Los archivos locales de data/jornadas/ son la
    # unica fuente para eso, y cargar_jornadas_locales() ya etiqueta cada
    # jornada con su temporada real (por fecha): separarlas aqui evita que
    # la J1 de la temporada nueva se cuele mezclada bajo "2025/2026".
    locales = cargar_jornadas_locales()
    locales_2526 = [j for j in locales if j["temporada"] == "2025/2026"]
    # Solo temporadas POSTERIORES: un fichero local anterior a la 25/26 se
    # mezclaria por numero con el bloque de webprincipal de su temporada.
    locales_actual = [j for j in locales if j["temporada"] > "2025/2026"]
    locales_antiguas = sorted({j["temporada"] for j in locales if j["temporada"] < "2025/2026"})
    if locales_antiguas:
        print(f"  AVISO: se ignoran jornadas locales de temporadas anteriores: {locales_antiguas}")

    if not jornadas_2526 and not locales_2526 and jornadas_previas(previo, "2025/2026"):
        jornadas_2526 = list(jornadas_previas(previo, "2025/2026"))
        print("  sin datos nuevos: se conserva el dato previo")

    if len(jornadas_2526) < len(locales_2526):
        ids_web = {j["jornada"] for j in jornadas_2526}
        for jl in locales_2526:
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

    # ── Temporadas posteriores a la 25/26: solo archivos locales, webprincipal no las tiene ──
    # Una por una (en la 27/28 conviviran ficheros de 26/27 y de 27/28). Las
    # jornadas que ya no estan en data/jornadas (el numero se reutiliza cada
    # temporada) se conservan del historico previo.
    for nombre_actual in sorted({j["temporada"] for j in locales_actual}):
        por_numero = {j["jornada"]: j for j in jornadas_previas(previo, nombre_actual) if isinstance(j, dict)}
        for j in locales_actual:
            if j["temporada"] == nombre_actual:
                por_numero[j["jornada"]] = j
        locales_actual_temporada = sorted(por_numero.values(), key=lambda x: x["jornada"])
        _guardar_temporada_local(historico, nombre_actual, locales_actual_temporada)

    guardar_o_conservar(historico, previo)


def _guardar_temporada_local(historico, nombre_actual, locales_actual):
    if locales_actual:
        stats_actual = calcular_stats(locales_actual)
        historico["temporadas"][nombre_actual] = {
            "temporada": nombre_actual,
            "fuente": "local (data/jornadas/)",
            "jornadas": locales_actual,
            "estadisticas": stats_actual,
        }
        f = stats_actual["frecuencias_signos"]
        print(f"Temporada {nombre_actual}:")
        print(f"  -> {len(locales_actual)} jornadas | 1={f['1']}% X={f['X']}% 2={f['2']}%\n")



def guardar_o_conservar(historico, previo):
    # Ninguna temporada que ya estaba guardada puede desaparecer.
    for nombre, bloque in ((previo.get("temporadas") or {}).items()):
        if nombre not in historico["temporadas"] and jornadas_previas(previo, nombre):
            historico["temporadas"][nombre] = bloque
            print(f"Temporada {nombre}: no se pudo recargar, se conserva el dato previo")

    if not historico["temporadas"]:
        print("AVISO: no se ha cargado ninguna temporada; no se escribe nada.")
        return 0

    guardar_json(SALIDA, historico)
    total = sum(len(t["jornadas"]) for t in historico["temporadas"].values())
    total_partidos = sum(
        int((t.get("estadisticas") or {}).get("partidos_totales") or 0)
        for t in historico["temporadas"].values()
    )
    print(f"Guardado en {SALIDA}")
    print(f"Total jornadas: {total} | Total partidos con signo: {total_partidos}")


if __name__ == "__main__":
    main()
