import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import generar_contexto_competitivo as contexto_mod

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
HISTORICO_LIGAS_ESPANA = DATA / "memoria_ia" / "historico_ligas_espana.json"
OUT = DATA / "memoria_ia" / "patrones_competitivos.json"
OUT_H2H = DATA / "memoria_ia" / "historial_enfrentamientos.json"
MEMORIA = DATA / "memoria_ia" / "aprendizaje_global.json"
CONTEXTO = DATA / "memoria_ia" / "contexto_competitivo.json"

ANALIZADORES = {
    "primera": contexto_mod.analizar_primera,
    "segunda": contexto_mod.analizar_segunda,
}

# Antes del primer dia de una temporada no hay tabla previa alguna -saltarlo
# evita analizar un contexto vacio sin sentido.
MIN_EQUIPOS_PARA_ANALIZAR = 1

# Un cruce con menos de 2 partidos con cuotas conocidas no da una tasa fiable
# -se guarda igualmente el historial, pero sin "tasa_sorpresa_historica".
MIN_CASOS_CON_CUOTAS_PARA_TASA = 2

# Por debajo de este % de probabilidad implicita de mercado, una brecha de tabla
# (top10 vs resto) se considera "sin margen real amplio" -ver caso Brommapojkarna-
# Hammarby (jornada 74, 2026-07-26): favorito de tabla y de mercado coincidian, pero
# la probabilidad implicita real (49-58%) no reflejaba una diferencia de clase tan
# grande como sugeria la posicion en tabla.
UMBRAL_MARGEN_ESTRECHO = 55.0

# Regla 11 (feedback_metodo_prediccion_manual.md): "el equipo que llega con
# una racha de derrotas esta mas necesitado y por eso rinde mejor/reacciona"
# es un mito, verificado con datos reales de 3 temporadas (2.526 partidos)
# tras el caso Kristiansund 1-2 Start (jornada 74, 2026-07-25). Un equipo
# con 3 derrotas seguidas SIN puntuar rinde PEOR de lo normal en el
# siguiente partido, no mejor -3 es el mismo umbral que usa el campo
# racha_actual.derrotas ya vivo en el pipeline (recalcular_dinamicas_calendario.py).
UMBRAL_RACHA_DERROTAS_SIN_PUNTUAR = 3


def racha_derrotas_previa(historial_puntos, equipo, umbral=UMBRAL_RACHA_DERROTAS_SIN_PUNTUAR):
    """Replica la semantica de racha_actual.derrotas del pipeline en vivo:
    derrotas CONSECUTIVAS que terminan en el partido mas reciente de ESE
    equipo -0 si su ultimo partido registrado no fue una derrota. Se basa
    solo en partidos YA jugados antes de la fecha actual (historial_puntos
    se actualiza despues de procesar cada dia, nunca antes)."""
    pasados = historial_puntos.get(equipo) or []
    if not pasados or pasados[-1] != 0:
        return 0
    derrotas = 0
    for puntos in reversed(pasados):
        if puntos == 0:
            derrotas += 1
        else:
            break
    return derrotas


def puntos_del_resultado(gl, gv, es_local):
    if gl == gv:
        return 1
    gano_local = gl > gv
    return 3 if (gano_local == es_local) else 0


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def tabla_vacia():
    return defaultdict(lambda: {"equipo": "", "pj": 0, "gf": 0, "gc": 0, "puntos": 0})


def aplicar_partido(tabla, local, visitante, gl, gv):
    tabla[local]["equipo"] = tabla[local]["equipo"] or local
    tabla[visitante]["equipo"] = tabla[visitante]["equipo"] or visitante
    tabla[local]["pj"] += 1
    tabla[visitante]["pj"] += 1
    tabla[local]["gf"] += gl
    tabla[local]["gc"] += gv
    tabla[visitante]["gf"] += gv
    tabla[visitante]["gc"] += gl
    if gl > gv:
        tabla[local]["puntos"] += 3
    elif gl < gv:
        tabla[visitante]["puntos"] += 3
    else:
        tabla[local]["puntos"] += 1
        tabla[visitante]["puntos"] += 1


def tabla_a_lista_ordenada(tabla):
    filas = []
    for datos in tabla.values():
        if datos["pj"] <= 0:
            continue
        filas.append({
            "equipo": datos["equipo"],
            "pj": datos["pj"],
            "puntos": datos["puntos"],
            "dg": datos["gf"] - datos["gc"],
            "gf": datos["gf"],
        })
    filas.sort(key=lambda e: (-e["puntos"], -e["dg"], -e["gf"], e["equipo"]))
    for idx, fila in enumerate(filas, start=1):
        fila["posicion"] = idx
    return filas


def objetivo_cerrado(equipo):
    return bool(equipo) and not equipo.get("objetivos_vivos")


def necesidad_viva(equipo):
    return bool(equipo) and bool(equipo.get("objetivos_vivos"))


def descenso_vivo(equipo):
    if not necesidad_viva(equipo):
        return False
    return equipo.get("situacion_competitiva") in {
        "en_descenso_con_opciones", "riesgo_descenso", "permanencia_por_cerrar",
    }


def puntos_de(equipo):
    try:
        return float((equipo or {}).get("puntos") or 0)
    except Exception:
        return 0.0


def tier_por_posicion(equipo, corte=10):
    """Mitad alta (1-10) contra el resto de la tabla (11 en adelante, sea
    Primera con 20 equipos o Segunda con 22) -clase pura por posicion en ESE
    momento de la temporada, sin mirar objetivos ni si hay descenso/ascenso
    en juego. Complementa a los patrones de objetivos: un equipo del top 10
    puede no tener nada "en juego" segun evaluar_plaza/evaluar_descenso y
    aun asi ser claramente mejor que uno de la zona baja."""
    if not equipo:
        return None
    posicion = equipo.get("posicion")
    if not isinstance(posicion, int) or posicion <= 0:
        return None
    return "top10" if posicion <= corte else "resto"


def base_patron():
    return {"casos": 0, "sorpresas": 0, "tasa_sorpresa": 0.0, "ejemplos": []}


def registrar(patrones, clave, sorpresa, ejemplo):
    patron = patrones[clave]
    patron["casos"] += 1
    if sorpresa:
        patron["sorpresas"] += 1
    if sorpresa or len(patron["ejemplos"]) < 8:
        patron["ejemplos"].append(ejemplo)
        patron["ejemplos"] = patron["ejemplos"][-12:]


def ejemplo(liga, temporada, fecha, partido, signo, lectura):
    return {
        "liga": liga,
        "temporada": temporada,
        "fecha": fecha,
        "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
        "resultado": partido.get("resultado"),
        "signo_real": signo,
        "lectura": lectura,
    }


def cargar_partidos_por_temporada(historico, liga):
    temporadas = ((historico.get("ligas") or {}).get(liga) or {}).get("temporadas") or {}
    bloques = []
    for temporada in sorted(temporadas.keys()):
        partidos = sorted(
            (temporadas[temporada].get("partidos") or []),
            key=lambda p: p.get("fecha") or "",
        )
        if partidos:
            bloques.append((temporada, partidos))
    return bloques


def analizar_temporada_historica(liga, temporada, partidos, patrones):
    """Reconstruye la tabla dia a dia (no jornada a jornada, este origen de
    datos no trae numero de jornada) y usa la situacion competitiva real de
    CADA MOMENTO -nunca la de hoy, ni la de partidos futuros de esa misma
    temporada- para saber si un resultado fue una sorpresa respecto a lo que
    la motivacion de cada equipo hacia esperar."""
    analizador = ANALIZADORES[liga]
    tabla = tabla_vacia()
    historial_puntos = defaultdict(list)

    por_fecha = defaultdict(list)
    for p in partidos:
        if p.get("signo") in ("1", "X", "2") and p.get("local") and p.get("visitante"):
            por_fecha[p.get("fecha") or ""].append(p)

    for fecha in sorted(por_fecha.keys()):
        partidos_del_dia = por_fecha[fecha]

        tabla_previa = tabla_a_lista_ordenada(tabla)
        mapa = {}
        if len(tabla_previa) >= MIN_EQUIPOS_PARA_ANALIZAR:
            analisis = analizador(tabla_previa)
            mapa = {e.get("clave", contexto_mod.normalizar_nombre(e.get("equipo"))): e for e in analisis.get("equipos", [])}

        for partido in partidos_del_dia:
            signo = partido.get("signo")
            local = mapa.get(contexto_mod.normalizar_nombre(partido.get("local", "")))
            visitante = mapa.get(contexto_mod.normalizar_nombre(partido.get("visitante", "")))

            clave_local = contexto_mod.normalizar_nombre(partido.get("local", ""))
            clave_visitante = contexto_mod.normalizar_nombre(partido.get("visitante", ""))
            visitante_racha = racha_derrotas_previa(historial_puntos, clave_visitante)
            local_racha = racha_derrotas_previa(historial_puntos, clave_local)

            if local and visitante:
                local_cerrado = objetivo_cerrado(local)
                visitante_cerrado = objetivo_cerrado(visitante)
                local_necesita = necesidad_viva(local)
                visitante_necesita = necesidad_viva(visitante)
                local_descenso = descenso_vivo(local)
                visitante_descenso = descenso_vivo(visitante)
                local_favorito = puntos_de(local) >= puntos_de(visitante) + 5
                visitante_favorito = puntos_de(visitante) >= puntos_de(local) + 5

                if visitante_cerrado and local_necesita:
                    registrar(
                        patrones, "necesitado_local_vs_visitante_objetivo_cerrado", signo != "2",
                        ejemplo(liga, temporada, fecha, partido, signo,
                                "El local con objetivo vivo puntua o gana ante visitante con objetivo cerrado."),
                    )
                if local_cerrado and visitante_necesita:
                    registrar(
                        patrones, "visitante_necesitado_vs_local_objetivo_cerrado", signo != "1",
                        ejemplo(liga, temporada, fecha, partido, signo,
                                "El visitante con objetivo vivo puntua o gana ante local con objetivo cerrado."),
                    )
                if visitante_descenso and local_favorito:
                    registrar(
                        patrones, "visitante_descenso_vs_local_favorito", signo != "1",
                        ejemplo(liga, temporada, fecha, partido, signo,
                                "Visitante con urgencia de descenso/permanencia rompe o amenaza el 1 fijo."),
                    )
                if local_descenso and visitante_favorito:
                    registrar(
                        patrones, "local_descenso_vs_visitante_favorito", signo != "2",
                        ejemplo(liga, temporada, fecha, partido, signo,
                                "Local con urgencia de descenso/permanencia rompe o amenaza el 2 fijo."),
                    )
                if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
                    sorpresa = (local_necesita and signo != "2") or (visitante_necesita and signo != "1")
                    registrar(
                        patrones, "equipo_necesitado_vs_equipo_sin_objetivo", sorpresa,
                        ejemplo(liga, temporada, fecha, partido, signo,
                                "Choque necesidad contra objetivo cerrado: no tratar al equipo sin objetivo como fijo limpio."),
                    )

                local_tier = tier_por_posicion(local)
                visitante_tier = tier_por_posicion(visitante)
                tier_favorito_signo = None
                if local_tier == "top10" and visitante_tier == "resto":
                    tier_favorito_signo = "1"
                    registrar(
                        patrones, "top10_local_vs_resto_visitante", signo != "1",
                        ejemplo(liga, temporada, fecha, partido, signo,
                                "Local del top 10 recibe a un equipo de la segunda mitad de la tabla."),
                    )
                elif visitante_tier == "top10" and local_tier == "resto":
                    tier_favorito_signo = "2"
                    registrar(
                        patrones, "top10_visitante_vs_resto_local", signo != "2",
                        ejemplo(liga, temporada, fecha, partido, signo,
                                "Visitante del top 10 viaja a un equipo de la segunda mitad de la tabla."),
                    )

                # Matiz pedido por Marc tras el fallo real de la jornada 74 (Brommapojkarna-Hammarby,
                # 2026-07-26): una brecha de posicion en tabla (top10 vs resto) no siempre viene
                # respaldada por un margen real amplio. Version corregida tras un primer intento
                # fallido: al principio se comparo "direccion tabla vs direccion mercado", pero el
                # caso real que motivo esto tenia mercado Y tabla de acuerdo (ambos favorecian al
                # equipo del top 10) -lo que de verdad bajaba la confianza era que la PROBABILIDAD
                # implicita de mercado para ese favorito de tabla era corta (no habia margen real),
                # no que el mercado señalara a otro signo distinto. Por eso aqui se mide el MARGEN
                # (probabilidad implicita de las cuotas para el signo de tabla), no solo la direccion.
                if tier_favorito_signo:
                    probs_mercado = probabilidad_implicita_cuotas(partido)
                    prob_favorito_mercado = probs_mercado.get(tier_favorito_signo)
                    if prob_favorito_mercado is not None:
                        clave_brecha = (
                            "brecha_tabla_margen_estrecho_mercado"
                            if prob_favorito_mercado < UMBRAL_MARGEN_ESTRECHO
                            else "brecha_tabla_margen_amplio_mercado"
                        )
                        registrar(
                            patrones, clave_brecha, signo != tier_favorito_signo,
                            ejemplo(liga, temporada, fecha, partido, signo,
                                    f"Brecha de tabla top10 vs resto; favorito de tabla={tier_favorito_signo}, "
                                    f"probabilidad implicita de mercado para ese favorito={prob_favorito_mercado:.1f}%."),
                        )

                # Matiz pedido por Marc (2026-08), a raiz de comprobar con datos reales
                # que el Barcelona -ya campeon en la jornada 35 de LaLiga 2025/26- jugo con
                # alineacion alternativa y perdio 2 de los 3 partidos sin nada en juego que
                # le quedaban (Alaves 1-0, Valencia 3-1): un "rebote" de la racha perdedora
                # contra un rival SIN objetivo (que puede rotar/no exigirse al maximo) no
                # prueba lo mismo que un rebote contra un rival que SI se lo juega todo. Se
                # cruza aqui, no en el bloque de mas abajo, porque necesita el contexto
                # competitivo del rival (objetivo_cerrado), que solo existe dentro de este if.
                if visitante_racha >= UMBRAL_RACHA_DERROTAS_SIN_PUNTUAR:
                    clave_rival = (
                        "racha_perdedora_visitante_no_rebota_rival_sin_objetivo" if local_cerrado
                        else "racha_perdedora_visitante_no_rebota_rival_motivado"
                    )
                    registrar(
                        patrones, clave_rival, signo == "2",
                        ejemplo(liga, temporada, fecha, partido, signo,
                                f"Visitante con {visitante_racha} derrotas seguidas; rival local con objetivo "
                                f"{'cerrado (puede rotar)' if local_cerrado else 'vivo (se lo juega)'}."),
                    )
                if local_racha >= UMBRAL_RACHA_DERROTAS_SIN_PUNTUAR:
                    clave_rival = (
                        "racha_perdedora_local_no_rebota_rival_sin_objetivo" if visitante_cerrado
                        else "racha_perdedora_local_no_rebota_rival_motivado"
                    )
                    registrar(
                        patrones, clave_rival, signo == "1",
                        ejemplo(liga, temporada, fecha, partido, signo,
                                f"Local con {local_racha} derrotas seguidas; rival visitante con objetivo "
                                f"{'cerrado (puede rotar)' if visitante_cerrado else 'vivo (se lo juega)'}."),
                    )

            # Regla 11: "necesidad por racha de derrotas" -verificar si un equipo
            # que llega con >=3 derrotas seguidas SIN puntuar de verdad "rebota"
            # (gana) mas de lo esperable, o si -como confirmo el analisis manual
            # con datos reales- sigue rindiendo peor. Se mide en TODOS los
            # partidos con historial suficiente, no solo cuando hay contexto
            # competitivo de tabla (local/visitante de arriba), porque esto es
            # una propiedad de la racha reciente, no de la clasificacion.
            if visitante_racha >= UMBRAL_RACHA_DERROTAS_SIN_PUNTUAR:
                registrar(
                    patrones, "racha_perdedora_visitante_no_rebota", signo == "2",
                    ejemplo(liga, temporada, fecha, partido, signo,
                            f"Visitante llega con {visitante_racha} derrotas seguidas sin puntuar: "
                            "la 'necesidad' no predice un rebote, historicamente rinde peor."),
                )
            if local_racha >= UMBRAL_RACHA_DERROTAS_SIN_PUNTUAR:
                registrar(
                    patrones, "racha_perdedora_local_no_rebota", signo == "1",
                    ejemplo(liga, temporada, fecha, partido, signo,
                            f"Local llega con {local_racha} derrotas seguidas sin puntuar: "
                            "la 'necesidad' no predice un rebote, historicamente rinde peor."),
                )

            aplicar_partido(tabla, partido.get("local", ""), partido.get("visitante", ""), partido["gl"], partido["gv"])
            historial_puntos[clave_local].append(puntos_del_resultado(partido["gl"], partido["gv"], es_local=True))
            historial_puntos[clave_visitante].append(puntos_del_resultado(partido["gl"], partido["gv"], es_local=False))


def normalizar_equipo_h2h(nombre):
    return contexto_mod.normalizar_nombre(nombre)


def clave_par_equipos(a, b):
    return "__".join(sorted([normalizar_equipo_h2h(a), normalizar_equipo_h2h(b)]))


def favorito_por_cuotas(partido):
    """El favorito de mercado en AQUEL momento -la cuota mas baja gana-, no
    la clasificacion de hoy. Es la señal que pide Marc: motivacion extra o
    incomodidad especifica entre estos dos equipos en concreto, presente
    durante toda la temporada y no solo cuando hay descenso/ascenso en juego."""
    c1, cx, c2 = partido.get("cuota_1"), partido.get("cuota_x"), partido.get("cuota_2")
    if not (c1 and cx and c2):
        return None
    cuotas = {"1": c1, "X": cx, "2": c2}
    return min(cuotas, key=cuotas.get)


def probabilidad_implicita_cuotas(partido):
    """Probabilidad implicita normalizada (100/cuota, repartida a que sume 100)
    por signo, o {} si no hay las 3 cuotas. Es el margen REAL que el mercado
    daba a cada signo en aquel momento -mas preciso que solo mirar "cual cuota
    es mas baja" (favorito_por_cuotas), porque dos partidos pueden compartir
    el mismo favorito y aun asi tener un margen muy distinto (60% no es lo
    mismo que 35% aunque los dos sean "el mas probable")."""
    c1, cx, c2 = partido.get("cuota_1"), partido.get("cuota_x"), partido.get("cuota_2")
    if not (c1 and cx and c2):
        return {}
    inversas = {"1": 1.0 / c1, "X": 1.0 / cx, "2": 1.0 / c2}
    total = sum(inversas.values())
    if total <= 0:
        return {}
    return {signo: valor / total * 100 for signo, valor in inversas.items()}


def analizar_enfrentamientos_directos(historico):
    pares = defaultdict(lambda: {
        "equipos": [],
        "casos_totales": 0,
        "casos_con_cuotas": 0,
        "sorpresas": 0,
        "tasa_sorpresa_historica": None,
        "ejemplos": [],
    })

    for liga, info in (historico.get("ligas") or {}).items():
        for partido in ((info.get("consolidado") or {}).get("partidos") or []):
            local = partido.get("local", "")
            visitante = partido.get("visitante", "")
            if not local or not visitante:
                continue

            clave = clave_par_equipos(local, visitante)
            entrada = pares[clave]
            if not entrada["equipos"]:
                entrada["equipos"] = sorted([local, visitante])
            entrada["casos_totales"] += 1

            favorito = favorito_por_cuotas(partido)
            es_sorpresa = bool(favorito) and partido.get("signo") != favorito
            if favorito:
                entrada["casos_con_cuotas"] += 1
                if es_sorpresa:
                    entrada["sorpresas"] += 1

            registro = {
                "liga": liga,
                "temporada": partido.get("temporada"),
                "fecha": partido.get("fecha"),
                "local": local,
                "visitante": visitante,
                "resultado": partido.get("resultado"),
                "signo": partido.get("signo"),
                "favorito_cuotas": favorito,
                "sorpresa": es_sorpresa,
            }
            if es_sorpresa or len(entrada["ejemplos"]) < 8:
                entrada["ejemplos"].append(registro)
                entrada["ejemplos"] = entrada["ejemplos"][-10:]

    salida = {}
    for clave, entrada in pares.items():
        casos_cuotas = entrada["casos_con_cuotas"]
        if casos_cuotas >= MIN_CASOS_CON_CUOTAS_PARA_TASA:
            entrada["tasa_sorpresa_historica"] = round(entrada["sorpresas"] / casos_cuotas * 100, 1)
        salida[clave] = entrada
    return salida


def analizar():
    historico = cargar_json(HISTORICO_LIGAS_ESPANA, {})
    patrones = defaultdict(base_patron)
    temporadas_analizadas = {}

    for liga in ANALIZADORES:
        temporadas_analizadas[liga] = []
        for temporada, partidos in cargar_partidos_por_temporada(historico, liga):
            analizar_temporada_historica(liga, temporada, partidos, patrones)
            temporadas_analizadas[liga].append(temporada)

    salida_patrones = {}
    for clave, patron in sorted(patrones.items()):
        casos = patron["casos"] or 1
        patron["tasa_sorpresa"] = round(patron["sorpresas"] / casos * 100, 1)
        salida_patrones[clave] = dict(patron)

    salida = {
        "version": "3.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": (
            "Patrones aprendidos de las 3 temporadas reales cargadas en "
            "data/memoria_ia/historico_ligas_espana.json, reconstruyendo la "
            "situacion competitiva real de cada equipo dia a dia -no "
            "comparando contra la clasificacion de HOY."
        ),
        "temporadas_analizadas": temporadas_analizadas,
        "patrones": salida_patrones,
        "regla_uso": "Si un patron supera el 30% de sorpresa, sube incertidumbre; si supera el 45%, recomienda cobertura cuando haya dobles/triples.",
    }

    guardar_json(OUT, salida)

    memoria = cargar_json(MEMORIA, {})
    memoria["patrones_competitivos"] = salida
    guardar_json(MEMORIA, memoria)

    contexto = cargar_json(CONTEXTO, {})
    contexto["patrones_aprendidos"] = salida
    guardar_json(CONTEXTO, contexto)

    h2h = analizar_enfrentamientos_directos(historico)
    salida_h2h = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": (
            "Historial de enfrentamientos directos entre cada par de equipos "
            "en las 3 temporadas cargadas, usando el favorito de mercado de "
            "cada partido (cuotas de aquel momento) para medir si ese cruce "
            "concreto tiende a dar sorpresas -independiente de lo que se "
            "juegue la clasificacion esta temporada."
        ),
        "minimo_casos_para_tasa": MIN_CASOS_CON_CUOTAS_PARA_TASA,
        "enfrentamientos": h2h,
    }
    guardar_json(OUT_H2H, salida_h2h)

    print(f"Patrones competitivos aprendidos: {OUT}")
    for clave, patron in salida_patrones.items():
        print(f"  {clave}: {patron['casos']} casos, {patron['tasa_sorpresa']}% sorpresa")
    print(f"Historial de enfrentamientos directos: {OUT_H2H}")
    con_tasa = [e for e in h2h.values() if e["tasa_sorpresa_historica"] is not None]
    print(f"  {len(h2h)} cruces distintos, {len(con_tasa)} con suficientes cuotas para tener tasa")


if __name__ == "__main__":
    analizar()
