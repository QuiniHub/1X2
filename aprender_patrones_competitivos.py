import re
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import generar_contexto_competitivo as contexto_mod

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = DATA / "memoria_ia" / "patrones_competitivos.json"
MEMORIA = DATA / "memoria_ia" / "aprendizaje_global.json"
CONTEXTO = DATA / "memoria_ia" / "contexto_competitivo.json"

ANALIZADORES = {
    "primera": contexto_mod.analizar_primera,
    "segunda": contexto_mod.analizar_segunda,
}

# Antes de la primera jornada de una temporada archivada no hay tabla previa
# alguna -saltarla evita analizar un contexto vacio sin sentido.
MIN_EQUIPOS_PARA_ANALIZAR = 1


def calendarios_historicos_por_liga():
    historico = DATA / "historico"
    return {
        "primera": sorted(historico.glob("calendario_primera_*.json")),
        "segunda": sorted(historico.glob("calendario_segunda_*.json")),
    }


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def signo_resultado(resultado):
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(resultado or ""))
    if not m:
        return None
    gl, gv = int(m.group(1)), int(m.group(2))
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


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


def ejemplo(liga, temporada, jornada_num, partido, signo, lectura):
    return {
        "liga": liga,
        "temporada": temporada,
        "jornada_liga": jornada_num,
        "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
        "resultado": partido.get("resultado"),
        "signo_real": signo,
        "lectura": lectura,
    }


def analizar_calendario_historico(liga, calendario, patrones):
    """Reconstruye la tabla jornada a jornada y usa la situacion competitiva
    real de CADA MOMENTO (no la de hoy) para saber si un resultado fue una
    sorpresa respecto a lo que la motivacion de cada equipo hacia esperar."""
    analizador = ANALIZADORES[liga]
    temporada = calendario.get("temporada", "?")
    jornadas = sorted(calendario.get("jornadas", []), key=lambda j: int(j.get("jornada", 0) or 0))
    tabla = tabla_vacia()

    for jornada in jornadas:
        partidos_jugados = [p for p in jornada.get("partidos", []) if signo_resultado(p.get("resultado"))]
        if not partidos_jugados:
            continue

        tabla_previa = tabla_a_lista_ordenada(tabla)
        mapa = {}
        if len(tabla_previa) >= MIN_EQUIPOS_PARA_ANALIZAR:
            analisis = analizador(tabla_previa)
            mapa = {e.get("clave", contexto_mod.normalizar_nombre(e.get("equipo"))): e for e in analisis.get("equipos", [])}

        for partido in partidos_jugados:
            signo = signo_resultado(partido.get("resultado"))
            local = mapa.get(contexto_mod.normalizar_nombre(partido.get("local", "")))
            visitante = mapa.get(contexto_mod.normalizar_nombre(partido.get("visitante", "")))

            if local and visitante:
                local_cerrado = objetivo_cerrado(local)
                visitante_cerrado = objetivo_cerrado(visitante)
                local_necesita = necesidad_viva(local)
                visitante_necesita = necesidad_viva(visitante)
                local_descenso = descenso_vivo(local)
                visitante_descenso = descenso_vivo(visitante)
                local_favorito = puntos_de(local) >= puntos_de(visitante) + 5
                visitante_favorito = puntos_de(visitante) >= puntos_de(local) + 5
                jornada_num = jornada.get("jornada")

                if visitante_cerrado and local_necesita:
                    registrar(
                        patrones, "necesitado_local_vs_visitante_objetivo_cerrado", signo != "2",
                        ejemplo(liga, temporada, jornada_num, partido, signo,
                                "El local con objetivo vivo puntua o gana ante visitante con objetivo cerrado."),
                    )
                if local_cerrado and visitante_necesita:
                    registrar(
                        patrones, "visitante_necesitado_vs_local_objetivo_cerrado", signo != "1",
                        ejemplo(liga, temporada, jornada_num, partido, signo,
                                "El visitante con objetivo vivo puntua o gana ante local con objetivo cerrado."),
                    )
                if visitante_descenso and local_favorito:
                    registrar(
                        patrones, "visitante_descenso_vs_local_favorito", signo != "1",
                        ejemplo(liga, temporada, jornada_num, partido, signo,
                                "Visitante con urgencia de descenso/permanencia rompe o amenaza el 1 fijo."),
                    )
                if local_descenso and visitante_favorito:
                    registrar(
                        patrones, "local_descenso_vs_visitante_favorito", signo != "2",
                        ejemplo(liga, temporada, jornada_num, partido, signo,
                                "Local con urgencia de descenso/permanencia rompe o amenaza el 2 fijo."),
                    )
                if (local_necesita and visitante_cerrado) or (visitante_necesita and local_cerrado):
                    sorpresa = (local_necesita and signo != "2") or (visitante_necesita and signo != "1")
                    registrar(
                        patrones, "equipo_necesitado_vs_equipo_sin_objetivo", sorpresa,
                        ejemplo(liga, temporada, jornada_num, partido, signo,
                                "Choque necesidad contra objetivo cerrado: no tratar al equipo sin objetivo como fijo limpio."),
                    )

            gl, gv = (int(x) for x in re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", partido["resultado"]).groups())
            aplicar_partido(tabla, partido.get("local", ""), partido.get("visitante", ""), gl, gv)


def analizar():
    patrones = defaultdict(base_patron)
    temporadas_analizadas = {}

    for liga, archivos in calendarios_historicos_por_liga().items():
        temporadas_analizadas[liga] = []
        for archivo in archivos:
            calendario = cargar_json(archivo, {})
            if not calendario.get("jornadas"):
                continue
            analizar_calendario_historico(liga, calendario, patrones)
            temporadas_analizadas[liga].append(calendario.get("temporada", archivo.stem))

    salida_patrones = {}
    for clave, patron in sorted(patrones.items()):
        casos = patron["casos"] or 1
        patron["tasa_sorpresa"] = round(patron["sorpresas"] / casos * 100, 1)
        salida_patrones[clave] = dict(patron)

    salida = {
        "version": "2.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": (
            "Patrones aprendidos de temporadas completas archivadas en data/historico/, "
            "reconstruyendo la situacion competitiva real de cada equipo jornada a jornada "
            "-no comparando contra la clasificacion de HOY, que en pretemporada no tiene "
            "nada que ver con la situacion en la que se jugo cada partido historico."
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
    print(f"Patrones competitivos aprendidos: {OUT}")
    for clave, patron in salida_patrones.items():
        print(f"  {clave}: {patron['casos']} casos, {patron['tasa_sorpresa']}% sorpresa")


if __name__ == "__main__":
    analizar()
