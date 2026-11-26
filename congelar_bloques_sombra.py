"""Congela los bloques en sombra de la jornada EN JUEGO (26/11/2026).

Bug real visto en la J24: Losilla pasa a la jornada siguiente en cuanto la
actual arranca (el 26/11 a las 08:02 ya servia la J25), el motor se queda sin
mercado, publica probabilidades planas para una jornada que ya se juega y los
modulos en sombra (valiente, radar, tercero, sorpresa nombrada, columna
valiente, ranker, optimizador, Elige 8) REESCRIBEN sus bloques en
data/predicciones/jornada_N.json con esas probabilidades. Los marcadores leen
ese fichero al cerrar la jornada: habrian medido una columna que nadie dijo
antes del cierre.

La fuente de verdad es el snapshot pre-cierre (data/backtesting/pre_cierre/
jornada_N.json), inmutable desde el primer partido. Este script corre al final
de la cadena de prediccion y, si la jornada ya ha empezado y existe snapshot,
restaura en el espejo (y en ultima_prediccion.json si es la misma jornada)
todos los bloques en sombra que el snapshot tenga. Lo que no este en el
snapshot (modulos nacidos despues del cierre) se RETIRA del espejo para que
ningun marcador lo mida.

Decision de Marc 26/11/2026 ("soluciona los 2 casos"): ademas de los bloques
en sombra se congela la PREDICCION ENTERA. Desde el primer partido, los 14
partidos (probabilidades, signos, coberturas, trazas) y los bloques de
decision son los de la foto del cierre; solo se actualizan encima los
resultados reales (resultado, signo_oficial) que trae el motor en cada
ejecucion. Como un boleto sellado: nadie reescribe pronosticos a mitad de
jornada. El snapshot pre-cierre sigue siendo la unica fuente de verdad.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
PREDICCIONES_DIR = DATA / "predicciones"
SNAPSHOTS_DIR = DATA / "backtesting" / "pre_cierre"

BLOQUES_SOMBRA = ("valiente", "tercero_valor", "radar_tormenta", "sorpresa_nombrada", "columna_valiente",
                  "favoritos_en_riesgo", "optimizador_boleto", "elige8_ev")
# Bloques de decision que tambien se congelan (si existen en el snapshot).
BLOQUES_DECISION = ("coste", "boleto_millonario", "boleto_ev_premio", "criterio_cobertura", "calibracion_cobertura",
                    "ataques_favorito_prioritarios", "ranking_incertidumbre_coberturas", "ranking_elige8_confianza_real",
                    "riesgos_detectados", "riesgos_no_cubiertos_por_presupuesto", "alertas_boleto", "resumen",
                    "elige8_seguro", "elige8_modos", "calibracion_probabilidades", "modelo_predictivo")
# Claves por partido que siguen VIVAS (resultados reales) y no se congelan.
CLAVES_VIVAS_PARTIDO = ("resultado", "signo_oficial", "estado", "estado_partido", "marcador", "minuto", "en_juego",
                        "goles_local", "goles_visitante")
CLAVES_VIVAS_PLENO = ("resultado", "signo_oficial", "estado")


def cargar_json(ruta, defecto=None):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(ruta, datos):
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def _fecha(valor):
    try:
        f = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return f if f.tzinfo else f.replace(tzinfo=timezone.utc)


def jornada_empezada(snapshot, ahora):
    """True si el primer partido del snapshot ya se jugo (o se esta jugando)."""
    inicio = _fecha(snapshot.get("primer_partido_utc"))
    return bool(inicio and inicio <= ahora)


def congelar(jornada, ahora=None, dir_predicciones=None, dir_snapshots=None, ruta_ultima=None):
    """Devuelve un resumen; idempotente. Solo actua si la jornada empezo."""
    ahora = ahora or datetime.now(timezone.utc)
    dir_predicciones = Path(dir_predicciones or PREDICCIONES_DIR)
    dir_snapshots = Path(dir_snapshots or SNAPSHOTS_DIR)
    ruta_ultima = Path(ruta_ultima or PREDICCION)
    snapshot = cargar_json(dir_snapshots / f"jornada_{jornada}.json", {}) or {}
    pred_snap = snapshot.get("prediccion") or {}
    if not pred_snap or pred_snap.get("jornada") != jornada:
        return {"jornada": jornada, "estado": "sin_snapshot"}
    if not jornada_empezada(snapshot, ahora):
        return {"jornada": jornada, "estado": "jornada_sin_empezar"}
    restaurados, retirados, tocados = [], [], []
    for ruta in (dir_predicciones / f"jornada_{jornada}.json", ruta_ultima):
        datos = cargar_json(ruta, {}) or {}
        if datos.get("jornada") != jornada:
            continue
        cambio = False
        for clave in BLOQUES_SOMBRA:
            if clave in pred_snap:
                if datos.get(clave) != pred_snap[clave]:
                    datos[clave] = pred_snap[clave]
                    cambio = True
                    if clave not in restaurados:
                        restaurados.append(clave)
            elif clave in datos:
                datos.pop(clave)
                cambio = True
                if clave not in retirados:
                    retirados.append(clave)
        # --- prediccion entera: partidos y bloques de decision desde la foto del cierre ---
        partidos_snap = {p.get("num"): p for p in pred_snap.get("partidos") or [] if isinstance(p.get("num"), int)}
        if partidos_snap and datos.get("partidos"):
            nuevos = []
            for actual in datos["partidos"]:
                base = partidos_snap.get(actual.get("num"))
                if not base:
                    nuevos.append(actual)
                    continue
                congelado = dict(base)
                for clave in CLAVES_VIVAS_PARTIDO:
                    if clave in actual:
                        congelado[clave] = actual[clave]
                nuevos.append(congelado)
            if nuevos != datos["partidos"]:
                datos["partidos"] = nuevos
                cambio = True
        pleno_snap = pred_snap.get("pleno15")
        if isinstance(pleno_snap, dict) and isinstance(datos.get("pleno15"), dict):
            pleno = dict(pleno_snap)
            for clave in CLAVES_VIVAS_PLENO:
                if clave in datos["pleno15"]:
                    pleno[clave] = datos["pleno15"][clave]
            if pleno != datos["pleno15"]:
                datos["pleno15"] = pleno
                cambio = True
        for clave in BLOQUES_DECISION:
            if clave in pred_snap and datos.get(clave) != pred_snap[clave]:
                datos[clave] = pred_snap[clave]
                cambio = True
        if cambio or "prediccion_congelada_al_cierre" not in datos:
            datos["prediccion_congelada_al_cierre"] = {
                "activa": True,
                "foto_del_cierre": str(snapshot.get("refrescado_en") or snapshot.get("creado_en")),
                "primer_partido_utc": snapshot.get("primer_partido_utc"),
                "congelado_en": ahora.isoformat(),
                "lectura": "Prediccion congelada al cierre (decision 26/11/2026): pronosticos, coberturas y bloques "
                           "son los de la foto del cierre; solo los resultados se actualizan en vivo.",
            }
            cambio = True
        if cambio:
            datos["bloques_sombra_congelados"] = {
                "desde_snapshot": str(snapshot.get("refrescado_en") or snapshot.get("creado_en")),
                "primer_partido_utc": snapshot.get("primer_partido_utc"),
                "congelado_en": ahora.isoformat(),
                "motivo": "jornada en juego: los bloques en sombra se miden tal y como se dijeron antes del cierre",
            }
            guardar_json(ruta, datos)
            tocados.append(ruta.name)
    return {"jornada": jornada, "estado": "congelado" if tocados else "ya_congelado",
            "restaurados": restaurados, "retirados": retirados, "ficheros": tocados}


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    prediccion = cargar_json(PREDICCION, {})
    jornada = prediccion.get("jornada")
    if not isinstance(jornada, int):
        print("Sin jornada activa; nada que congelar.")
        return
    r = congelar(jornada)
    print(f"Congelar bloques sombra J{jornada}: {r['estado']}"
          + (f" | restaurados {r['restaurados']} | retirados {r['retirados']} | {r['ficheros']}" if r.get("ficheros") else ""))


if __name__ == "__main__":
    main()
