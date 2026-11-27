"""Backtest PRERREGISTRADO del optimizador de boleto (optimizador_boleto.py).

Pregunta: con el MISMO presupuesto (columnas) que jugamos de verdad en cada
jornada cerrada de la 26/27, y SOLO con los datos que habia antes del cierre
(snapshot inmutable data/backtesting/pre_cierre/jornada_N.json y % LAE de
data/memoria_ia/porcentajes_lae/2026_2027/jornada_N.json), ¿el sistema que
propone el optimizador habria hecho mas aciertos y cobrado mas que el boleto
que sellamos (data/quinielas_jugadas.json)?

Variantes evaluadas: objetivos P14, P13plus y premio_esperado, cada uno con
contra_masa=False/True (6 sistemas por jornada). Variante PRINCIPAL:
premio_esperado sin contra_masa (es la que el informe propone publicar).

CRITERIOS PRERREGISTRADOS (se escriben en el JSON ANTES de calcular nada):
  C1  premio total de la temporada del optimizador (simulado con el
      escrutinio REAL de cada jornada, anadiendo nuestras columnas a los
      acertantes reales) >= premio total REAL cobrado por nuestros boletos,
      sobre las jornadas con premio nuestro conocido.
  C2  nº de jornadas con >=13 aciertos de la mejor columna >= el nuestro.
  Veredicto "supera" solo si cumple C1 y C2; "no supera" si falla alguno.
  Se informa de las 6 variantes; el veredicto de cabecera es el de la
  variante principal.

HONESTIDAD:
  - El optimizador no tiene parametros ajustados (no hay sobreajuste de
    busqueda), pero el modelo de premio con que elige SI es aproximado:
    recaudacion walk-forward (media de escrutinios ANTERIORES; defecto del
    modelo si no hay), factor_acertantes = 1 (sin meta-aprendizaje, que se
    ajusto con escrutinios posteriores), categorias 10-11 por campo medio.
  - El premio simulado del optimizador usa el escrutinio real: fondo_k =
    fraccion_k x recaudacion / (acertantes_reales + nuestras columnas),
    premio minimo 1,5 EUR, gravamen 20% > 40.000 EUR. Si la recaudacion
    guardada no es plausible (0,3-20 M EUR), se reconstruye de la 3a
    categoria (acertantes x premio / 7,5%) y se marca. Sin recaudacion ni
    reconstruccion, se usa el premio real por categoria (sin ajustar por
    nuestras columnas) y se marca.
  - Boletos nuestros REDUCIDOS (columnas del producto > apuestas pagadas):
    el presupuesto del optimizador es el de apuestas PAGADAS; el premio
    nuestro es el real registrado (no se puede recomponer la reducida).
  - Jornadas sin premio nuestro conocido quedan fuera del total C1 (se
    listan). Muestra corta (una temporada): el resultado orienta, no decide.

Salida: data/memoria_ia/backtest_optimizador_boleto.json + resumen ASCII.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from modelo_reparto_quiniela import (
    CATEGORIAS,
    FRACCION_RECAUDACION,
    PREMIO_MINIMO_PAGADO,
    RECAUDACION_DEFECTO,
    columnas_boleto,
    distribucion_aciertos_masa,
    premio_neto,
)
from optimizador_ev_premio import mezclar_probabilidades
import optimizador_boleto as ob

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
# 26/11/2026 (peticion de Marc: "nos hubiera ido mejor con estas decisiones?"):
# la fuente de probabilidades es un parametro. 'mezcla' = motor+Losilla 50/50
# (el prerregistro original); 'mercado' = solo Losilla (la decision pendiente
# de bajar el peso del motor); 'motor' = solo el motor publicado.
FUENTE = "mezcla"
if "--fuente" in sys.argv:
    FUENTE = sys.argv[sys.argv.index("--fuente") + 1]
SOLO_RAPIDO = "--rapido" in sys.argv   # solo P13plus (+/- masa) y P14: evita los 10-35 s del objetivo premio
_SUFIJO = "" if FUENTE == "mezcla" else f"_{FUENTE}"
SALIDA = DATA / "memoria_ia" / f"backtest_optimizador_boleto{_SUFIJO}.json"
PRE_CIERRE = DATA / "backtesting" / "pre_cierre"
TEMPORADA = "2026_2027"
PORCENTAJES = DATA / "memoria_ia" / "porcentajes_lae" / TEMPORADA
JORNADAS = DATA / "jornadas"
QUINIELAS = DATA / "quinielas_jugadas.json"
HISTORIAL_PREMIOS = DATA / "premios" / "historial_premios.json"

VARIANTES = [(obj, cm) for obj in ob.OBJETIVOS for cm in (False, True)]
if SOLO_RAPIDO:
    VARIANTES = [("P13plus", False), ("P13plus", True), ("P14", False)]
# La variante PRERREGISTRADA es siempre premio_esperado sin contra_masa. Con
# --rapido esa variante no se calcula y la cabecera del JSON pasa a ser
# P13plus: antes el JSON decia a la vez "variante principal = premio_esperado"
# (criterios) y variante_principal = P13plus. Ahora lo dice sin contradiccion.
VARIANTE_PRERREGISTRADA = ("premio_esperado", False)
VARIANTE_PRINCIPAL = ("P13plus", False) if SOLO_RAPIDO else VARIANTE_PRERREGISTRADA
RECAUDACION_MIN, RECAUDACION_MAX = 300_000.0, 20_000_000.0

CRITERIOS = {
    "C1": "premio total simulado del optimizador (escrutinio real, nuestras columnas anadidas a los "
          "acertantes) >= premio total real cobrado por nuestros boletos, en jornadas con premio conocido",
    "C2": "numero de jornadas con >=13 aciertos de la mejor columna >= el de nuestros boletos",
    "veredicto": (
        "supera solo si C1 y C2; variante principal = premio_esperado sin contra_masa; "
        "las 6 variantes se informan"
        if VARIANTE_PRINCIPAL == VARIANTE_PRERREGISTRADA else
        "supera solo si C1 y C2; la variante PRERREGISTRADA es premio_esperado sin contra_masa, que en "
        "esta ejecucion (--rapido) NO se calcula; la cabecera de este fichero es P13plus, elegida a "
        "posteriori: su veredicto es exploratorio, no el prerregistrado"
    ),
    "presupuesto": "mismas columnas que jugamos (apuestas pagadas si el boleto fue reducido)",
    "sin_fuga": "snapshot pre-cierre inmutable + % LAE pre-cierre; recaudacion walk-forward; factor_acertantes=1",
}


def cargar_json(path, defecto=None):
    if not path.exists():
        return defecto if defecto is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return defecto if defecto is not None else {}


def nombre_variante(objetivo, contra_masa):
    return f"{objetivo}{'__contra_masa' if contra_masa else ''}"


# ---------------------------------------------------------------------------
# datos por jornada
# ---------------------------------------------------------------------------
def signos_oficiales(jornada):
    data = cargar_json(JORNADAS / f"jornada_{jornada}.json", {})
    signos = {}
    for p in data.get("partidos") or []:
        num, signo = p.get("num"), str(p.get("signo_oficial") or "").upper()
        if isinstance(num, int) and 1 <= num <= 14 and signo in ("1", "X", "2"):
            signos[num] = signo
    return [signos[n] for n in range(1, 15)] if len(signos) == 14 else None


def masa_y_escrutinio(jornada):
    registro = cargar_json(PORCENTAJES / f"jornada_{jornada}.json", {})
    partidos = {p["numero"]: p["porcentajes"] for p in registro.get("partidos") or []
                if isinstance(p.get("numero"), int) and p.get("porcentajes")}
    masa = [partidos[n] for n in range(1, 15)] if all(n in partidos for n in range(1, 15)) else None
    return masa, registro.get("escrutinio") or {}


def probabilidades_pre_cierre(jornada):
    snapshot = cargar_json(PRE_CIERRE / f"jornada_{jornada}.json", {})
    prediccion = snapshot.get("prediccion") or {}
    if prediccion.get("jornada") != jornada:
        return None
    partidos = {p["num"]: p for p in prediccion.get("partidos") or []
                if isinstance(p.get("num"), int) and 1 <= p["num"] <= 14 and p.get("probabilidades")}
    if len(partidos) != 14:
        return None
    salida = []
    for n in range(1, 15):
        p = partidos[n]
        mercado = p.get("mercado_losilla") if isinstance(p.get("mercado_losilla"), dict) else None
        if FUENTE == "mercado" and mercado and sum(float(mercado.get(k) or 0) for k in ("1", "X", "2")) > 0:
            salida.append(mezclar_probabilidades(p["probabilidades"], mercado, peso_losilla=1.0))
        elif FUENTE == "motor":
            salida.append(mezclar_probabilidades(p["probabilidades"], mercado, peso_losilla=0.0))
        else:
            # igual que en produccion: mezcla 50/50; solo se salta en los
            # snapshots con el mercado ya integrado si Marc enciende
            # optimizador_ev_premio.EVITAR_SEGUNDA_MEZCLA (apagado por defecto).
            salida.append(mezclar_probabilidades(p["probabilidades"], mercado, partido=p))
    return salida


def jugadas_26_27():
    data = cargar_json(QUINIELAS, {"jugadas": []})
    salida = {}
    for jugada in data.get("jugadas") or []:
        # la numeracion se repite cada temporada: solo jugadas de la 26/27
        if str(jugada.get("temporada") or TEMPORADA) != TEMPORADA:
            continue
        j = jugada.get("jornada")
        signos = [ob.normalizar_signos(s) for s in (jugada.get("signos") or [])[:14]]
        if isinstance(j, int) and len(signos) == 14 and (PORCENTAJES / f"jornada_{j}.json").exists():
            salida[j] = {"signos": signos, "importe_total": jugada.get("importe_total"),
                         "premio_eur": jugada.get("premio_eur"), "aciertos_senales": jugada.get("aciertos_senales")}
    return salida


def premio_real(jornada, jugada):
    """(premio_eur, aciertos, fuente) de nuestro boleto; premio None si no se conoce."""
    historial = cargar_json(HISTORIAL_PREMIOS, {"jornadas": []})
    for e in historial.get("jornadas") or []:
        if e.get("jornada") == jornada and str(e.get("temporada") or TEMPORADA) == TEMPORADA:
            fuente = str(e.get("fuente_premio") or "")
            premio = e.get("premio_eur")
            if "reducida" in fuente and jugada.get("premio_eur") is None:
                return None, e.get("aciertos"), fuente
            if fuente == "pendiente" and premio in (None, 0, 0.0) and jugada.get("premio_eur") is None:
                # 'pendiente' con 0 EUR: en el historial significa sin premio
                return 0.0, e.get("aciertos"), fuente
            return float(premio or 0.0), e.get("aciertos"), fuente
    if jugada.get("premio_eur") is not None:
        return float(jugada["premio_eur"]), jugada.get("aciertos_senales"), "quinielas_jugadas"
    return None, None, "desconocido"


# ---------------------------------------------------------------------------
# premio simulado con escrutinio real
# ---------------------------------------------------------------------------
def recaudacion_plausible(escrutinio):
    """(recaudacion, origen). Reconstruye de la 3a/4a categoria si la guardada
    no es plausible."""
    valor = escrutinio.get("recaudacion_eur")
    if isinstance(valor, (int, float)) and RECAUDACION_MIN <= valor <= RECAUDACION_MAX:
        return float(valor), "escrutinio"
    categorias = escrutinio.get("categorias") or {}
    for cat in ("13", "12"):
        c = categorias.get(cat) or {}
        acert, premio = c.get("acertantes") or 0, c.get("premio_eur") or 0.0
        if acert > 0 and premio > 0:
            rec = acert * premio / FRACCION_RECAUDACION[int(cat)]
            if RECAUDACION_MIN <= rec <= RECAUDACION_MAX:
                return float(rec), f"reconstruida_de_categoria_{cat}"
    return None, "sin_recaudacion"


def escrutinio_valido(escrutinio):
    """Un escrutinio placebo (todas las categorias a 0, como el guardado en
    la J14 26/27) no sirve para repartir: se exige 3a categoria con
    acertantes y premio reales."""
    cat = (escrutinio.get("categorias") or {}).get("13") or {}
    return (cat.get("acertantes") or 0) > 0 and (cat.get("premio_eur") or 0.0) > 0


def acertantes_modelo(masa, reales, recaudacion):
    """Acertantes por categoria que predice el modelo de reparto (masa LAE +
    resultados reales); respaldo cuando el escrutinio no es valido."""
    dist = distribucion_aciertos_masa(masa, reales)
    apuestas = recaudacion / ob.PRECIO_APUESTA
    return {k: apuestas * dist[k] for k in CATEGORIAS}


def conteo_columnas(boleto, reales):
    conteo = [1] + [0] * len(boleto)
    for i, signos in enumerate(boleto):
        acierta = 1 if reales[i] in signos else 0
        falla = len(signos) - acierta
        nueva = [0] * len(conteo)
        for k in range(i + 1):
            nueva[k] += conteo[k] * falla
            nueva[k + 1] += conteo[k] * acierta
        conteo = nueva
    return conteo


def premio_simulado(boleto, reales, escrutinio, anadir_columnas=True, masa=None):
    """Euros netos que cobraria `boleto` con el reparto real. Devuelve
    (total, desglose, aciertos_mejor_columna, origen). Si el escrutinio no es
    valido (placebo) y hay masa, los acertantes salen del modelo de reparto y
    el origen lo dice."""
    conteo = conteo_columnas(boleto, reales)
    aciertos = max(k for k, v in enumerate(conteo) if v > 0)
    recaudacion, origen = recaudacion_plausible(escrutinio)
    categorias = escrutinio.get("categorias") or {}
    estimados = None
    if not escrutinio_valido(escrutinio) and masa is not None and recaudacion:
        estimados = acertantes_modelo(masa, reales, recaudacion)
        origen = "escrutinio_no_valido__acertantes_por_modelo_de_reparto"
    total, desglose = 0.0, {}
    for cat in CATEGORIAS:
        nuestras = conteo[cat]
        if not nuestras:
            continue
        real = categorias.get(str(cat)) or {}
        acertantes = int(real.get("acertantes") or 0) if estimados is None else estimados[cat]
        if recaudacion:
            fondo = FRACCION_RECAUDACION[cat] * recaudacion
            divisor = acertantes + (nuestras if anadir_columnas else 0)
            unitario = fondo / max(divisor, 1)
            unitario = 0.0 if unitario < PREMIO_MINIMO_PAGADO else premio_neto(unitario)
        else:
            unitario = float(real.get("premio_eur") or 0.0)
        ganado = unitario * nuestras
        total += ganado
        if ganado:
            desglose[str(cat)] = {"columnas": nuestras, "premio_unitario_eur": round(unitario, 2)}
    return round(total, 2), desglose, aciertos, origen


# ---------------------------------------------------------------------------
# backtest
# ---------------------------------------------------------------------------
def escribir(salida):
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ejecutar(verbose=True):
    inicio = time.perf_counter()
    base = {
        "version": 1,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": "Backtest prerregistrado del optimizador de boleto (knapsack en logaritmos + "
                       "busqueda local Clair-Letscher) frente a los boletos realmente jugados en la 26/27.",
        "criterios_prerregistrados": CRITERIOS,
        "fuente_probabilidades": FUENTE,
        "variante_principal": nombre_variante(*VARIANTE_PRINCIPAL),
        "variante_prerregistrada": nombre_variante(*VARIANTE_PRERREGISTRADA),
        "variante_principal_es_la_prerregistrada": VARIANTE_PRINCIPAL == VARIANTE_PRERREGISTRADA,
        "estado": "prerregistrado_pendiente_de_resultados",
    }
    escribir(base)  # los criterios quedan escritos ANTES de calcular

    jugadas = jugadas_26_27()
    filas, recaudaciones_previas = [], []
    for jornada in sorted(jugadas):
        jugada = jugadas[jornada]
        reales = signos_oficiales(jornada)
        masa, escrutinio = masa_y_escrutinio(jornada)
        probs = probabilidades_pre_cierre(jornada)
        if not (reales and masa and probs and escrutinio.get("categorias")):
            if verbose:
                print(f"  J{jornada}: sin datos completos (resultados/masa/snapshot/escrutinio) -> fuera")
            continue
        columnas_producto = columnas_boleto(jugada["signos"])
        importe = jugada.get("importe_total")
        presupuesto = columnas_producto
        reducida = False
        if isinstance(importe, (int, float)) and importe > 0:
            pagadas = int(round(importe / ob.PRECIO_APUESTA))
            if pagadas < columnas_producto:
                presupuesto, reducida = pagadas, True
        recaudacion_wf = (sum(recaudaciones_previas) / len(recaudaciones_previas)
                          if recaudaciones_previas else RECAUDACION_DEFECTO)

        premio_nuestro, aciertos_hist, fuente_premio = premio_real(jornada, jugada)
        aciertos_nuestro = max(k for k, v in enumerate(conteo_columnas(jugada["signos"], reales)) if v > 0)
        sim_nuestro, _, _, origen_rec = premio_simulado(jugada["signos"], reales, escrutinio,
                                                        anadir_columnas=False, masa=masa)

        fila = {
            "jornada": jornada,
            "presupuesto_columnas": presupuesto,
            "coste_eur": ob.coste_eur(presupuesto),
            "boleto_reducido": reducida,
            "columnas_producto_jugado": columnas_producto,
            "recaudacion_walk_forward_eur": round(recaudacion_wf, 2),
            "recaudacion_escrutinio_origen": origen_rec,
            "nuestro": {
                "signos": jugada["signos"],
                "aciertos_senales": aciertos_nuestro,
                "aciertos_historial": aciertos_hist,
                "premio_real_eur": premio_nuestro,
                "premio_fuente": fuente_premio,
                "premio_simulado_producto_completo_eur": None if reducida else sim_nuestro,
            },
            "variantes": {},
        }
        for objetivo, contra in VARIANTES:
            res = ob.optimizar(probs, masa, presupuesto, objetivo=objetivo, contra_masa=contra,
                               recaudacion=recaudacion_wf, factor_acertantes=1.0)
            premio, desglose, aciertos, _ = premio_simulado(res["signos"], reales, escrutinio, masa=masa)
            fila["variantes"][nombre_variante(objetivo, contra)] = {
                "signos": res["signos"],
                "columnas": res["columnas"],
                "triples": res["triples"],
                "dobles": res["dobles"],
                "aciertos_mejor_columna": aciertos,
                "premio_simulado_eur": premio,
                "desglose": desglose,
                "P14_modelo": res["P14"],
                "P13plus_modelo": res["P13plus"],
                "premio_esperado_modelo_eur": res.get("premio_esperado"),
                "segundos": res["segundos"],
            }
        # metricas del modelo para nuestro boleto (mismo evaluador, informativo)
        ev = ob.Evaluador(ob.matriz_probs(probs), ob.matriz_probs(masa), recaudacion=recaudacion_wf)
        met = ob._redondear(ev.metricas(ob.mascara(jugada["signos"]))) if not reducida else {}
        fila["nuestro"]["P14_modelo"] = met.get("P14")
        fila["nuestro"]["P13plus_modelo"] = met.get("P13plus")
        fila["nuestro"]["premio_esperado_modelo_eur"] = met.get("premio_esperado")
        filas.append(fila)
        if verbose:
            v = fila["variantes"][nombre_variante(*VARIANTE_PRINCIPAL)]
            print(f"  J{jornada:>2} ({presupuesto:>3} col{', reducida' if reducida else ''}): nuestro "
                  f"{aciertos_nuestro} ac / {('%.2f' % premio_nuestro) if premio_nuestro is not None else '?'} EUR | "
                  f"optimizador {v['aciertos_mejor_columna']} ac / {v['premio_simulado_eur']:.2f} EUR "
                  f"({v['triples']}T+{v['dobles']}D, {v['segundos']:.1f}s)")
        rec, _ = recaudacion_plausible(escrutinio)
        if rec:
            recaudaciones_previas.append(rec)

    # agregados
    con_premio = [f for f in filas if f["nuestro"]["premio_real_eur"] is not None]
    total_nuestro = round(sum(f["nuestro"]["premio_real_eur"] for f in con_premio), 2)
    n13_nuestro = sum(1 for f in filas if f["nuestro"]["aciertos_senales"] >= 13)
    media_nuestro = round(sum(f["nuestro"]["aciertos_senales"] for f in filas) / max(len(filas), 1), 3)
    resumen = {}
    for objetivo, contra in VARIANTES:
        nombre = nombre_variante(objetivo, contra)
        total = round(sum(f["variantes"][nombre]["premio_simulado_eur"] for f in con_premio), 2)
        total_todas = round(sum(f["variantes"][nombre]["premio_simulado_eur"] for f in filas), 2)
        n13 = sum(1 for f in filas if f["variantes"][nombre]["aciertos_mejor_columna"] >= 13)
        media = round(sum(f["variantes"][nombre]["aciertos_mejor_columna"] for f in filas) / max(len(filas), 1), 3)
        gana = sum(1 for f in filas if f["variantes"][nombre]["aciertos_mejor_columna"] > f["nuestro"]["aciertos_senales"])
        pierde = sum(1 for f in filas if f["variantes"][nombre]["aciertos_mejor_columna"] < f["nuestro"]["aciertos_senales"])
        c1 = total >= total_nuestro
        c2 = n13 >= n13_nuestro
        resumen[nombre] = {
            "premio_total_simulado_eur_jornadas_comparables": total,
            "premio_total_simulado_eur_todas": total_todas,
            "jornadas_con_13_o_mas": n13,
            "media_aciertos_mejor_columna": media,
            "jornadas_mas_aciertos_que_nosotros": gana,
            "jornadas_menos_aciertos_que_nosotros": pierde,
            "C1_premio": c1,
            "C2_trece_o_mas": c2,
            "veredicto": "supera" if (c1 and c2) else "no supera",
        }
    principal = resumen[nombre_variante(*VARIANTE_PRINCIPAL)]
    salida = dict(base)
    salida.update({
        "estado": "completado",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "segundos_total": round(time.perf_counter() - inicio, 1),
        "jornadas_evaluadas": len(filas),
        "jornadas_con_premio_nuestro_conocido": [f["jornada"] for f in con_premio],
        "jornadas_sin_premio_nuestro_conocido": [f["jornada"] for f in filas if f["nuestro"]["premio_real_eur"] is None],
        "jornadas_con_premio_estimado_por_modelo": [f["jornada"] for f in filas
                                                    if "modelo" in f["recaudacion_escrutinio_origen"]],
        "coste_total_eur": round(sum(f["coste_eur"] for f in filas), 2),
        "nuestro": {
            "premio_total_real_eur_jornadas_comparables": total_nuestro,
            "jornadas_con_13_o_mas": n13_nuestro,
            "media_aciertos_senales": media_nuestro,
        },
        "variantes": resumen,
        "veredicto_principal": principal["veredicto"],
        "aviso": (
            "Una temporada, premio simulado con modelo de reparto aproximado y recaudacion walk-forward; "
            "sin parametros ajustados pero el modelo de premio es aproximado. Orienta, no decide."
        ),
        "detalle": filas,
    })
    escribir(salida)
    return salida


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("== Backtest prerregistrado: optimizador de boleto vs boletos jugados 26/27 ==")
    salida = ejecutar(verbose=True)
    n = salida["nuestro"]
    print(f"\nJornadas evaluadas: {salida['jornadas_evaluadas']} (coste total {salida['coste_total_eur']:.2f} EUR); "
          f"con premio nuestro conocido: {len(salida['jornadas_con_premio_nuestro_conocido'])}; "
          f"sin conocer: {salida['jornadas_sin_premio_nuestro_conocido']}")
    print(f"NUESTRO: premio real {n['premio_total_real_eur_jornadas_comparables']:.2f} EUR, "
          f">=13 en {n['jornadas_con_13_o_mas']} jornadas, media {n['media_aciertos_senales']:.2f} aciertos")
    for nombre, r in salida["variantes"].items():
        print(f"  {nombre:<30} premio {r['premio_total_simulado_eur_jornadas_comparables']:>8.2f} EUR | >=13: {r['jornadas_con_13_o_mas']} | "
              f"media {r['media_aciertos_mejor_columna']:.2f} | +{r['jornadas_mas_aciertos_que_nosotros']}/-{r['jornadas_menos_aciertos_que_nosotros']} jornadas "
              f"| C1 {'ok' if r['C1_premio'] else 'NO'} C2 {'ok' if r['C2_trece_o_mas'] else 'NO'} -> {r['veredicto']}")
    print(f"\nVeredicto variante principal ({salida['variante_principal']}): {salida['veredicto_principal']}")
    print(f"Guardado en {SALIDA} ({salida['segundos_total']:.0f}s)")


if __name__ == "__main__":
    main()
