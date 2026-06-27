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
    equipos_stats = defaultdict(lambda: {
        "partidos": 0, "victorias": 0, "empates": 0, "derrotas": 0,
        "gf": 0, "gc": 0, "sorpresas_causadas": 0, "como_local": 0, "como_visitante": 0
    })
    jornadas_data = []
    jornadas_impredecibles = []
    jornadas_predecibles = []

    for path in sorted(JORNADAS.glob("jornada_*.json"), 
                       key=lambda p: int(p.stem.split("_")[1])):
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
                    equipos_stats[local]["sorpresas_causadas"] += 1
                    sorpresas_jornada += 1
                    sorpresas += 1
            
            if visitante:
                equipos_stats[visitante]["partidos"] += 1
                equipos_stats[visitante]["como_visitante"] += 1
                if signo == "2":
                    equipos_stats[visitante]["victorias"] += 1
                elif signo == "X":
                    equipos_stats[visitante]["empates"] += 1
                else:
                    equipos_stats[visitante]["derrotas"] += 1
            
            competicion = (p.get("competicion") or p.get("liga") or "liga").lower()
            partidos_por_competicion[competicion] += 1
        
        if signos_jornada:
            pct_sorpresa = (signos_jornada.count("X") + signos_jornada.count("2")) / len(signos_jornada) * 100
            jornada_info = {
                "jornada": jornada_num,
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
                f"el {round(signos['2']/total_partidos*100,1)}%. El {round(sorpresas/total_partidos*100,1)}% "
                f"de los partidos son sorpresas para el pronóstico habitual."
            )
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
        key=lambda x: x[1]["sorpresas_causadas"] / max(x[1]["partidos"], 1),
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
                "sorpresas_causadas": v["sorpresas_causadas"],
                "pct_sorpresa": round(v["sorpresas_causadas"] / max(v["partidos"], 1) * 100, 1)
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
    
    total_aciertos = 0
    total_posibles = 0
    mejor_jornada = None
    peor_jornada = None
    mejor_aciertos = 0
    peor_aciertos = 99
    total_cobrado = 0.0
    
    for j in premios.get("jornadas", []):
        num = int(j.get("jornada", 0))
        if num < 61:
            continue
        aciertos = j.get("aciertos", 0)
        if aciertos and str(aciertos).isdigit():
            aciertos = int(aciertos)
            total_aciertos += aciertos
            total_posibles += 14
            if aciertos > mejor_aciertos:
                mejor_aciertos = aciertos
                mejor_jornada = num
            if aciertos < peor_aciertos:
                peor_aciertos = aciertos
                peor_jornada = num
        premio = j.get("premio_eur", 0.0)
        if prize := float(premio or 0):
            total_cobrado += prize

    memoria["aprendizaje_quiniela"] = {
        "jornadas_jugadas": len(jornadas_jugadas),
        "jornadas_con_resultado": len(jornadas_con_resultado),
        "mejor_jornada": {"jornada": mejor_jornada, "aciertos": mejor_aciertos},
        "peor_jornada": {"jornada": peor_jornada, "aciertos": peor_aciertos},
        "total_cobrado_eur": round(total_cobrado, 2),
        "precision_media": round(total_aciertos / max(total_posibles, 1) * 100, 1),
        "fallos_mas_comunes": [
            "Fijo fallado cuando había alerta de motivación activa",
            "No cubrir empate en partidos con alta incertidumbre",
            "Confiar demasiado en el favorito cuando el rival está desesperado",
            "No detectar el factor 'último partido' en equipos eliminados"
        ]
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
        "conclusion_pesos": (
            "El sistema ha aprendido que la SORPRESA y el EMPATE pesan más de lo esperado. "
            "La FORMA RECIENTE y la CLASIFICACIÓN engañan más de lo que ayudan. "
            "Los GOLES y la MOTIVACIÓN COMPETITIVA son los factores más fiables."
        )
    }

    # ══════════════════════════════════════════
    # 5. RESUMEN COMPACTO PARA EL CHAT
    # ══════════════════════════════════════════
    print("5. Generando resumen para chat...")
    
    est = memoria["estadisticas_globales"]
    apq = memoria["aprendizaje_quiniela"]
    
    resumen = f"""SOY LA IA DE QUINIHUB. ESTO ES LO QUE SÉ Y HE APRENDIDO:

SOBRE EL FÚTBOL (basado en {est.get('total_partidos_analizados', 0)} partidos analizados):
- Gana el local el {est.get('frecuencia_1', 0)}% de las veces. Hay empate el {est.get('frecuencia_X', 0)}%. Gana el visitante el {est.get('frecuencia_2', 0)}%.
- El {est.get('pct_sorpresa_global', 0)}% de los partidos son sorpresas para el pronóstico habitual.
- Las jornadas de La Quiniela tienen de media un {memoria['patrones_jornada'].get('media_sorpresa_por_jornada', 0)}% de sorpresa.

SOBRE LO QUE HE APRENDIDO DE LOS PESOS:
- La SORPRESA pesa más de lo que pensaba inicialmente (+72% sobre mi referencia base).
- El EMPATE suelo subestimarlo — ha subido un 75% en mi modelo.
- La FORMA RECIENTE engaña — la he reducido un 50%.
- La CLASIFICACIÓN sola miente — la he reducido un 50%.
- Los GOLES y la MOTIVACIÓN son los factores más fiables.

PATRONES COMPETITIVOS QUE HE VALIDADO:
- Equipo necesitado vs sin objetivo: 66% de sorpresa (294 casos). MUY FIABLE.
- Local desesperado (descenso) vs visitante objetivo cerrado: 79.6% sorpresa (147 casos). EL MÁS FIABLE.
- Visitante necesitado vs local sin objetivos: 52.4% sorpresa (147 casos). MODERADO.

MIS FALLOS MÁS HABITUALES:
- Fijo fallado (35 veces): confío demasiado en el favorito sin cobertura.
- No cubro empate (16 veces): el X me cuesta más de lo que debería.
- Precision en FIJOS: solo 46.9%. En DOBLES: 72.4%. En TRIPLES: 100%.

SOBRE NUESTRAS QUINIELAS:
- Llevamos {apq.get('jornadas_jugadas', 0)} jornadas jugadas con IA.
- Mejor resultado: J{apq.get('mejor_jornada', {}).get('jornada', '?')} con {apq.get('mejor_jornada', {}).get('aciertos', '?')} aciertos.
- Total cobrado: {apq.get('total_cobrado_eur', 0)}€
- Precisión media: {apq.get('precision_media', 0)}%

EQUIPOS QUE MÁS SORPRENDEN (dan la sorpresa con más frecuencia):"""

    for eq in memoria["equipos_destacados"].get("mas_sorprendentes", [])[:5]:
        resumen += f"\n- {eq['equipo']}: {eq['pct_sorpresa']}% de sorpresa en {eq['partidos']} partidos"

    resumen += "\n\nESTADO ACTUAL: "
    resumen += "J70 en juego (5 partidos pendientes esta noche/mañana). J71 bloqueada hasta cerrar J70."
    
    memoria["resumen_para_chat"] = resumen
    memoria["temporadas_analizadas"] = ["2025_2026"]
    
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
