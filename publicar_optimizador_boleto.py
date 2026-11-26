"""Publica el bloque "optimizador_boleto" en ultima_prediccion.json (26/11/2026).

Punto 3 del informe "Algoritmos contra nuestros fallos 1X2": reparto exacto de
un presupuesto en columnas entre fijos, dobles y triples (knapsack en
logaritmos + busqueda local de Clair-Letscher), con la P(14) y P(>=13) exactas
y el premio esperado del modelo de reparto. Backtest prerregistrado en
data/memoria_ia/backtest_optimizador_boleto.json: el objetivo P13plus cumple los
dos criterios (premio y >=13) frente a nuestros boletos reales de la 26/27; el
objetivo premio_esperado NO cumple C2 (0 treces en 22 jornadas) y se publica
solo como lectura "contra la masa".

Solo lectura del motor: el bloque es una ESTRUCTURA SUGERIDA; jugar dinero
real lo decide siempre Marc.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import optimizador_boleto as ob

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
PREDICCIONES_DIR = DATA / "predicciones"
BACKTEST = DATA / "memoria_ia" / "backtest_optimizador_boleto.json"

PRESUPUESTO_PRINCIPAL = 18          # la base semanal de Marc (13,50 EUR)
PRESUPUESTOS_ALTERNATIVOS = (9, 16, 24, 32, 48)
OBJETIVO_PUBLICADO = "P13plus"      # el unico que paso C1 y C2 en el backtest

AVISO = ("Estructura sugerida por el optimizador (modo sombra: se mide contra lo jugado). "
         "P(14) y P(>=13) son exactas dadas las probabilidades; el premio esperado depende "
         "del modelo de reparto y orienta, no decide. Jugar dinero real lo decide siempre Marc.")


def cargar_json(ruta, defecto=None):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(ruta, datos):
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def resumen_backtest():
    bt = cargar_json(BACKTEST, {}) or {}
    variantes = bt.get("variantes") or {}
    nuestro = bt.get("nuestro") or {}
    principal = variantes.get(OBJETIVO_PUBLICADO) or {}
    return {
        "jornadas": bt.get("jornadas_evaluadas"),
        "nuestro_premio_eur": nuestro.get("premio_total_real_eur_jornadas_comparables"),
        "nuestro_trece_o_mas": nuestro.get("jornadas_con_13_o_mas"),
        "nuestro_media_aciertos": nuestro.get("media_aciertos_senales"),
        "variante_publicada": OBJETIVO_PUBLICADO,
        "variante_premio_eur": principal.get("premio_total_simulado_eur_jornadas_comparables"),
        "variante_trece_o_mas": principal.get("jornadas_con_13_o_mas"),
        "variante_media_aciertos": principal.get("media_aciertos_mejor_columna"),
        "variante_mas_que_nosotros": principal.get("jornadas_mas_aciertos_que_nosotros"),
        "variante_menos_que_nosotros": principal.get("jornadas_menos_aciertos_que_nosotros"),
        "veredicto_variante_publicada": principal.get("veredicto"),
        "veredicto_premio_esperado": bt.get("veredicto_principal"),
        "jornada_con_premio_estimado": bt.get("jornadas_con_premio_estimado_por_modelo"),
        "aviso": bt.get("aviso"),
    }


def _res_compacto(res):
    return {k: res.get(k) for k in ("signos", "columnas", "coste_eur", "triples", "dobles",
                                     "P14", "P13plus", "P12plus", "premio_esperado", "segundos")}


def construir_bloque():
    datos = ob.datos_jornada_actual()
    ahora = datetime.now(timezone.utc).isoformat()
    base = {"modo": "sombra", "generado_en": ahora, "aviso": AVISO, "objetivo_publicado": OBJETIVO_PUBLICADO,
            "backtest": resumen_backtest()}
    if not datos:
        return {**base, "estado": "no_disponible", "motivo": "prediccion sin 14 partidos"}
    kw = dict(recaudacion=datos["recaudacion"], factor_acertantes=datos["factor_acertantes"])
    masa = datos["masa"] or None
    principal = ob.optimizar(datos["probs"], masa, PRESUPUESTO_PRINCIPAL, objetivo=OBJETIVO_PUBLICADO, **kw)
    bloque = {**base, "estado": "ok", "jornada": datos["jornada"], "presupuesto_columnas": PRESUPUESTO_PRINCIPAL,
              "fuente_masa": datos["fuente_masa"], "recaudacion_estimada": datos["recaudacion"],
              **_res_compacto(principal),
              "detalle_partidos": principal.get("detalle_partidos"),
              "comparaciones": {k: _res_compacto(v) for k, v in (principal.get("comparaciones") or {}).items()
                                if isinstance(v, dict) and "signos" in v},
              "alternativas_por_presupuesto": {}}
    for presupuesto in PRESUPUESTOS_ALTERNATIVOS:
        res = ob.optimizar(datos["probs"], masa, presupuesto, objetivo=OBJETIVO_PUBLICADO, **kw)
        bloque["alternativas_por_presupuesto"][str(presupuesto)] = _res_compacto(res)
    if masa:
        try:
            cola = ob.optimizar(datos["probs"], masa, PRESUPUESTO_PRINCIPAL, objetivo="premio_esperado",
                                contra_masa=True, **kw)
            bloque["lectura_contra_masa"] = {**_res_compacto(cola),
                                             "nota": "objetivo premio_esperado contra la masa: 0 treces en 22 jornadas "
                                                     "de backtest, NO cumple el criterio; solo lectura de cola."}
        except Exception as exc:  # pragma: no cover
            bloque["lectura_contra_masa"] = {"error": str(exc)[:120]}
    return bloque


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    prediccion = cargar_json(PREDICCION, {})
    if not prediccion or not prediccion.get("partidos"):
        print("Sin ultima_prediccion.json; nada que publicar.")
        return
    if not prediccion.get("prediccion_disponible") or not prediccion.get("prediccion_permitida"):
        if prediccion.pop("optimizador_boleto", None) is not None:
            guardar_json(PREDICCION, prediccion)
        print("Prediccion bloqueada o no disponible; bloque optimizador_boleto retirado.")
        return
    bloque = construir_bloque()
    prediccion["optimizador_boleto"] = bloque
    guardar_json(PREDICCION, prediccion)
    jornada = prediccion.get("jornada")
    espejo = PREDICCIONES_DIR / f"jornada_{jornada}.json"
    if isinstance(jornada, int) and espejo.exists():
        datos = cargar_json(espejo, {})
        if datos.get("jornada") == jornada:
            datos["optimizador_boleto"] = bloque
            guardar_json(espejo, datos)
    if bloque.get("estado") == "ok":
        print(f"Optimizador de boleto J{jornada} ({OBJETIVO_PUBLICADO}, {PRESUPUESTO_PRINCIPAL} col): "
              f"{' '.join(bloque['signos'])} | P14 {bloque['P14']:.5f} P13+ {bloque['P13plus']:.4f} "
              f"EV {bloque.get('premio_esperado') or 0:.2f} EUR")
    else:
        print(f"Optimizador de boleto: {bloque.get('estado')} - {bloque.get('motivo')}")


if __name__ == "__main__":
    main()
