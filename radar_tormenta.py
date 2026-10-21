"""Radar de Tormenta (peticion de Marc, 21/10/2026) — MODO SOMBRA.

La investigacion mundial y nuestros tres estudios propios dicen que la
sorpresa concreta (el "tercero": gana el signo que menos masa LAE lleva) NO
se predice. Lo que si dejo el estudio prerregistrado de terceros de España
(estudio_terceros_espana.py, J1-14 de 2026-27, DECISION_LOG 21/10/2026) es
donde VIVE la tormenta:

  - 15 de los 25 terceros cayeron en partidos SIN DUEÑO (favorito del motor
    por debajo del 45%): 21,4% de tasa dentro vs 14,5% fuera (x1,48, la unica
    hipotesis que rozo el umbral; quedo INDETERMINADA y pasa a seguimiento
    prospectivo — este radar ES ese seguimiento).
  - El tercero NUNCA fue X (0 de 25): es el 2 del visitante despreciado (19)
    o el 1 del local al que nadie respeta (6). El "signo del rayo" del radar
    es siempre el signo NO-X con menor masa.
  - Hay EQUIPOS DEL CAOS con nombre: Eibar femenino (4 de los 5 terceros de
    Liga F), Levante en casa (2 de los 6 "unos"), Real Oviedo y Granada a
    domicilio (3 apariciones cada uno), Athletic masculino (3).

ADVERTENCIA DE CIRCULARIDAD (honesta, prerregistrada): la lista de equipos
del caos y el umbral "sin dueño" salen de las jornadas 1-14 de 2026-27. El
marcador de este radar solo puntua jornadas POSTERIORES a su despliegue
(su bloque se publica pre-cierre, como La Valiente): examen con datos nuevos,
jamas con el mismo examen del que salio la lista.

QUE PUBLICA: bloque "radar_tormenta" en ultima_prediccion.json (y espejo
jornada_N.json) con hasta 3 partidos en "zona de tormenta", cada uno con su
signo del rayo. La web lo pinta como insignia sobre el partido y el marcador
vive en el Laboratorio. NO entra en ningun boleto: sombra pura.

PRERREGISTRO del marcador (data/memoria_ia/marcador_radar_tormenta.json):
por jornada cerrada con bloque publicado y masa LAE versionada se registra
cuantos terceros reales cayeron dentro/fuera de la zona y cuantos rayos
(signo exacto) acertaron. Veredicto tras >=10 jornadas evaluadas:
  - CANDIDATA si tasa de terceros dentro >= 1,5x la tasa fuera y >= 5
    terceros capturados en zona;
  - DESPIDO si la tasa dentro <= la tasa fuera;
  - EN_PRUEBA en medio.
Umbrales y lista de caos NO se tocan sin nueva entrada en DECISION_LOG.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from optimizador_ev_premio import cargar_json, guardar_json, porcentajes_masa
from actualizar_porcentajes_lae import temporada_etiqueta

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
FUENTE_LOSILLA = DATA / "memoria_ia" / "fuente_losilla.json"
PREDICCIONES_DIR = DATA / "predicciones"
JORNADAS_DIR = DATA / "jornadas"
PORCENTAJES_DIR = DATA / "memoria_ia" / "porcentajes_lae"
MARCADOR = DATA / "memoria_ia" / "marcador_radar_tormenta.json"

# --- Umbrales prerregistrados (estudio_terceros_espana.py; no tocar sin
# nueva entrada en DECISION_LOG) ---
UMBRAL_SIN_DUENO = 45.0
PESO_SIN_DUENO = 2
PESO_CAOS = 2
SCORE_MIN = 2
MAX_ZONA = 3

# Equipos del caos (J1-14 2026-27). "femenino" True exige "(f)" en el nombre;
# False lo excluye. "solo" restringe el contexto que mostro el patron.
EQUIPOS_CAOS = (
    {"clave": "eibar", "femenino": True, "solo": None,
     "motivo": "Eibar F: 4 de los 5 terceros de Liga F"},
    {"clave": "levante", "femenino": False, "solo": "casa",
     "motivo": "Levante en casa: 2 'unos' que nadie vio"},
    {"clave": "oviedo", "femenino": False, "solo": "fuera",
     "motivo": "Oviedo fuera: gana cuando nadie lo mira"},
    {"clave": "granada", "femenino": False, "solo": "fuera",
     "motivo": "Granada fuera: 2 victorias de tercero"},
    {"clave": "athletic", "femenino": False, "solo": None,
     "motivo": "Athletic: 3 terceros, equipo bipolar 26/27"},
)

AVISO_SOMBRA = (
    "Experimental, MODO SOMBRA: el radar señala la zona donde es mas probable "
    "que caiga el resultado que nadie ve (nunca el partido exacto; eso no lo "
    "predice nadie, ver INVESTIGACION_SORPRESAS.md). No entra en ningun boleto "
    "hasta graduarse con el marcador prerregistrado."
)

CRITERIO = (
    "Hasta 3 partidos con score >= 2: +2 si el favorito del motor esta por "
    "debajo del 45% (partido sin dueño, unica señal que rozo umbral en el "
    "estudio de terceros J1-14) y +2 por cada equipo del caos en su contexto "
    "(Eibar F; Levante en casa; Oviedo y Granada fuera; Athletic). El signo "
    "del rayo es el signo NO-X con menor masa LAE (los 25 terceros de J1-14 "
    "fueron 19 doses y 6 unos: ninguno fue X)."
)


def _norm(nombre):
    s = unicodedata.normalize("NFKD", str(nombre or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def _es_femenino(nombre):
    return "(f)" in _norm(nombre)


def equipos_caos_en_partido(local, visitante):
    """Motivos de caos aplicables al partido, en su contexto casa/fuera."""
    motivos = []
    for lado, nombre in (("casa", local), ("fuera", visitante)):
        n = _norm(nombre)
        for e in EQUIPOS_CAOS:
            if e["clave"] not in n:
                continue
            if e["femenino"] != _es_femenino(nombre):
                continue
            if e["solo"] and e["solo"] != lado:
                continue
            motivos.append(f"{nombre}: {e['motivo']}")
    return motivos


def signo_del_rayo(probs, masa_partido):
    """Signo NO-X con menor masa LAE (fallback: menor prob del motor)."""
    fuente = masa_partido if masa_partido else probs
    return min(("1", "2"), key=lambda s: float(fuente.get(s, 100.0)))


def puntuar_partido(partido, masa_partido):
    probs = {k: float(v) for k, v in (partido.get("probabilidades") or {}).items()
             if k in ("1", "X", "2")}
    if len(probs) != 3:
        return None
    prob_top = max(probs.values())
    score = 0
    motivos = []
    if prob_top < UMBRAL_SIN_DUENO:
        score += PESO_SIN_DUENO
        motivos.append(f"partido sin dueño (favorito {prob_top:.0f}%)")
    for m in equipos_caos_en_partido(partido.get("local"), partido.get("visitante")):
        score += PESO_CAOS
        motivos.append(m)
    rayo = signo_del_rayo(probs, masa_partido)
    return {
        "num": partido.get("num"),
        "local": partido.get("local"),
        "visitante": partido.get("visitante"),
        "score": score,
        "motivos": motivos,
        "prob_top": round(prob_top, 1),
        "signo_rayo": rayo,
        "masa_rayo": round(float(masa_partido.get(rayo)), 1) if masa_partido else None,
        "prob_motor_rayo": round(probs[rayo], 1),
    }


def construir_bloque_radar(prediccion, fuente_losilla=None):
    """Nucleo del bloque `radar_tormenta` (testeable, sin tocar disco)."""
    jornada = prediccion.get("jornada")
    base = {
        "modo": "sombra",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "jornada": jornada,
        "criterio": CRITERIO,
        "aviso": AVISO_SOMBRA,
    }
    partidos = sorted(
        [p for p in prediccion.get("partidos") or []
         if isinstance(p.get("num"), int) and 1 <= p["num"] <= 14],
        key=lambda p: p["num"],
    )
    if len(partidos) != 14 or any(not p.get("probabilidades") for p in partidos):
        return {**base, "estado": "no_disponible", "zona": [],
                "motivo": "La prediccion no tiene los 14 partidos con probabilidades."}
    masa, fuente_masa = porcentajes_masa(jornada, fuente_losilla or {})
    base["fuente_masa"] = fuente_masa
    evaluados = []
    for p in partidos:
        fila = puntuar_partido(p, (masa or {}).get(p["num"]) or {})
        if fila:
            evaluados.append(fila)
    zona = sorted(
        [f for f in evaluados if f["score"] >= SCORE_MIN],
        key=lambda f: (-f["score"], f["prob_top"], f["num"]),
    )[:MAX_ZONA]
    if not zona:
        return {**base, "estado": "sin_tormenta", "zona": [],
                "motivo": "Ningun partido alcanza score 2: jornada sin zona clara "
                          "de tormenta. Declararlo es parte del diseño."}
    return {**base, "estado": "ok", "zona": zona}


# ---------------------------------------------------------------------------
# Marcador prospectivo (patron marcador_valiente)
# ---------------------------------------------------------------------------

def _pares(partidos):
    return {(_norm(p.get("local")), _norm(p.get("visitante")))
            for p in partidos if p.get("local") and p.get("visitante")}


def _misma_jornada(snapshot_partidos, jornada_partidos):
    """Guarda anti-mezcla de temporadas: los fixtures deben coincidir (>=10
    de 14 por nombres normalizados); la numeracion J se reinicia cada año."""
    return len(_pares(snapshot_partidos) & _pares(jornada_partidos)) >= 10


def evaluar_jornada_cerrada(bloque, snapshot_partidos, jornada_partidos, masa_jornada):
    """Metrica de concentracion de una jornada cerrada. None si no evaluable."""
    oficiales = {}
    for p in jornada_partidos:
        num = p.get("num") or p.get("numero")
        if p.get("signo_oficial") in ("1", "X", "2") and isinstance(num, int):
            oficiales[num] = p["signo_oficial"]
    if len(oficiales) < 14 or not _misma_jornada(snapshot_partidos, jornada_partidos):
        return None
    if not masa_jornada:
        return None
    nums_zona = {z["num"] for z in bloque.get("zona") or []}
    rayos = {z["num"]: z["signo_rayo"] for z in bloque.get("zona") or []}
    terceros_total = terceros_zona = rayos_aciertos = 0
    for num, oficial in oficiales.items():
        mm = masa_jornada.get(num)
        if not mm:
            return None
        tercero = min(mm, key=lambda s: float(mm[s]))
        if oficial == tercero:
            terceros_total += 1
            if num in nums_zona:
                terceros_zona += 1
        if num in nums_zona and oficial == rayos[num]:
            rayos_aciertos += 1
    return {
        "partidos_zona": len(nums_zona),
        "terceros_totales": terceros_total,
        "terceros_en_zona": terceros_zona,
        "rayos_acertados": rayos_aciertos,
    }


def _masa_jornada(etiqueta, jornada):
    datos = cargar_json(PORCENTAJES_DIR / etiqueta / f"jornada_{jornada}.json", {})
    return {p["numero"]: p["porcentajes"] for p in datos.get("partidos") or []
            if isinstance(p.get("numero"), int)}


def actualizar_marcador_radar(dir_predicciones=None, dir_jornadas=None,
                              ruta_marcador=None, etiqueta=None, ahora=None):
    """Al cerrar cada jornada con bloque radar publicado, registra la
    concentracion de terceros dentro/fuera de la zona. Idempotente por
    (temporada, jornada)."""
    dir_predicciones = Path(dir_predicciones or PREDICCIONES_DIR)
    dir_jornadas = Path(dir_jornadas or JORNADAS_DIR)
    ruta_marcador = Path(ruta_marcador or MARCADOR)
    ahora = ahora or datetime.now(timezone.utc)
    etiqueta = etiqueta or temporada_etiqueta(datetime.now())

    marcador = cargar_json(ruta_marcador, {})
    jornadas = marcador.get("jornadas") or []
    registradas = {(j.get("temporada"), j.get("jornada")) for j in jornadas}
    nuevas = 0
    for path in sorted(dir_predicciones.glob("jornada_*.json")):
        snapshot = cargar_json(path, {}) or {}
        bloque = snapshot.get("radar_tormenta") or {}
        if bloque.get("estado") not in ("ok", "sin_tormenta"):
            continue
        jornada = bloque.get("jornada")
        if not isinstance(jornada, int) or (etiqueta, jornada) in registradas:
            continue
        datos_jornada = cargar_json(dir_jornadas / f"jornada_{jornada}.json", {})
        resumen = evaluar_jornada_cerrada(
            bloque,
            snapshot.get("partidos") or [],
            datos_jornada.get("partidos") or [],
            _masa_jornada(etiqueta, jornada),
        )
        if resumen is None:
            continue  # jornada abierta, otra temporada o sin masa versionada
        jornadas.append({
            "temporada": etiqueta,
            "jornada": jornada,
            "zona": [{"num": z["num"],
                      "partido": f"{z['local']} - {z['visitante']}",
                      "signo_rayo": z["signo_rayo"],
                      "motivos": z["motivos"]}
                     for z in bloque.get("zona") or []],
            **resumen,
            "registrado_en": ahora.isoformat(),
        })
        registradas.add((etiqueta, jornada))
        nuevas += 1
    if not nuevas and marcador:
        return {"nuevas": 0, "resumen": marcador.get("resumen") or {}}

    evaluadas = len(jornadas)
    pz = sum(j["partidos_zona"] for j in jornadas)
    pt = evaluadas * 14
    tz = sum(j["terceros_en_zona"] for j in jornadas)
    tt = sum(j["terceros_totales"] for j in jornadas)
    ra = sum(j["rayos_acertados"] for j in jornadas)
    tasa_dentro = (tz / pz * 100) if pz else 0.0
    fuera_n = pt - pz
    tasa_fuera = ((tt - tz) / fuera_n * 100) if fuera_n else 0.0
    if evaluadas < 10:
        veredicto = "en_prueba"
    elif tasa_fuera and tasa_dentro >= 1.5 * tasa_fuera and tz >= 5:
        veredicto = "candidata"
    elif tasa_dentro <= tasa_fuera:
        veredicto = "despido"
    else:
        veredicto = "en_prueba"
    resumen = {
        "jornadas_evaluadas": evaluadas,
        "partidos_en_zona": pz,
        "terceros_en_zona": tz,
        "terceros_totales": tt,
        "rayos_acertados": ra,
        "tasa_terceros_dentro_pct": round(tasa_dentro, 1),
        "tasa_terceros_fuera_pct": round(tasa_fuera, 1),
        "veredicto": veredicto,
        "criterio_graduacion": ("tras >=10 jornadas: candidata si tasa dentro >= "
                                "1,5x fuera y >=5 terceros capturados; despido si "
                                "dentro <= fuera"),
    }
    guardar_json(ruta_marcador, {
        "version": 1,
        "actualizado_en": ahora.isoformat(),
        "modo": "sombra",
        "resumen": resumen,
        "jornadas": jornadas,
    })
    return {"nuevas": nuevas, "resumen": resumen}


# ---------------------------------------------------------------------------
# Script de pipeline (patron senal_valiente)
# ---------------------------------------------------------------------------

def main():
    prediccion = cargar_json(PREDICCION, {})
    if not prediccion:
        print("Sin ultima_prediccion.json; nada que radiar.")
        return
    if not prediccion.get("prediccion_disponible") or not prediccion.get("prediccion_permitida"):
        if prediccion.pop("radar_tormenta", None) is not None:
            guardar_json(PREDICCION, prediccion)
        print("Prediccion bloqueada o no disponible; bloque radar retirado.")
        return

    fuente_losilla = cargar_json(FUENTE_LOSILLA, {})
    bloque = construir_bloque_radar(prediccion, fuente_losilla)
    prediccion["radar_tormenta"] = bloque
    guardar_json(PREDICCION, prediccion)

    jornada = prediccion.get("jornada")
    espejo = PREDICCIONES_DIR / f"jornada_{jornada}.json"
    if isinstance(jornada, int) and espejo.exists():
        datos_espejo = cargar_json(espejo, {})
        if datos_espejo.get("jornada") == jornada:
            datos_espejo["radar_tormenta"] = bloque
            guardar_json(espejo, datos_espejo)

    if bloque.get("estado") == "ok":
        zona = "; ".join(
            f"P{z['num']} {z['local']} - {z['visitante']} rayo {z['signo_rayo']} "
            f"(score {z['score']})" for z in bloque["zona"]
        )
        print(f"Radar de Tormenta (sombra) J{jornada}: {zona}")
    else:
        print(f"Radar de Tormenta (sombra) J{jornada}: {bloque.get('estado')} - "
              f"{bloque.get('motivo')}")


if __name__ == "__main__":
    main()
