"""Columna valiente europea (modo sombra, 23/11/2026).

Regla de Marc tras la J24: "no quiero solo los resultados que por % tienen
mas peso, quiero que prediga incluso los de menos peso por sorpresas posibles,
jugandosela". Y: "de que sirve que anote todo lo aprendido si luego no lo
aplico". Este modulo APLICA en el pipeline, cada jornada europea, lo medido en
las 4 Champions de 26/27 (J5, J13, J15, J19; 56 partidos con masa LAE):

  - favorito de la masa <40% ("sin dueno"): acierta 1/6; la X salio 3/6.
  - favorito 65-79.9%: cae 6/19 (uno y medio por jornada).
  - favorito >=80%: 10/10, nunca cae.
  - espanol de media tabla favorito FUERA (<65%): 0 aciertos (Celta, Getafe,
    Real Sociedad, Atletico); solo el Betis (3/3, como favorito en casa o
    >=65) rompe la pauta, y queda fuera de la regla por el umbral, no por
    nombre.
  - la columna de la masa hizo 10, 8, 8 y 10: ~9/14.

Reglas prerregistradas (orden de prioridad; tope CAMBIOS_MAX cambios):
  R4  favorito >=80 no se toca nunca.
  R1  sin dueno (<40) -> X.
  R3  espanol favorito fuera con masa <60 -> el no-favorito mas probable
      (fallaron por X: Atletico en Stuttgart, Getafe en Craiova).
  R2  UN gigante 65-79.9 cae por jornada, pero el selector automatico acerto
      1/4 in-sample: NO se cambia solo; se publica la lista "gigantes_en_riesgo"
      y lo nombra el ojeador con las señales previas (favorito que viene de
      perder, rotacion declarada, rival en racha: visibles en 6 de 7 sorpresas).
  R5  la Sorpresa Nombrada del modulo sorpresa_nombrada.py, si no choca con
      R4 y aun queda cupo.

Se publica como bloque "columna_valiente" junto a la columna de la masa, y un
marcador en sombra cuenta aciertos valiente vs masa por jornada europea
cerrada. Criterio de graduacion prerregistrado (ver CRITERIO_GRADUACION).
HONESTIDAD: las reglas salen de las mismas 4 jornadas con las que se mide el
backtest retrospectivo (in-sample). Solo el marcador prospectivo vale.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
PREDICCIONES_DIR = DATA / "predicciones"
JORNADAS_DIR = DATA / "jornadas"
PORCENTAJES_DIR = DATA / "memoria_ia" / "porcentajes_lae"
MARCADOR = DATA / "memoria_ia" / "marcador_columna_valiente.json"
BACKTEST = DATA / "memoria_ia" / "backtest_columna_valiente.json"
CALENDARIOS_ESP = (DATA / "calendario_primera.json", DATA / "calendario_segunda.json")

SIGNOS = ("1", "X", "2")
SIN_DUENO_MAX = 40.0
GIGANTE_MIN = 65.0
INTOCABLE_MIN = 80.0
ESPANOL_FUERA_MAX = 60.0
CAMBIOS_MAX = 5
MIN_PARTIDOS_EXTRANJEROS = 10
GRADUACION_MIN_JORNADAS = 6
GRADUACION_VENTAJA = 0.5
SUSPENSION_DESVENTAJA = -1.0

AVISO_SOMBRA = ("Experimental, MODO SOMBRA: la columna valiente se publica y se mide contra la "
                "columna de la masa, pero no sustituye a la recomendacion hasta graduarse. "
                "Jugar dinero real lo decide siempre Marc.")
CRITERIO_GRADUACION = (
    f"Prerregistrado 23/11/2026: con >={GRADUACION_MIN_JORNADAS} jornadas europeas cerradas, si la media de "
    f"(aciertos valiente - aciertos masa) >= +{GRADUACION_VENTAJA} -> 'candidata' (avisar a Marc); si <= "
    f"{SUSPENSION_DESVENTAJA} -> 'suspendida'; en otro caso 'en_prueba'. El criterio no se cambia tras ver los datos."
)


def cargar_json(ruta, defecto=None):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(ruta, datos):
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def _norm(nombre):
    return " ".join(str(nombre or "").lower().replace(".", " ").split())


_EQUIPOS_ESP = None


def equipos_espanoles(rutas=None):
    """Nombres (normalizados) de todos los clubes de 1a y 2a segun los calendarios."""
    global _EQUIPOS_ESP
    if rutas is None and _EQUIPOS_ESP is not None:
        return _EQUIPOS_ESP
    nombres = set()
    for ruta in (rutas or CALENDARIOS_ESP):
        datos = cargar_json(ruta, {}) or {}
        for jornada in datos.get("jornadas", []):
            for p in jornada.get("partidos", []):
                nombres.add(_norm(p.get("local")))
                nombres.add(_norm(p.get("visitante")))
    nombres.discard("")
    if rutas is None:
        _EQUIPOS_ESP = nombres
    return nombres


def es_espanol(nombre, espanoles):
    n = _norm(nombre)
    if not n:
        return False
    if n in espanoles:
        return True
    # "RC Celta de Vigo" vs "Celta", "Real Betis Balompie" vs "Real Betis"
    return any(n in e or e in n for e in espanoles if len(min(n, e, key=len)) >= 5)


def es_jornada_europea(partidos, espanoles=None):
    espanoles = espanoles if espanoles is not None else equipos_espanoles()
    extranjeros = sum(1 for p in partidos
                      if not (es_espanol(p.get("local"), espanoles) and es_espanol(p.get("visitante"), espanoles)))
    return extranjeros >= MIN_PARTIDOS_EXTRANJEROS, extranjeros


def prediccion_publicable(prediccion):
    """True si el pipeline permite publicar sobre esta prediccion (misma
    guarda que La Valiente: prediccion_disponible y prediccion_permitida)."""
    return bool(prediccion and prediccion.get("prediccion_disponible") and prediccion.get("prediccion_permitida"))


def publicar_bloque_sombra(clave, bloque, prediccion, ruta_prediccion, dir_predicciones=None):
    """Escribe (o RETIRA, si bloque es None) el bloque `clave` en
    ultima_prediccion.json y en el espejo jornada_N.json de la misma jornada.

    Auditoria 26/11: ranker_favoritos y elige8_ev publicaban su bloque aunque
    la prediccion estuviera bloqueada, y si el bloque nuevo no era 'ok' se
    quedaba en disco el de la ejecucion anterior. Devuelve los ficheros
    cambiados."""
    ruta_prediccion = Path(ruta_prediccion)
    dir_predicciones = Path(dir_predicciones) if dir_predicciones else ruta_prediccion.parent
    jornada = prediccion.get("jornada")
    cambiados = []
    destinos = [(ruta_prediccion, prediccion)]
    espejo = dir_predicciones / f"jornada_{jornada}.json"
    if isinstance(jornada, int) and espejo.exists():
        datos = cargar_json(espejo, {}) or {}
        if datos.get("jornada") == jornada:
            destinos.append((espejo, datos))
    for ruta, datos in destinos:
        if bloque is None:
            if clave not in datos:
                continue
            datos.pop(clave)
        else:
            datos[clave] = bloque
        guardar_json(ruta, datos)
        cambiados.append(ruta.name)
    return cambiados


def etiqueta_de_jornada(jornada, dir_jornadas=None):
    """'2026_2027' de data/jornadas/jornada_N.json segun su FECHA real (nunca
    segun el numero ni segun now()). None si no hay fichero o no trae fecha."""
    import cronologia_jornadas as cj
    try:
        datos = cj.cargar_jornada(jornada, dir_jornadas or JORNADAS_DIR)
    except (TypeError, ValueError):
        return None
    fecha = cj.fecha_real_jornada(datos) if datos else None
    return cj.temporada_de_fecha(fecha, jornada) if fecha else None


def cargar_masa(jornada, etiqueta=None, partidos=None):
    """{num: {'1':..,'X':..,'2':..}} de porcentajes_lae/<temporada>/jornada_N.json.

    Auditoria 26/11: sin etiqueta se buscaba jornada_N en CUALQUIER temporada
    (la mas reciente primero) y al empezar la 27/28 habria devuelto la masa de
    la J-N de la 26/27, que es otro partido. Ahora la temporada sale de la
    fecha real de la jornada y no hay salto a otras temporadas: si no hay
    masa de ESTA jornada se devuelve {} (masa_de ya cae a mercado_losilla).
    Si se pasan los `partidos` de la prediccion se comprueba ademas que los
    equipos del fichero de masa son los mismos."""
    etiqueta = etiqueta or etiqueta_de_jornada(jornada)
    if not etiqueta:
        return {}
    datos = cargar_json(PORCENTAJES_DIR / etiqueta / f"jornada_{jornada}.json")
    if not datos or datos.get("jornada") != jornada:
        return {}
    if partidos:
        import cronologia_jornadas as cj
        coinciden, comparables = cj.coincidencia_equipos(datos, {"partidos": list(partidos)})
        # Medido en J1-J25: la masa de su jornada casa >= 10 de 14 equipos y
        # dos jornadas distintas nunca comparten 3 partidos.
        if comparables >= cj.UMBRAL_PARTIDOS_IGUALES and coinciden < 3:
            return {}
    return {p["numero"]: {s: float(p["porcentajes"].get(s, 0)) for s in SIGNOS}
            for p in datos.get("partidos", []) if p.get("porcentajes")}


def masa_de(partido, masa):
    m = masa.get(partido.get("num"))
    if m:
        return m
    ml = partido.get("mercado_losilla") or {}
    if all(s in ml for s in SIGNOS):
        return {s: float(ml[s]) for s in SIGNOS}
    return None


def favorito(probs):
    return max(SIGNOS, key=lambda s: probs.get(s, 0))


def construir_columna(partidos, masa, espanoles=None, sorpresa=None):
    """Devuelve (columna_valiente, columna_masa, cambios, descartes)."""
    espanoles = espanoles if espanoles is not None else equipos_espanoles()
    columna_masa, columna, cambios, descartes = {}, {}, [], []
    datos = {}
    for p in partidos:
        num = p.get("num")
        m = masa_de(p, masa)
        motor = {s: float((p.get("probabilidades") or {}).get(s, 0)) for s in SIGNOS}
        if not m:
            m = motor
            descartes.append({"num": num, "motivo": "sin masa LAE: se usa el motor como masa"})
        fav = favorito(m)
        columna_masa[num] = fav
        columna[num] = fav
        datos[num] = (p, m, motor, fav)

    def cambiar(num, signo, regla, motivo):
        if len(cambios) >= CAMBIOS_MAX or columna[num] != columna_masa[num]:
            return False
        columna[num] = signo
        p, m, motor, fav = datos[num]
        cambios.append({"num": num, "local": p.get("local"), "visitante": p.get("visitante"),
                        "de": fav, "a": signo, "regla": regla, "motivo": motivo,
                        "masa": m, "motor": motor})
        return True

    # R1 sin dueno -> X (de menor a mayor favorito: el mas abierto primero)
    for num, (p, m, motor, fav) in sorted(datos.items(), key=lambda kv: max(kv[1][1].values())):
        top = m[fav]
        if top < SIN_DUENO_MAX and fav != "X":
            cambiar(num, "X", "R1_sin_dueno",
                    f"favorito de la masa al {top:.0f}%: en 26/27 el favorito acerto 1/6 y la X salio 3/6")
    # R3 espanol favorito fuera con masa < 60 -> el no-favorito mas probable (en
    # 26/27 fallaron por X: Atletico en Stuttgart, Getafe en Craiova)
    for num, (p, m, motor, fav) in datos.items():
        top = m[fav]
        if fav == "2" and top < ESPANOL_FUERA_MAX and es_espanol(p.get("visitante"), espanoles)                 and not es_espanol(p.get("local"), espanoles):
            signo = max([s for s in SIGNOS if s != fav], key=lambda s: motor.get(s, 0))
            cambiar(num, signo, "R3_espanol_favorito_fuera",
                    f"{p.get('visitante')} favorito fuera al {top:.0f}%: los espanoles de media tabla favoritos "
                    f"fuera en Europa 26/27 no ganaron ninguno (Atletico X, Getafe X); solo la Real al 61% gano")
    # R2 un gigante 65-79.9 cae por jornada (6/19), pero el motor NO sabe cual:
    # en el backtest in-sample el selector por duda del motor acerto 1 de 4, asi
    # que NO se cambia en automatico. Se publica la lista para que el ojeador
    # (Marc/Claude) nombre el que cae con las señales que SI avisaron en 6 de 7
    # sorpresas: favorito que viene de perder, rotacion declarada, rival en racha.
    gigantes = []
    for num, (p, m, motor, fav) in datos.items():
        if GIGANTE_MIN <= m[fav] < INTOCABLE_MIN:
            no_fav = [s for s in SIGNOS if s != fav]
            gigantes.append({"num": num, "local": p.get("local"), "visitante": p.get("visitante"), "favorito": fav,
                             "masa": m[fav], "motor": motor.get(fav, 0),
                             "signo_si_cae": max(no_fav, key=lambda s: motor.get(s, 0))})
    gigantes.sort(key=lambda g: g["masa"])
    # R5 sorpresa nombrada del modulo
    if sorpresa and sorpresa.get("estado") == "ok":
        num = sorpresa.get("num")
        if num in datos and datos[num][1][datos[num][3]] < INTOCABLE_MIN:
            cambiar(num, sorpresa.get("signo"), "R5_sorpresa_nombrada",
                    "la Sorpresa Nombrada de la jornada: " + "; ".join(
                        s.get("texto") or s.get("tipo", "") for s in sorpresa.get("senales", [])))
        elif num in datos:
            descartes.append({"num": num, "motivo": "sorpresa nombrada sobre un favorito >=80: R4 manda"})
    return columna, columna_masa, cambios, descartes, gigantes


def esperados(columna, partidos, masa):
    total = 0.0
    for p in partidos:
        m = masa_de(p, masa) or {s: float((p.get("probabilidades") or {}).get(s, 0)) for s in SIGNOS}
        total += m.get(columna.get(p.get("num")), 0) / 100.0
    return round(total, 2)


def construir_bloque(prediccion, masa=None, espanoles=None):
    partidos = [p for p in prediccion.get("partidos", []) if isinstance(p.get("num"), int) and p["num"] <= 14]
    jornada = prediccion.get("jornada")
    ahora = datetime.now(timezone.utc).isoformat()
    base = {"modo": "sombra", "generado_en": ahora, "jornada": jornada, "aviso": AVISO_SOMBRA,
            "criterio_graduacion": CRITERIO_GRADUACION}
    if len(partidos) < 14:
        return {**base, "estado": "no_disponible", "motivo": "prediccion incompleta"}
    espanoles = espanoles if espanoles is not None else equipos_espanoles()
    europea, extranjeros = es_jornada_europea(partidos, espanoles)
    if not europea:
        return {**base, "estado": "no_aplica", "partidos_extranjeros": extranjeros,
                "motivo": f"jornada domestica ({extranjeros} partidos con equipo extranjero): las reglas se midieron "
                          f"solo en semanas europeas y no se extrapolan"}
    masa = masa if masa is not None else cargar_masa(jornada, partidos=partidos)
    columna, columna_masa, cambios, descartes, gigantes = construir_columna(
        partidos, masa, espanoles, prediccion.get("sorpresa_nombrada"))
    orden = sorted(columna)
    return {**base, "estado": "ok", "partidos_extranjeros": extranjeros,
            "columna": [columna[n] for n in orden], "columna_masa": [columna_masa[n] for n in orden],
            "cambios": cambios, "descartes": descartes, "gigantes_en_riesgo": gigantes,
            "gigantes_lectura": ("Los favoritos del 65-79% cayeron 6 de 19 en 26/27 (uno y medio por jornada); "
                                 "el que cae lo nombra el ojeador con las señales que avisaron en 6 de 7 sorpresas: "
                                 "favorito que viene de perder, rotacion declarada, rival en racha."),
            "x_en_columna": sum(1 for n in orden if columna[n] == "X"),
            "esperados_valiente": esperados(columna, partidos, masa),
            "esperados_masa": esperados(columna_masa, partidos, masa),
            "fuente_masa": "porcentajes_lae" if masa else "mercado_losilla/motor",
            "lectura": ("La columna de la masa hizo 10, 8, 8 y 10 en las Champions de 26/27 y nunca lleva X. "
                        "Esta columna coloca las X donde salen (sin dueno), tumba un gigante y no se fia del "
                        "espanol de media tabla fuera. Expectativa parecida, forma de resultado real.")}


def _signos_reales(jornada, dir_jornadas=None):
    datos = cargar_json((dir_jornadas or JORNADAS_DIR) / f"jornada_{jornada}.json", {}) or {}
    reales = {}
    for p in datos.get("partidos", []):
        if isinstance(p.get("num"), int) and p["num"] <= 14:
            reales[p["num"]] = p.get("signo_oficial")
    if len(reales) < 14 or any(s not in SIGNOS for s in reales.values()):
        return None
    return [reales[n] for n in sorted(reales)]


def resumen_marcador(registros):
    n = len(registros)
    if not n:
        return {"jornadas_evaluadas": 0, "veredicto": "sin_datos"}
    difs = [r["aciertos_valiente"] - r["aciertos_masa"] for r in registros]
    media = sum(difs) / n
    if n >= GRADUACION_MIN_JORNADAS and media >= GRADUACION_VENTAJA:
        veredicto = "candidata"
    elif n >= GRADUACION_MIN_JORNADAS and media <= SUSPENSION_DESVENTAJA:
        veredicto = "suspendida"
    else:
        veredicto = "en_prueba"
    por_regla = {}
    for r in registros:
        for c in r.get("cambios", []):
            d = por_regla.setdefault(c["regla"], {"cambios": 0, "aciertos": 0, "acertaba_masa": 0})
            d["cambios"] += 1
            d["aciertos"] += int(c.get("acierto", False))
            d["acertaba_masa"] += int(c.get("acertaba_masa", False))
    return {"jornadas_evaluadas": n, "aciertos_valiente": sum(r["aciertos_valiente"] for r in registros),
            "aciertos_masa": sum(r["aciertos_masa"] for r in registros), "media_diferencia": round(media, 2),
            "x_acertadas": sum(r.get("x_acertadas", 0) for r in registros),
            "x_salidas": sum(r.get("x_salidas", 0) for r in registros),
            "por_regla": por_regla, "veredicto": veredicto}


def evaluar(bloque, reales):
    col, masa_col = bloque["columna"], bloque["columna_masa"]
    cambios = []
    for c in bloque.get("cambios", []):
        real = reales[c["num"] - 1]
        cambios.append({**{k: c[k] for k in ("num", "local", "visitante", "de", "a", "regla")},
                        "real": real, "acierto": real == c["a"], "acertaba_masa": real == c["de"]})
    return {"aciertos_valiente": sum(a == r for a, r in zip(col, reales)),
            "aciertos_masa": sum(a == r for a, r in zip(masa_col, reales)),
            "x_salidas": reales.count("X"), "x_acertadas": sum(1 for a, r in zip(col, reales) if a == r == "X"),
            "cambios": cambios}


def actualizar_marcador(dir_predicciones=None, dir_jornadas=None, ruta_marcador=None, etiqueta=None, ahora=None,
                        dir_snapshots=None):
    """Registra cada jornada europea cerrada una sola vez (idempotente).

    Auditoria 26/11: el bloque se lee del snapshot PRE-CIERRE (no del espejo
    data/predicciones, que se reescribe con la jornada en juego) y la
    temporada sale de la fecha de la jornada, no de now(). dir_predicciones
    se conserva en la firma pero ya no se lee."""
    from senal_valiente import bloques_del_cierre
    dir_jornadas = Path(dir_jornadas or JORNADAS_DIR)
    ruta_marcador = ruta_marcador or MARCADOR
    ahora = ahora or datetime.now(timezone.utc)
    marcador = cargar_json(ruta_marcador, {}) or {}
    registros = marcador.get("registros", [])
    vistos = {(r.get("temporada"), r.get("jornada")) for r in registros}
    nuevas = 0
    for etiqueta, jornada, bloque, _pred, _datos in bloques_del_cierre(
            "columna_valiente", dir_jornadas, dir_snapshots, etiqueta):
        if bloque.get("estado") != "ok" or (etiqueta, jornada) in vistos:
            continue
        reales = _signos_reales(jornada, dir_jornadas)
        if not reales:
            continue
        registros.append({"temporada": etiqueta, "jornada": jornada, "registrado_en": ahora.isoformat(),
                          "columna": bloque["columna"], "columna_masa": bloque["columna_masa"], "reales": reales,
                          **evaluar(bloque, reales)})
        vistos.add((etiqueta, jornada))
        nuevas += 1
    registros.sort(key=lambda r: (r.get("temporada"), r.get("registrado_en")))
    resumen = resumen_marcador(registros)
    guardar_json(ruta_marcador, {"version": 1, "modo": "sombra", "actualizado_en": ahora.isoformat(),
                                 "criterio": CRITERIO_GRADUACION, "resumen": resumen, "registros": registros})
    return {"nuevas": nuevas, "resumen": resumen}


def backtest(jornadas=(5, 13, 15, 19), etiqueta="2026_2027"):
    """Retrospectivo IN-SAMPLE sobre los snapshots pre-cierre: las reglas se
    derivaron de estas mismas jornadas, asi que solo mide coherencia, no
    capacidad predictiva. Se publica con esa advertencia."""
    resultados = []
    for j in jornadas:
        snap = cargar_json(DATA / "backtesting" / "pre_cierre" / f"jornada_{j}.json", {}) or {}
        pred = snap.get("prediccion", snap)
        if not pred.get("partidos"):
            continue
        masa = cargar_masa(j, etiqueta)
        reales = _signos_reales(j)
        if not masa or not reales:
            continue
        pred = dict(pred)
        pred["jornada"] = j
        pred.pop("sorpresa_nombrada", None)  # el modulo no existia: solo R1-R4
        bloque = construir_bloque(pred, masa)
        if bloque.get("estado") != "ok":
            resultados.append({"jornada": j, "estado": bloque.get("estado"), "motivo": bloque.get("motivo")})
            continue
        resultados.append({"jornada": j, **evaluar(bloque, reales), "columna": bloque["columna"],
                           "columna_masa": bloque["columna_masa"], "reales": reales})
    ok = [r for r in resultados if "aciertos_valiente" in r]
    salida = {"generado_en": datetime.now(timezone.utc).isoformat(), "jornadas": resultados,
              "total_valiente": sum(r["aciertos_valiente"] for r in ok),
              "total_masa": sum(r["aciertos_masa"] for r in ok),
              "x_acertadas": sum(r["x_acertadas"] for r in ok), "x_salidas": sum(r["x_salidas"] for r in ok),
              "advertencia": ("IN-SAMPLE: las reglas R1-R4 se midieron en estas mismas 4 jornadas. Este numero "
                              "no demuestra nada hacia delante; solo el marcador prospectivo cuenta.")}
    guardar_json(BACKTEST, salida)
    return salida


def main():
    if "--backtest" in sys.argv:
        r = backtest()
        print(f"Backtest in-sample columna valiente: {r['total_valiente']} vs masa {r['total_masa']} "
              f"(X acertadas {r['x_acertadas']} de {r['x_salidas']})")
        return
    prediccion = cargar_json(PREDICCION, {})
    if not prediccion:
        print("Sin ultima_prediccion.json; nada que construir.")
        return
    if not prediccion.get("prediccion_disponible") or not prediccion.get("prediccion_permitida"):
        if prediccion.pop("columna_valiente", None) is not None:
            guardar_json(PREDICCION, prediccion)
        print("Prediccion bloqueada o no disponible; bloque columna_valiente retirado.")
        return
    bloque = construir_bloque(prediccion)
    prediccion["columna_valiente"] = bloque
    guardar_json(PREDICCION, prediccion)
    jornada = prediccion.get("jornada")
    espejo = PREDICCIONES_DIR / f"jornada_{jornada}.json"
    if isinstance(jornada, int) and espejo.exists():
        datos = cargar_json(espejo, {})
        if datos.get("jornada") == jornada:
            datos["columna_valiente"] = bloque
            guardar_json(espejo, datos)
    if bloque.get("estado") == "ok":
        cambios = ", ".join(f"P{c['num']} {c['de']}->{c['a']} ({c['regla']})" for c in bloque["cambios"])
        print(f"Columna valiente (sombra) J{jornada}: {' '.join(bloque['columna'])} | masa: "
              f"{' '.join(bloque['columna_masa'])} | cambios: {cambios}")
    else:
        print(f"Columna valiente (sombra) J{jornada}: {bloque.get('estado')} - {bloque.get('motivo')}")


if __name__ == "__main__":
    main()
