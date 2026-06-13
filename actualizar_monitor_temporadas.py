import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import requests
except Exception:
    requests = None


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
TEMPORADAS = DATA / "temporadas"
SALIDA = TEMPORADAS / "monitor_temporadas.json"

HEADERS = {
    "User-Agent": "QuinielaIAPro/1.0 (+https://github.com/QuiniHub/1X2)",
    "Accept-Language": "es-ES,es;q=0.9",
}

LIGAS = {
    "primera": "SP1.csv",
    "segunda": "SP2.csv",
}


def ahora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def temporada_inicio_actual(fecha=None):
    fecha = fecha or datetime.now()
    return fecha.year if fecha.month >= 8 else fecha.year - 1


def temporada_info(inicio):
    return {
        "inicio": inicio,
        "fin": inicio + 1,
        "label": f"{inicio}/{inicio + 1}",
        "slug": f"{inicio}_{inicio + 1}",
        "football_data": f"{inicio % 100:02d}{(inicio + 1) % 100:02d}",
        "laliga": f"{inicio}-{(inicio + 1) % 100:02d}",
    }


def descargar(url):
    if requests is not None:
        respuesta = requests.get(url, headers=HEADERS, timeout=20)
        return respuesta.status_code, respuesta.text
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=20) as respuesta:
            return respuesta.status, respuesta.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        return exc.code, ""
    except URLError:
        return 0, ""


def revisar_football_data(info):
    resultado = {}
    detectada = False
    for liga, archivo in LIGAS.items():
        url = f"https://www.football-data.co.uk/mmz4281/{info['football_data']}/{archivo}"
        status, texto = descargar(url)
        filas = []
        if status == 200 and texto.strip():
            try:
                filas = list(csv.DictReader(io.StringIO(texto)))
            except Exception:
                filas = []
        equipos = set()
        partidos_con_fecha = 0
        for fila in filas:
            local = (fila.get("HomeTeam") or "").strip()
            visitante = (fila.get("AwayTeam") or "").strip()
            if local and visitante:
                equipos.add(local)
                equipos.add(visitante)
                partidos_con_fecha += 1
        detectada = detectada or partidos_con_fecha > 0
        resultado[liga] = {
            "url": url,
            "http_status": status,
            "filas": len(filas),
            "partidos_con_equipos": partidos_con_fecha,
            "equipos_detectados": len(equipos),
        }
    return detectada, resultado


def revisar_laliga(info):
    resultado = {}
    detectada = False
    marcadores_equipos = {
        "primera": ("Real Madrid", "Barcelona", "Athletic", "Atlético", "Valencia", "Sevilla"),
        "segunda": ("Almería", "Málaga", "Racing", "Deportivo", "Las Palmas", "Granada"),
    }
    for liga, slug in {
        "primera": "laliga-easports",
        "segunda": "laliga-hypermotion",
    }.items():
        url = f"https://www.laliga.com/{slug}/resultados/{info['laliga']}/jornada-1"
        status, texto = descargar(url)
        texto_min = texto.lower()
        tiene_temporada = info["laliga"] in texto or info["label"] in texto
        equipos_en_html = sum(1 for equipo in marcadores_equipos[liga] if equipo.lower() in texto_min)
        tiene_partidos = equipos_en_html >= 2
        detectada = detectada or (status == 200 and tiene_temporada and tiene_partidos)
        resultado[liga] = {
            "url": url,
            "http_status": status,
            "temporada_en_html": bool(tiene_temporada),
            "equipos_marcadores_detectados": equipos_en_html,
            "indicios_calendario": bool(tiene_partidos),
        }
    return detectada, resultado


def crear_resumen_temporada_detectada(info, fuentes):
    destino = TEMPORADAS / info["slug"] / "resumen_temporada.json"
    if destino.exists():
        return
    guardar_json(destino, {
        "version": "1.0",
        "generado_en": ahora_iso(),
        "temporada": info["label"],
        "estado": "detectada_pendiente_de_carga_completa",
        "fuentes_detectadas": fuentes,
        "nota": "La automatizacion ya ha detectado fuentes para la nueva temporada; se cargaran calendarios y estadisticas cuando las fuentes publiquen datos suficientes.",
    })


def main():
    inicio_actual = temporada_inicio_actual()
    actual = temporada_info(inicio_actual)
    siguiente = temporada_info(inicio_actual + 1)

    fd_detectada, fd = revisar_football_data(siguiente)
    laliga_detectada, laliga = revisar_laliga(siguiente)
    detectada = fd_detectada or laliga_detectada

    salida = {
        "generado_en": ahora_iso(),
        "temporada_activa_estimada": actual,
        "temporada_siguiente_vigilada": siguiente,
        "estado": "temporada_siguiente_detectada" if detectada else "esperando_publicacion",
        "football_data": fd,
        "laliga": laliga,
    }
    guardar_json(SALIDA, salida)
    if detectada:
        crear_resumen_temporada_detectada(siguiente, {"football_data": fd, "laliga": laliga})
    print(f"Monitor temporadas: {siguiente['label']} -> {salida['estado']}.")


if __name__ == "__main__":
    main()
