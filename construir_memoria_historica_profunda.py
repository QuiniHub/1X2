"""
Construye la memoria histórica profunda de la IA a partir de:
1. Los JSONs de jornadas (temporada 2025/2026)
2. El historial de quinielas (CSV)
3. Los perfiles de equipos
4. Los patrones competitivos existentes

Genera data/memoria_ia/memoria_historica_profunda.json
Este archivo es la "alma" de la IA — todo lo que sabe sobre el fútbol.
NO se muestra en la web. Es para uso interno del chat IA.
"""
import json
import csv
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter

import cronologia_jornadas

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
SALIDA = DATA / "memoria_ia" / "memoria_historica_profunda.json"

def cargar_json(path, default=None):
    if default is None:
        default = {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except:
        return default

def signo_resultado(resultado):
    try:
        g1, g2 = [int(x) for x in str(resultado).split("-")]
        return "1" if g1 > g2 else "X" if g1 == g2 else "2"
    except:
        return ""

NOMBRES_PESO = {
    "forma_reciente": "la FORMA RECIENTE",
    "casa_fuera": "el factor CASA/FUERA",
    "clasificacion": "la CLASIFICACIÓN",
    "goles": "los GOLES",
    "empate": "el EMPATE",
    "sorpresa": "la SORPRESA",
    "motivacion_competitiva": "la MOTIVACIÓN COMPETITIVA",
    "necesidad_descenso_ascenso_europa": "la NECESIDAD (descenso/ascenso/Europa)",
    "fatiga": "la FATIGA",
    "bajas": "las BAJAS",
}

def describir_pesos_aprendidos(pesos_actuales, referencia):
    cambios = []
    for clave, ref_valor in (referencia or {}).items():
        actual = (pesos_actuales or {}).get(clave)
        if actual is None or not ref_valor:
            continue
        cambios.append((clave, (actual - ref_valor) / ref_valor * 100))
    if not cambios:
        return []

    suben = sorted([c for c in cambios if c[1] > 15], key=lambda c: -c[1])[:2]
    bajan = sorted([c for c in cambios if c[1] < -15], key=lambda c: c[1])[:2]
    estables = sorted([c for c in cambios if abs(c[1]) <= 15], key=lambda c: abs(c[1]))[:2]

    lineas = []
    for clave, pct in suben:
        lineas.append(f"- {NOMBRES_PESO.get(clave, clave.upper())} pesa más de lo esperado — ha subido un {abs(round(pct))}% sobre mi referencia base.")
    for clave, pct in bajan:
        lineas.append(f"- {NOMBRES_PESO.get(clave, clave.upper())} la he reducido un {abs(round(pct))}% — engañaba más de lo que ayudaba.")
    if estables:
        nombres = " y ".join(NOMBRES_PESO.get(c[0], c[0].upper()) for c in estables)
        lineas.append(f"- {nombres} son los factores que menos he tenido que tocar — los más fiables desde el inicio.")
    return lineas

ESTADOS_TEXTO = {
    "bloqueada": "bloqueada, esperando el cierre de la jornada anterior",
    "aprendiendo": "aprendiendo de la jornada anterior antes de predecir la siguiente",
    "lista_para_publicar": "lista para publicar",
    "publicada": "publicada",
}

def describir_estado_actual(ultima_prediccion):
    jornada = ultima_prediccion.get("jornada")
    estado = ultima_prediccion.get("estado") or "desconocido"
    if not jornada:
        return "sin datos de jornada disponibles ahora mismo."
    texto = ESTADOS_TEXTO.get(estado, estado)
    frase = f"J{jornada} en estado: {texto}."
    motivo = ultima_prediccion.get("motivo_bloqueo")
    if estado == "bloqueada" and motivo:
        frase += f" Motivo: {motivo}."
    return frase

def _entero(valor):
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return 0


def etiqueta_temporada(temporada):
    """'2026_2027' -> '26/27'."""
    partes = str(temporada or "").split("_")
    if len(partes) == 2 and all(len(p) == 4 and p.isdigit() for p in partes):
        return f"{partes[0][2:]}/{partes[1][2:]}"
    return str(temporada or "?")


def resumen_premios(premios, jugadas, indice):
    """Mejor/peor jornada, total cobrado y precision de las quinielas JUGADAS.

    Auditoria 26/11: el bucle hacia 'if num < 61: continue', un filtro por
    NUMERO de jornada que dejaba fuera la temporada 26/27 entera (J1-J24): el
    chat decia 'mejor J70, total cobrado 97,34' con 237,72 EUR y dos jornadas
    de 13 aciertos sin contar. Ahora cuenta toda jornada con jugada real
    (quinielas_jugadas.json), sea del numero que sea, y cada una lleva su
    temporada y su fecha (la numeracion se reinicia cada agosto).

    premios: lista de historial_premios.json; jugadas: lista de
    quinielas_jugadas.json; indice: cronologia_jornadas.indice_jornadas().
    """
    por_numero = {int(f["numero"]): f for f in (indice or [])}
    jugadas_por_numero = {}
    for jugada in jugadas or []:
        numero = _entero(jugada.get("jornada"))
        if numero:
            jugadas_por_numero[numero] = jugada

    filas = []
    for registro in premios or []:
        numero = _entero(registro.get("jornada"))
        if not numero:
            continue
        aciertos = _entero(registro.get("aciertos"))
        fallos = _entero(registro.get("fallos"))
        if jugadas_por_numero:
            jugada = jugadas_por_numero.get(numero)
            if jugada is None:
                continue
        else:
            jugada = {}
            if aciertos + fallos <= 0:
                continue
        fila_jornada = por_numero.get(numero) or {}
        fecha = fila_jornada.get("fecha") or cronologia_jornadas.parsear_fecha(jugada.get("validado_en"))
        temporada = fila_jornada.get("temporada") or (
            cronologia_jornadas.temporada_de_fecha(fecha, numero) if fecha else None
        )
        # La jugada tiene que ser de la misma temporada que el fichero.
        fecha_jugada = cronologia_jornadas.parsear_fecha(jugada.get("validado_en"))
        if fecha_jugada and temporada:
            if cronologia_jornadas.temporada_de_fecha(fecha_jugada, numero) != temporada:
                continue
        try:
            premio = float(registro.get("premio_eur") or 0)
        except (TypeError, ValueError):
            premio = 0.0
        filas.append({
            "jornada": numero,
            "temporada": temporada,
            "fecha": fecha,
            "aciertos": aciertos,
            "evaluada": aciertos + fallos > 0,
            "premio": premio,
        })

    filas.sort(key=lambda f: (f["fecha"] is not None, f["fecha"] or datetime.min.date(), f["jornada"]))
    evaluadas = [f for f in filas if f["evaluada"]]

    def ficha(fila):
        if not fila:
            return {"jornada": None, "temporada": None, "aciertos": None}
        return {"jornada": fila["jornada"], "temporada": fila["temporada"], "aciertos": fila["aciertos"]}

    mejor = peor = None
    for fila in evaluadas:  # orden cronologico: a igualdad gana la mas reciente
        if mejor is None or fila["aciertos"] >= mejor["aciertos"]:
            mejor = fila
        if peor is None or fila["aciertos"] <= peor["aciertos"]:
            peor = fila

    cobrado_por_temporada = defaultdict(float)
    for fila in filas:
        cobrado_por_temporada[fila["temporada"] or "sin_fecha"] += fila["premio"]
    temporada_actual = evaluadas[-1]["temporada"] if evaluadas else None
    de_la_actual = [f for f in evaluadas if f["temporada"] == temporada_actual]

    total_aciertos = sum(f["aciertos"] for f in evaluadas)
    return {
        "jornadas_evaluadas": len(evaluadas),
        "mejor_jornada": ficha(mejor),
        "peor_jornada": ficha(peor),
        "total_cobrado_eur": round(sum(f["premio"] for f in filas), 2),
        "cobrado_por_temporada_eur": {k: round(v, 2) for k, v in cobrado_por_temporada.items()},
        "precision_media": round(total_aciertos / max(len(evaluadas) * 14, 1) * 100, 1),
        "temporada_actual": temporada_actual,
        "precision_media_temporada_actual": round(
            sum(f["aciertos"] for f in de_la_actual) / max(len(de_la_actual) * 14, 1) * 100, 1
        ),
        "jornadas_temporada_actual": len(de_la_actual),
    }


# Patrones que se cuentan en el chat: (clave en patrones_competitivos.json, texto).
PATRONES_PARA_CHAT = (
    ("equipo_necesitado_vs_equipo_sin_objetivo", "Equipo necesitado vs equipo sin objetivo"),
    ("necesitado_local_vs_visitante_objetivo_cerrado", "Local necesitado vs visitante con objetivo cerrado"),
    ("visitante_necesitado_vs_local_objetivo_cerrado", "Visitante necesitado vs local con objetivo cerrado"),
)


def lineas_patrones(patrones):
    """Lineas del chat sobre patrones competitivos, sacadas del fichero.

    Auditoria 26/11: el texto llevaba cifras escritas a mano ('66% (294
    casos)', '79.6% (147 casos)') que contradecian patrones_competitivos.json
    (87 casos al 69,0%, 44 al 77,3%...). Ahora cada linea sale del dato real y
    avisa cuando la muestra es pequena.
    """
    datos = (patrones or {}).get("patrones") or {}
    lineas = []
    for clave, texto in PATRONES_PARA_CHAT:
        patron = datos.get(clave) or {}
        casos = _entero(patron.get("casos"))
        if casos <= 0:
            continue
        muestra = "muestra amplia" if casos >= 150 else "muestra media" if casos >= 60 else "muestra pequeña, orientativo"
        lineas.append(f"- {texto}: {patron.get('tasa_sorpresa', 0)}% de sorpresa ({casos} casos; {muestra}).")
    return lineas


def construir_memoria():
    print("=== Construyendo memoria histórica profunda ===")
    
    memoria = {
        "version": "1.0",
        "descripcion": "Memoria historica profunda de la IA — conocimiento acumulado sobre futbol y quinielas",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "temporadas_analizadas": [],
        "estadisticas_globales": {},
        "patrones_jornada": {},
        "equipos_destacados": {},
        "aprendizaje_quiniela": {},
        "dinamicas_temporada": {},
        "factores_humanos_validados": {},
        "resumen_para_chat": ""
    }

    # ══════════════════════════════════════════
    # 1. ANALIZAR TODAS LAS JORNADAS JSON
    # ══════════════════════════════════════════
    print("1. Analizando jornadas...")
    
    total_partidos = 0
    signos = Counter()
    sorpresas = 0
    partidos_por_competicion = defaultdict(int)
    tipo_stats = defaultdict(lambda: {"aciertos": 0, "total": 0})
    fijos_fallados = 0
    empates_no_cubiertos = 0
    equipos_stats = defaultdict(lambda: {
        "partidos": 0, "victorias": 0, "empates": 0, "derrotas": 0,
        "gf": 0, "gc": 0, "sorpresas_causadas": 0, "como_local": 0, "como_visitante": 0
    })
    jornadas_data = []
    jornadas_impredecibles = []
    jornadas_predecibles = []

    indice = cronologia_jornadas.indice_jornadas(JORNADAS)
    temporadas_vistas = []
    for fila in indice:  # orden cronologico real, no por numero
        path = Path(fila["ruta"])
        data = cargar_json(path, {})
        jornada_num = int(data.get("jornada", 0) or 0)
        if not jornada_num:
            continue
        
        partidos = data.get("partidos", [])
        signos_jornada = []
        sorpresas_jornada = 0
        
        for p in partidos:
            signo = p.get("signo_oficial", "")
            if signo not in ("1", "X", "2"):
                resultado = p.get("resultado", "")
                signo = signo_resultado(resultado)
            if not signo:
                continue
            
            signos[signo] += 1
            total_partidos += 1
            signos_jornada.append(signo)

            jugado = "".join(c for c in str(p.get("signo_nuestro") or "") if c in "1X2")
            if jugado:
                tipo = "FIJO" if len(jugado) == 1 else "DOBLE" if len(jugado) == 2 else "TRIPLE"
                acierto = p.get("acierto_nuestro")
                if acierto is None:
                    acierto = signo in jugado
                tipo_stats[tipo]["total"] += 1
                if acierto:
                    tipo_stats[tipo]["aciertos"] += 1
                elif tipo == "FIJO":
                    fijos_fallados += 1
                if signo == "X" and "X" not in jugado:
                    empates_no_cubiertos += 1

            local = (p.get("local") or "").lower().strip()
            visitante = (p.get("visitante") or "").lower().strip()
            
            if local:
                equipos_stats[local]["partidos"] += 1
                equipos_stats[local]["como_local"] += 1
                try:
                    resultado_str = p.get("resultado", "")
                    partes = str(resultado_str).split("-") if "-" in str(resultado_str) else ["0","0"]
                    gf_local = int(partes[0]) if partes[0].strip().isdigit() else 0
                    gc_local = int(partes[1]) if len(partes) > 1 and partes[1].strip().isdigit() else 0
                    equipos_stats[local]["gf"] += gf_local
                    equipos_stats[local]["gc"] += gc_local
                except:
                    pass
                if signo == "1":
                    equipos_stats[local]["victorias"] += 1
                elif signo == "X":
                    equipos_stats[local]["empates"] += 1
                else:
                    equipos_stats[local]["derrotas"] += 1
                    sorpresas_jornada += 1
                    sorpresas += 1

            if visitante:
                equipos_stats[visitante]["partidos"] += 1
                equipos_stats[visitante]["como_visitante"] += 1
                if signo == "2":
                    equipos_stats[visitante]["victorias"] += 1
                    # Auditoria 26/11: la victoria fuera se apuntaba al LOCAL
                    # que perdia, y el ranking de "equipos que mas sorprenden"
                    # eran en realidad los que mas pierden en casa.
                    equipos_stats[visitante]["sorpresas_causadas"] += 1
                elif signo == "X":
                    equipos_stats[visitante]["empates"] += 1
                else:
                    equipos_stats[visitante]["derrotas"] += 1
            
            competicion = (p.get("competicion") or p.get("liga") or "liga").lower()
            partidos_por_competicion[competicion] += 1
        
        if signos_jornada:
            if fila.get("temporada") and fila["temporada"] not in temporadas_vistas:
                temporadas_vistas.append(fila["temporada"])
            pct_sorpresa = (signos_jornada.count("X") + signos_jornada.count("2")) / len(signos_jornada) * 100
            jornada_info = {
                "jornada": jornada_num,
                "temporada": fila.get("temporada"),
                "partidos": len(signos_jornada),
                "distribucion": dict(Counter(signos_jornada)),
                "pct_sorpresa": round(pct_sorpresa, 1)
            }
            jornadas_data.append(jornada_info)
            if pct_sorpresa > 60:
                jornadas_impredecibles.append(jornada_info)
            elif pct_sorpresa < 35:
                jornadas_predecibles.append(jornada_info)

    # Estadísticas globales
    if total_partidos > 0:
        memoria["estadisticas_globales"] = {
            "total_partidos_analizados": total_partidos,
            "total_jornadas": len(jornadas_data),
            "frecuencia_1": round(signos["1"] / total_partidos * 100, 1),
            "frecuencia_X": round(signos["X"] / total_partidos * 100, 1),
            "frecuencia_2": round(signos["2"] / total_partidos * 100, 1),
            "pct_sorpresa_global": round(sorpresas / total_partidos * 100, 1),
            "por_competicion": dict(partidos_por_competicion),
            "conclusion": (
                f"En {total_partidos} partidos analizados, gana el local el {round(signos['1']/total_partidos*100,1)}% "
                f"de las veces, hay empate el {round(signos['X']/total_partidos*100,1)}% y gana el visitante "
                f"el {round(signos['2']/total_partidos*100,1)}%."
            ),
            "nota_pct_sorpresa_global": (
                "pct_sorpresa_global es el % de victorias visitantes (no mide sorpresas "
                "contra un favorito real); en patrones_jornada, pct_sorpresa es el % de "
                "partidos en los que NO gana el local."
            ),
        }

    # Jornadas más destacadas
    memoria["patrones_jornada"] = {
        "jornadas_mas_impredecibles": sorted(jornadas_impredecibles, 
            key=lambda x: x["pct_sorpresa"], reverse=True)[:10],
        "jornadas_mas_predecibles": sorted(jornadas_predecibles,
            key=lambda x: x["pct_sorpresa"])[:10],
        "media_sorpresa_por_jornada": round(
            sum(j["pct_sorpresa"] for j in jornadas_data) / len(jornadas_data), 1
        ) if jornadas_data else 0
    }

    # ══════════════════════════════════════════
    # 2. EQUIPOS MÁS DESTACADOS
    # ══════════════════════════════════════════
    print("2. Analizando equipos...")
    
    equipos_con_datos = {
        k: v for k, v in equipos_stats.items() 
        if v["partidos"] >= 5
    }
    
    # Equipos más sorprendentes como visitante
    sorprendentes = sorted(
        [(k, v) for k, v in equipos_con_datos.items() if v["como_visitante"] >= 3],
        key=lambda x: x[1]["sorpresas_causadas"] / max(x[1]["como_visitante"], 1),
        reverse=True
    )[:15]
    
    # Equipos más fiables como local
    fiables_local = sorted(
        [(k, v) for k, v in equipos_con_datos.items() if v["como_local"] >= 5],
        key=lambda x: x[1]["victorias"] / max(x[1]["como_local"], 1),
        reverse=True
    )[:15]
    
    memoria["equipos_destacados"] = {
        "mas_sorprendentes": [
            {
                "equipo": k.title(),
                "partidos": v["partidos"],
                "partidos_visitante": v["como_visitante"],
                "sorpresas_causadas": v["sorpresas_causadas"],
                "pct_sorpresa": round(v["sorpresas_causadas"] / max(v["como_visitante"], 1) * 100, 1)
            }
            for k, v in sorprendentes[:10]
        ],
        "mas_fiables_como_local": [
            {
                "equipo": k.title(),
                "partidos_local": v["como_local"],
                "victorias": v["victorias"],
                "pct_victoria_local": round(v["victorias"] / max(v["como_local"], 1) * 100, 1)
            }
            for k, v in fiables_local[:10]
        ],
        "total_equipos_analizados": len(equipos_con_datos)
    }

    # ══════════════════════════════════════════
    # 3. APRENDIZAJE DE QUINIELAS JUGADAS
    # ══════════════════════════════════════════
    print("3. Analizando quinielas jugadas...")
    
    historial = cargar_json(DATA / "historial_quinielas.json", {})
    premios = cargar_json(DATA / "premios" / "historial_premios.json", {})
    
    jornadas_jugadas = [j for j in historial.get("jornadas", [])
                        if j.get("nuestra_quiniela") and 
                        j.get("nuestra_quiniela") not in ("No jugada", "No validada", "Pendiente")]
    
    jornadas_con_resultado = [j for j in jornadas_jugadas 
                               if j.get("resultado_oficial") and 
                               j.get("resultado_oficial") != "Pendiente"]
    
    jugadas_reales = cargar_json(DATA / "quinielas_jugadas.json", {}).get("jugadas", [])
    rp = resumen_premios(premios.get("jornadas", []), jugadas_reales, indice)

    memoria["aprendizaje_quiniela"] = {
        "jornadas_jugadas": len(jornadas_jugadas),
        "jornadas_con_resultado": len(jornadas_con_resultado),
        "mejor_jornada": rp["mejor_jornada"],
        "peor_jornada": rp["peor_jornada"],
        "total_cobrado_eur": rp["total_cobrado_eur"],
        "cobrado_por_temporada_eur": rp["cobrado_por_temporada_eur"],
        "precision_media": rp["precision_media"],
        "temporada_actual": rp["temporada_actual"],
        "precision_media_temporada_actual": rp["precision_media_temporada_actual"],
        "jornadas_temporada_actual": rp["jornadas_temporada_actual"],
        "fallos_mas_comunes": [
            "Fijo fallado cuando había alerta de motivación activa",
            "No cubrir empate en partidos con alta incertidumbre",
            "Confiar demasiado en el favorito cuando el rival está desesperado",
            "No detectar el factor 'último partido' en equipos eliminados"
        ],
        "estadisticas_fallos": {
            "fijos_fallados": fijos_fallados,
            "empates_no_cubiertos": empates_no_cubiertos,
            "precision_por_tipo": {
                tipo: round(datos["aciertos"] / datos["total"] * 100, 1)
                for tipo, datos in tipo_stats.items() if datos["total"] > 0
            }
        }
    }

    # ══════════════════════════════════════════
    # 4. PATRONES COMPETITIVOS VALIDADOS
    # ══════════════════════════════════════════
    print("4. Cargando patrones competitivos...")
    
    patrones = cargar_json(DATA / "memoria_ia" / "patrones_competitivos.json", {})
    retroalimentacion = cargar_json(DATA / "memoria_ia" / "retroalimentacion_factores.json", {})
    pesos = cargar_json(DATA / "memoria_ia" / "pesos_dinamicos.json", {})
    
    factores_validados = {}
    for key, datos in patrones.get("patrones", {}).items():
        casos = datos.get("casos", 0)
        sorpresas_p = datos.get("sorpresas", 0)
        tasa = datos.get("tasa_sorpresa", 0)
        if casos >= 5:
            factores_validados[key] = {
                "casos": casos,
                "tasa_sorpresa": tasa,
                "fiabilidad": "alta" if tasa > 65 else "media" if tasa > 45 else "baja",
                "conclusion": datos.get("ejemplos", [{}])[0].get("lectura", "") if datos.get("ejemplos") else ""
            }
    
    # Añadir retroalimentación si existe
    for key, datos in retroalimentacion.get("factores", {}).items():
        if datos.get("casos", 0) > 0:
            if key in factores_validados:
                factores_validados[key]["tasa_confirmacion_real"] = datos.get("tasa_confirmacion", 0)
                factores_validados[key]["confirmados"] = datos.get("confirmo_patron", 0)
                factores_validados[key]["contradichos"] = datos.get("contradijo_patron", 0)
    
    memoria["factores_humanos_validados"] = factores_validados
    
    # Pesos aprendidos
    memoria["dinamicas_temporada"] = {
        "pesos_aprendidos": pesos.get("pesos", {}),
        "pesos_referencia": pesos.get("referencia", {}),
        # Auditoria 26/11: era un texto fijo; ahora sale de los pesos reales.
        "conclusion_pesos": " ".join(
            linea.lstrip("- ").strip()
            for linea in describir_pesos_aprendidos(pesos.get("pesos", {}), pesos.get("referencia", {}))
        ) or "Aún no hay suficiente variación en los pesos para destacar cambios."
    }

    # ══════════════════════════════════════════
    # 5. RESUMEN COMPACTO PARA EL CHAT
    # ══════════════════════════════════════════
    print("5. Generando resumen para chat...")
    
    est = memoria["estadisticas_globales"]
    apq = memoria["aprendizaje_quiniela"]
    ef = apq["estadisticas_fallos"]
    ultima_prediccion = cargar_json(DATA / "predicciones" / "ultima_prediccion.json", {})

    texto_pesos = "\n".join(
        describir_pesos_aprendidos(pesos.get("pesos", {}), pesos.get("referencia", {}))
    ) or "- Aún no hay suficiente variación en los pesos para destacar cambios."

    texto_patrones = "\n".join(lineas_patrones(patrones)) or "- Sin patrones medidos disponibles ahora mismo."
    texto_cobrado = ", ".join(
        f"{etiqueta_temporada(temp)}: {eur}€"
        for temp, eur in apq.get("cobrado_por_temporada_eur", {}).items()
    ) or "sin premios registrados"

    precision_tipo = ef["precision_por_tipo"]
    precision_fijo = f"{precision_tipo['FIJO']}%" if "FIJO" in precision_tipo else "sin datos suficientes"
    precision_doble = f"{precision_tipo['DOBLE']}%" if "DOBLE" in precision_tipo else "sin datos suficientes"
    precision_triple = f"{precision_tipo['TRIPLE']}%" if "TRIPLE" in precision_tipo else "sin datos suficientes"

    resumen = f"""SOY LA IA DE QUINIHUB. ESTO ES LO QUE SÉ Y HE APRENDIDO:

SOBRE EL FÚTBOL (basado en {est.get('total_partidos_analizados', 0)} partidos analizados):
- Gana el local el {est.get('frecuencia_1', 0)}% de las veces. Hay empate el {est.get('frecuencia_X', 0)}%. Gana el visitante el {est.get('frecuencia_2', 0)}%.
- De media, en una jornada de La Quiniela el local NO gana en el {memoria['patrones_jornada'].get('media_sorpresa_por_jornada', 0)}% de los partidos.

SOBRE LO QUE HE APRENDIDO DE LOS PESOS:
{texto_pesos}

PATRONES COMPETITIVOS MEDIDOS (cifras de patrones_competitivos.json):
{texto_patrones}

MIS FALLOS MÁS HABITUALES:
- Fijo fallado ({ef['fijos_fallados']} veces): confío demasiado en el favorito sin cobertura.
- No cubro empate ({ef['empates_no_cubiertos']} veces): el X me cuesta más de lo que debería.
- Precisión en FIJOS: {precision_fijo}. En DOBLES: {precision_doble}. En TRIPLES: {precision_triple}.

SOBRE NUESTRAS QUINIELAS:
- Llevamos {apq.get('jornadas_jugadas', 0)} jornadas jugadas con IA.
- Mejor resultado: J{apq.get('mejor_jornada', {}).get('jornada', '?')} de la {etiqueta_temporada(apq.get('mejor_jornada', {}).get('temporada'))} con {apq.get('mejor_jornada', {}).get('aciertos', '?')} aciertos.
- Total cobrado: {apq.get('total_cobrado_eur', 0)}€ ({texto_cobrado})
- Precisión media: {apq.get('precision_media', 0)}% (temporada {etiqueta_temporada(apq.get('temporada_actual'))}: {apq.get('precision_media_temporada_actual', 0)}% en {apq.get('jornadas_temporada_actual', 0)} jornadas)

EQUIPOS QUE MÁS GANAN FUERA DE CASA (victorias como visitante):"""

    for eq in memoria["equipos_destacados"].get("mas_sorprendentes", [])[:5]:
        resumen += f"\n- {eq['equipo']}: gana el {eq['pct_sorpresa']}% de sus {eq['partidos_visitante']} partidos fuera"

    resumen += "\n\nESTADO ACTUAL: " + describir_estado_actual(ultima_prediccion)

    memoria["resumen_para_chat"] = resumen
    memoria["temporadas_analizadas"] = temporadas_vistas
    
    # Guardar
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(memoria, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"\n✅ Memoria histórica profunda generada: {SALIDA}")
    print(f"   Partidos analizados: {total_partidos}")
    print(f"   Equipos: {len(equipos_con_datos)}")
    print(f"   Factores validados: {len(factores_validados)}")
    print(f"   Tamaño: {SALIDA.stat().st_size / 1024:.1f} KB")

if __name__ == "__main__":
    construir_memoria()
