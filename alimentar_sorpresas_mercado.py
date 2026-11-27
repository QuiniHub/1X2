"""
Alimenta data/memoria_ia/sorpresas_mercado.json con casos reales de sorpresa:
partidos donde el motor apostó FIJO con alta confianza y el resultado fue diferente,
cruzando el diario de aprendizaje con los snapshots de predicción disponibles.

La función reforzar_ajuste_por_memoria_sorpresas() del motor usa este archivo para
amplificar un 20% los ajustes motivacionales cuando hay >=3 casos similares.
"""

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import cronologia_jornadas

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
DIARIO = DATA / "memoria_ia" / "diario_aprendizaje.json"
PREDICCIONES = DATA / "predicciones"
JORNADAS = DATA / "jornadas"
SNAPSHOTS = DATA / "backtesting" / "pre_cierre"
SORPRESAS_MERCADO = DATA / "memoria_ia" / "sorpresas_mercado.json"

# Categorías que entiende reforzar_ajuste_por_memoria_sorpresas()
CAT_DERBI = "derbi"
CAT_SIN_PRESION = "partido_sin_presion"
CAT_MOTIVACIONAL = "motivacion_competitiva"
CAT_DESCONOCIDO = "desconocido"

# Pares de rivales históricos (misma lógica que DERBIS_HISTORICOS en el motor)
DERBIS = {
    frozenset(["real madrid", "barcelona"]), frozenset(["atletico", "real madrid"]),
    frozenset(["sevilla", "betis"]), frozenset(["valencia", "levante"]),
    frozenset(["athletic", "real sociedad"]), frozenset(["deportivo", "celta"]),
    frozenset(["atletico", "athletic"]), frozenset(["espanyol", "barcelona"]),
    frozenset(["valladolid", "salamanca"]), frozenset(["malaga", "granada"]),
    frozenset(["oviedo", "sporting"]), frozenset(["villarreal", "valencia"]),
}


def cargar_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def guardar_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def es_derbi(local: str, visitante: str) -> bool:
    l = local.lower()
    v = visitante.lower()
    for par in DERBIS:
        nombres = list(par)
        if any(nombres[0] in l or nombres[0] in v for _ in [1]) and \
           any(nombres[1] in l or nombres[1] in v for _ in [1]):
            return True
    return False


def extraer_equipos_de_nombre(nombre_partido: str):
    """'11. Málaga - Castellón' → ('Málaga', 'Castellón')"""
    m = re.match(r"^\d+\.\s*(.+?)\s*[-–]\s*(.+)$", nombre_partido.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", ""


def inferir_categoria_y_alertas(razonamiento: str, riesgo_necesidad: bool,
                                 local: str = "", visitante: str = ""):
    """Infiere la categoría de sorpresa y alertas motivacionales."""
    r = (razonamiento or "").lower()

    # Primero detectar derbis por nombre de equipos
    if es_derbi(local, visitante) or "derbi" in r or "rivalidad hist" in r:
        return CAT_DERBI, ["derbi_todo_puede_pasar"]

    if (
        "sin objetivos" in r
        or "ambos clasificados sin tension" in r
        or "ambos clasificados" in r
        or "ya salvado" in r
        or "sin presion" in r
    ):
        return CAT_SIN_PRESION, ["equipo_sin_objetivos"]

    if (
        riesgo_necesidad
        or "necesita" in r
        or "descenso" in r
        or "salvacion" in r
        or "playoff ascenso" in r
        or "ascenso directo" in r
        or "objetivo cerrado" in r
        or "competicion mas urgencia" in r
        or "mas necesitado" in r
    ):
        return CAT_MOTIVACIONAL, ["equipo_necesitado_vs_objetivo_cerrado"]

    return CAT_DESCONOCIDO, []


def numero_partido_desde_nombre(nombre_partido: str):
    m = re.match(r"^(\d+)\.", nombre_partido.strip())
    return int(m.group(1)) if m else None


def prob_top_desde_partidos(partido_snap: dict) -> float:
    """Calcula probabilidad_top desde el dict de probabilidades si el campo explícito es None."""
    pt = partido_snap.get("probabilidad_top")
    if pt is not None:
        return float(pt)
    probs = partido_snap.get("probabilidades") or {}
    if probs:
        return max(float(v) for v in probs.values())
    return 0.0


def numero_partido_entrada(entrada):
    """Numero de partido con cualquiera de las dos claves del fichero."""
    for clave in ("num_partido", "numero_partido"):
        valor = (entrada or {}).get(clave)
        try:
            numero = int(str(valor).strip())
        except (TypeError, ValueError):
            continue
        if numero > 0:
            return numero
    return 0


def numero_jornada_entrada(entrada):
    try:
        return int(str((entrada or {}).get("jornada")).strip())
    except (TypeError, ValueError):
        return 0


def temporada_de_jornada(numero):
    """Temporada del fichero data/jornadas/jornada_N.json (por su fecha real)."""
    datos = cronologia_jornadas.cargar_jornada(numero, JORNADAS) if numero else None
    fecha = cronologia_jornadas.fecha_real_jornada(datos) if datos else None
    return cronologia_jornadas.temporada_de_fecha(fecha, numero) if fecha else None


def temporada_entrada(entrada):
    """Temporada de una entrada: la guardada, la de su fecha o la del fichero
    de jornada. Una vez calculada se guarda en la entrada, asi que no cambia
    cuando jornada_N.json pase a ser de la temporada siguiente."""
    guardada = (entrada or {}).get("temporada")
    if guardada:
        return str(guardada)
    numero = numero_jornada_entrada(entrada)
    for campo in ("fecha", "registrada_en"):
        fecha = cronologia_jornadas.parsear_fecha(entrada.get(campo))
        if fecha is not None:
            return cronologia_jornadas.temporada_de_fecha(fecha, numero or None)
    return temporada_de_jornada(numero)


ORIGEN_DIARIO = "diario_aprendizaje_fallo_fijo"
ORIGEN_MERCADO = "mercado_favorito_no_gano"


def origen_entrada(entrada):
    """Origen de la entrada; las antiguas sin el campo se deducen."""
    origen = str((entrada or {}).get("origen") or "").strip()
    if origen:
        return origen
    if "probabilidad_mercado_favorito" in (entrada or {}):
        return ORIGEN_MERCADO
    return ORIGEN_DIARIO


def clave_entrada(entrada):
    """Identidad: (temporada, jornada, partido, origen). El origen entra
    porque un partido puede ser a la vez sorpresa de mercado y fijo fallado:
    la entrada de un escritor no debe impedir la del otro."""
    return (
        temporada_entrada(entrada),
        numero_jornada_entrada(entrada),
        numero_partido_entrada(entrada),
        origen_entrada(entrada),
    )


def texto_plano(valor):
    texto = unicodedata.normalize("NFKD", str(valor or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.lower().split())


def clave_sin_temporada(entrada):
    """Identidad de un fallo de fijo SIN temporada: jornada, partido, nombre
    del partido y signo real. diario_aprendizaje.json no trae temporada ni
    fecha, asi que la temporada de una entrada nueva se deduce del fichero
    jornada_N.json de HOY; cuando la temporada siguiente pise ese numero, el
    fallo antiguo saldria con la temporada equivocada y se reanadiria. Con
    esta clave se reconoce que ya estaba guardado (los equipos lo delatan)."""
    return (
        numero_jornada_entrada(entrada),
        numero_partido_entrada(entrada),
        texto_plano(entrada.get("partido")),
        str(entrada.get("signo_real") or "").strip().upper(),
    )


def normalizar_entrada(entrada):
    """Esquema unico: las dos claves de numero de partido, la temporada, el
    origen y el nombre del partido (lo pinta el chat de la web)."""
    numero = numero_partido_entrada(entrada)
    entrada["num_partido"] = numero
    entrada["numero_partido"] = numero
    if not entrada.get("origen"):
        entrada["origen"] = origen_entrada(entrada)
    if not entrada.get("partido") and (entrada.get("local") or entrada.get("visitante")):
        entrada["partido"] = f"{numero}. {entrada.get('local') or ''} - {entrada.get('visitante') or ''}"
    for campo in ("pronostico_jugado", "resultado"):
        if entrada.get(campo) is None:
            entrada[campo] = ""
    if not entrada.get("temporada"):
        temporada = temporada_entrada(entrada)
        if temporada:
            entrada["temporada"] = temporada
    return entrada


def prediccion_para_enriquecer(jornada):
    """Prediccion de ESA jornada real: el snapshot pre-cierre si existe y, si
    no, data/predicciones solo cuando son los mismos partidos (auditoria
    26/11: se cruzaba por numero sin comprobar temporada ni equipos)."""
    pred = cronologia_jornadas.prediccion_del_cierre(jornada, SNAPSHOTS, JORNADAS)
    if isinstance(pred, dict) and pred.get("partidos"):
        return pred
    pred = cargar_json(PREDICCIONES / f"jornada_{jornada}.json")
    datos = cronologia_jornadas.cargar_jornada(jornada, JORNADAS)
    if pred and datos and cronologia_jornadas.misma_jornada(pred, datos):
        return pred
    return {}


def procesar_diario():
    diario = cargar_json(DIARIO, {})
    entradas = diario.get("entradas", [])

    sorpresas = []
    vistas = set()

    for entrada in entradas:
        # Solo fallos de fijo
        if entrada.get("categoria_fallo") != "fallo_fijo":
            continue
        if entrada.get("tipo_apuesta") != "FIJO":
            continue
        if entrada.get("acierto", True):
            continue

        jornada = entrada.get("jornada")
        nombre_partido = entrada.get("partido", "")
        num = numero_partido_desde_nombre(nombre_partido)

        if not jornada or not num:
            continue

        clave = (jornada, num, texto_plano(nombre_partido))
        if clave in vistas:
            continue
        vistas.add(clave)

        local, visitante = extraer_equipos_de_nombre(nombre_partido)

        # Intentar enriquecer con el snapshot pre-cierre de la jornada
        snapshot = prediccion_para_enriquecer(numero_jornada_entrada(entrada))
        partido_snap = None
        if snapshot:
            for p in snapshot.get("partidos", []):
                if p.get("num") == num:
                    partido_snap = p
                    break

        razonamiento = (partido_snap or {}).get("razonamiento", "")
        riesgo_necesidad = bool((partido_snap or {}).get("riesgo_necesidad_real", False))
        probabilidad_top = prob_top_desde_partidos(partido_snap) if partido_snap else 0.0

        categoria, alertas = inferir_categoria_y_alertas(
            razonamiento, riesgo_necesidad, local, visitante
        )

        # Incluir siempre los fallos de fijo: el motor necesita casos reales.
        # Los "desconocido" sin alertas no coincidirán con el filtro del motor
        # pero los motivacionales sí. No filtramos por probabilidad mínima.
        sorpresas.append({
            "jornada": jornada,
            "temporada": entrada.get("temporada") or temporada_de_jornada(numero_jornada_entrada(entrada)),
            "partido": nombre_partido,
            "num_partido": num,
            "numero_partido": num,
            "local": local,
            "visitante": visitante,
            "pronostico_jugado": entrada.get("pronostico_jugado", ""),
            "signo_real": entrada.get("signo_real", ""),
            "resultado": entrada.get("resultado", ""),
            "categoria_sorpresa": categoria,
            "alerta_motivacion_detectada": alertas[0] if alertas else "",
            "alertas_motivacion_detectadas": alertas,
            "probabilidad_top": round(probabilidad_top, 1),
            "riesgo_necesidad_real": riesgo_necesidad,
            "tiene_snapshot": partido_snap is not None,
            "origen": "diario_aprendizaje_fallo_fijo",
            "registrada_en": datetime.now(timezone.utc).isoformat(),
        })

    return sorpresas


def es_entrada_esquema_actual(entrada):
    """True si la entrada identifica un partido (jornada + numero de partido).

    Auditoria 26/11: antes se descartaba todo lo que no tuviera la clave
    'num_partido', atribuyendolo a un "mecanismo del Mundial". No era eso:
    'numero_partido' es la clave con la que escribia el OTRO escritor activo
    de este fichero (actualizar_aprendizaje_ia.registrar_sorpresas_mercado,
    que corre antes en el mismo ciclo). Resultado: 46 sorpresas de mercado de
    la 26/27 se escribian y se borraban en cada ciclo. Ahora se aceptan las
    dos claves y normalizar_entrada() deja el esquema unico."""
    return bool(numero_jornada_entrada(entrada)) and bool(numero_partido_entrada(entrada))


def main():
    print("=== Alimentando sorpresas_mercado.json ===")

    sorpresas_nuevas = procesar_diario()

    actual = cargar_json(SORPRESAS_MERCADO, {"version": "1.0", "sorpresas": []})
    existentes_todas = actual.get("sorpresas", [])
    existentes = [normalizar_entrada(e) for e in existentes_todas if es_entrada_esquema_actual(e)]
    descartadas = len(existentes_todas) - len(existentes)

    # Identidad: (temporada, jornada, partido). Solo por numero, una sorpresa
    # de la J5 de una temporada taparia para siempre la J5 de la siguiente.
    claves_existentes = {clave_entrada(e) for e in existentes}
    # Fallos de fijo ya guardados, reconocibles aunque la temporada deducida
    # hoy del fichero de jornada no coincida con la que se guardo en su dia.
    diario_guardadas = {
        clave_sin_temporada(e) for e in existentes if origen_entrada(e) == ORIGEN_DIARIO
    }

    nuevas_añadidas = []
    for s in sorpresas_nuevas:
        if clave_sin_temporada(s) in diario_guardadas:
            continue
        clave = clave_entrada(s)
        if clave not in claves_existentes:
            diario_guardadas.add(clave_sin_temporada(s))
            existentes.append(s)
            nuevas_añadidas.append(s)
            claves_existentes.add(clave)

    resultado = {
        "version": "1.2",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "total_sorpresas": len(existentes),
        "descripcion": (
            "Sorpresas reales, con dos origenes: 'diario_aprendizaje_fallo_fijo' (el motor "
            "predijo FIJO y fallo) y 'mercado_favorito_no_gano' (el favorito claro del "
            "mercado no gano; lo escribe actualizar_aprendizaje_ia). "
            "Usados por reforzar_ajuste_por_memoria_sorpresas() para amplificar "
            "ajustes motivacionales un 20% cuando hay >=3 casos similares."
        ),
        "sorpresas": existentes,
    }

    guardar_json(SORPRESAS_MERCADO, resultado)

    print(f"  Casos nuevos añadidos: {len(nuevas_añadidas)}")
    if descartadas:
        print(f"  Entradas sin jornada o sin numero de partido descartadas: {descartadas}")
    print(f"  Total sorpresas en memoria: {len(existentes)}")
    by_cat = {}
    for s in existentes:
        c = s.get("categoria_sorpresa", "?")
        by_cat[c] = by_cat.get(c, 0) + 1
    for cat, n in sorted(by_cat.items()):
        print(f"    {cat}: {n}")

    if not nuevas_añadidas and not descartadas:
        print("  Sin cambios: el archivo ya estaba actualizado.")


if __name__ == "__main__":
    main()
