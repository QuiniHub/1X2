import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia"
CLASIFICACIONES = ROOT / "clasificaciones.json"


REGLAS = {
    "primera": {
        "nombre": "LALIGA EA SPORTS",
        "partidos_temporada": 38,
        "campeon": 1,
        "champions": 5,
        "europa_league": 2,
        "conference": 1,
        "descenso": 3,
        "nota_europa": "Lectura provisional de liga: la Copa del Rey y campeones europeos pueden mover plazas Europa League/Conference.",
    },
    "segunda": {
        "nombre": "LALIGA HYPERMOTION",
        "partidos_temporada": 42,
        "ascenso_directo": 2,
        "playoff_ascenso": 4,
        "descenso": 4,
    },
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


def normalizar_nombre(nombre):
    texto = unicodedata.normalize("NFKD", str(nombre or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = re.sub(r"\b(cf|fc|rc|cd|ud|sd|club|real|de|del|la|el|balompie|futbol)\b", "", texto)
    return re.sub(r"[^a-z0-9]", "", texto)


def int_valor(valor, defecto=0):
    try:
        return int(valor)
    except Exception:
        return defecto


def preparar_tabla(tabla, total_partidos):
    equipos = []
    for item in sorted(tabla or [], key=lambda x: int_valor(x.get("posicion"), 999)):
        pj = int_valor(item.get("pj"))
        puntos = int_valor(item.get("puntos", item.get("pts")))
        restantes = max(total_partidos - pj, 0)
        equipos.append({
            "clave": normalizar_nombre(item.get("equipo")),
            "equipo": item.get("equipo"),
            "posicion": int_valor(item.get("posicion")),
            "pj": pj,
            "puntos": puntos,
            "puntos_en_juego": restantes * 3,
            "maximo_puntos": puntos + restantes * 3,
            "dg": int_valor(item.get("dg")),
            "racha_actual": item.get("racha_actual", {}),
            "tendencias": item.get("tendencias", {}),
        })
    return equipos


def frontera_superior(equipos, fin):
    dentro = equipos[fin - 1] if len(equipos) >= fin else None
    perseguidor = equipos[fin] if len(equipos) > fin else None
    return dentro, perseguidor


def evaluar_plaza(equipo, equipos, fin, objetivo):
    dentro, perseguidor = frontera_superior(equipos, fin)
    if not dentro:
        return None
    pos = equipo["posicion"]
    puntos = equipo["puntos"]
    maximo = equipo["maximo_puntos"]

    if pos <= fin:
        if not perseguidor:
            return {
                "objetivo": objetivo,
                "estado": "en_plaza",
                "distancia_o_colchon": None,
                "lectura": f"Esta dentro de {objetivo}; no hay perseguidor directo fuera del corte.",
            }
        colchon = puntos - perseguidor["puntos"]
        asegurado = puntos > perseguidor["maximo_puntos"]
        estado = "asegurado_matematicamente" if asegurado else "defiende_plaza"
        return {
            "objetivo": objetivo,
            "estado": estado,
            "distancia_o_colchon": colchon,
            "lectura": f"Esta dentro de {objetivo} con {colchon} puntos sobre el primer perseguidor ({perseguidor['equipo']}).",
        }

    distancia = max(dentro["puntos"] - puntos + 1, 0)
    vivo = maximo >= dentro["puntos"]
    return {
        "objetivo": objetivo,
        "estado": "aspira_matematicamente" if vivo else "sin_opciones_reales",
        "distancia_o_colchon": -distancia,
        "lectura": f"Esta a {distancia} puntos de entrar en {objetivo}; maximo posible {maximo}.",
    }


def evaluar_titulo(equipo, equipos):
    if not equipos:
        return None
    lider = equipos[0]
    segundo = equipos[1] if len(equipos) > 1 else None
    if equipo["posicion"] == 1:
        if not segundo:
            return None
        colchon = equipo["puntos"] - segundo["puntos"]
        estado = "campeon_matematico" if equipo["puntos"] > segundo["maximo_puntos"] else "defiende_liderato"
        lectura = (
            f"Lidera con {colchon} puntos sobre {segundo['equipo']}. "
            f"{'Ya no puede ser alcanzado por puntos.' if estado == 'campeon_matematico' else 'Aun debe cerrar matematicamente el titulo.'}"
        )
        return {
            "objetivo": "titulo_liga",
            "estado": estado,
            "distancia_o_colchon": colchon,
            "lectura": lectura,
        }

    distancia = lider["puntos"] - equipo["puntos"] + 1
    vivo = equipo["maximo_puntos"] >= lider["puntos"]
    return {
        "objetivo": "titulo_liga",
        "estado": "aspira_matematicamente" if vivo else "sin_opciones_reales",
        "distancia_o_colchon": -distancia,
        "lectura": f"Esta a {distancia} puntos del lider ({lider['equipo']}); maximo posible {equipo['maximo_puntos']}.",
    }


def evaluar_descenso(equipo, equipos, plazas, nombre_objetivo):
    total = len(equipos)
    ultima_safe = total - plazas
    primera_descenso = ultima_safe + 1
    pos = equipo["posicion"]
    if total <= plazas:
        return None

    equipo_safe = equipos[ultima_safe - 1]
    equipo_descenso = equipos[ultima_safe]

    if pos >= primera_descenso:
        distancia = max(equipo_safe["puntos"] - equipo["puntos"] + 1, 0)
        estado = "en_descenso_con_opciones" if equipo["maximo_puntos"] >= equipo_safe["puntos"] else "descenso_muy_complicado"
        return {
            "objetivo": nombre_objetivo,
            "estado": estado,
            "distancia_o_colchon": -distancia,
            "lectura": f"Esta en zona de descenso y necesita {distancia} puntos para superar el corte de {equipo_safe['equipo']}.",
        }

    colchon = equipo["puntos"] - equipo_descenso["puntos"]
    asegurado = equipo["puntos"] > equipo_descenso["maximo_puntos"]
    if asegurado:
        estado = "salvado_matematicamente"
    elif colchon <= 3:
        estado = "riesgo_descenso"
    elif colchon <= equipo_descenso["puntos_en_juego"]:
        estado = "permanencia_por_cerrar"
    else:
        estado = "ventaja_por_permanencia"
    return {
        "objetivo": nombre_objetivo,
        "estado": estado,
        "distancia_o_colchon": colchon,
        "lectura": f"Tiene {colchon} puntos sobre el primer equipo en descenso ({equipo_descenso['equipo']}).",
    }


def nivel_motivacion(objetivos):
    score = 0
    estados_altos = {
        "defiende_liderato",
        "defiende_plaza",
        "aspira_matematicamente",
        "en_descenso_con_opciones",
        "riesgo_descenso",
    }
    estados_medios = {"permanencia_por_cerrar", "ventaja_por_permanencia", "descenso_muy_complicado"}
    for objetivo in objetivos:
        estado = objetivo.get("estado")
        if estado in estados_altos:
            score += 2
        elif estado in estados_medios:
            score += 1
    if score >= 5:
        return "maxima"
    if score >= 3:
        return "alta"
    if score >= 1:
        return "media"
    return "baja"


def limpiar_objetivos(equipo, objetivos):
    visibles = []
    for objetivo in objetivos:
        if not objetivo:
            continue
        estado = objetivo.get("estado")
        if estado in ("sin_opciones_reales", "salvado_matematicamente"):
            continue
        visibles.append(objetivo)
    equipo["objetivos"] = visibles
    equipo["motivacion_competitiva"] = nivel_motivacion(visibles)
    return equipo


def resumen_frontera(equipos, fin, etiqueta):
    dentro, fuera = frontera_superior(equipos, fin)
    if not dentro or not fuera:
        return None
    diferencia = dentro["puntos"] - fuera["puntos"]
    return f"{etiqueta}: {dentro['equipo']} marca el corte con {dentro['puntos']} puntos; {fuera['equipo']} persigue a {diferencia}."


def resumen_titulo(equipos):
    if len(equipos) < 2:
        return None
    lider, segundo = equipos[0], equipos[1]
    if lider["puntos"] > segundo["maximo_puntos"]:
        return f"Titulo: {lider['equipo']} ya es campeon matematico con {lider['puntos']} puntos; {segundo['equipo']} solo puede llegar a {segundo['maximo_puntos']}."
    diferencia = lider["puntos"] - segundo["puntos"]
    return f"Titulo: {lider['equipo']} lidera con {lider['puntos']} puntos; {segundo['equipo']} esta a {diferencia}."


def resumen_descenso(equipos, plazas, etiqueta):
    total = len(equipos)
    if total <= plazas:
        return None
    safe = equipos[total - plazas - 1]
    drop = equipos[total - plazas]
    diferencia = safe["puntos"] - drop["puntos"]
    return f"{etiqueta}: {safe['equipo']} esta justo fuera con {safe['puntos']}; {drop['equipo']} esta dentro a {diferencia}."


def analizar_primera(tabla):
    reglas = REGLAS["primera"]
    equipos = preparar_tabla(tabla, reglas["partidos_temporada"])
    fin_champions = reglas["champions"]
    fin_europa = fin_champions + reglas["europa_league"]
    fin_conference = fin_europa + reglas["conference"]

    analizados = []
    for equipo in equipos:
        objetivos = [
            evaluar_titulo(equipo, equipos),
            evaluar_plaza(equipo, equipos, fin_champions, "champions"),
            evaluar_plaza(equipo, equipos, fin_europa, "europa_league"),
            evaluar_plaza(equipo, equipos, fin_conference, "conference"),
            evaluar_descenso(equipo, equipos, reglas["descenso"], "descenso"),
        ]
        analizados.append(limpiar_objetivos(equipo, objetivos))

    lecturas = [
        resumen_titulo(equipos),
        resumen_frontera(equipos, fin_champions, "Champions"),
        resumen_frontera(equipos, fin_europa, "Europa League"),
        resumen_frontera(equipos, fin_conference, "Conference"),
        resumen_descenso(equipos, reglas["descenso"], "Descenso a Segunda"),
    ]
    return {
        "reglas": reglas,
        "equipos": analizados,
        "resumen": {
            "equipos": len(equipos),
            "partidos_temporada": reglas["partidos_temporada"],
            "puntos_maximos_restantes": max((e["puntos_en_juego"] for e in equipos), default=0),
        },
        "lecturas_clave": [x for x in lecturas if x],
    }


def analizar_segunda(tabla):
    reglas = REGLAS["segunda"]
    equipos = preparar_tabla(tabla, reglas["partidos_temporada"])
    fin_directo = reglas["ascenso_directo"]
    fin_playoff = fin_directo + reglas["playoff_ascenso"]

    analizados = []
    for equipo in equipos:
        objetivos = [
            evaluar_plaza(equipo, equipos, fin_directo, "ascenso_directo"),
            evaluar_plaza(equipo, equipos, fin_playoff, "playoff_ascenso"),
            evaluar_descenso(equipo, equipos, reglas["descenso"], "descenso_primera_federacion"),
        ]
        analizados.append(limpiar_objetivos(equipo, objetivos))

    lecturas = [
        resumen_frontera(equipos, fin_directo, "Ascenso directo"),
        resumen_frontera(equipos, fin_playoff, "Promocion de ascenso"),
        resumen_descenso(equipos, reglas["descenso"], "Descenso a Primera Federacion"),
    ]
    return {
        "reglas": reglas,
        "equipos": analizados,
        "resumen": {
            "equipos": len(equipos),
            "partidos_temporada": reglas["partidos_temporada"],
            "puntos_maximos_restantes": max((e["puntos_en_juego"] for e in equipos), default=0),
        },
        "lecturas_clave": [x for x in lecturas if x],
    }


def main():
    clasificaciones = cargar_json(CLASIFICACIONES, {})
    salida = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": "Contexto de objetivos y presion competitiva para calibrar predicciones de final de temporada.",
        "reglas": REGLAS,
        "primera": analizar_primera(clasificaciones.get("primera", [])),
        "segunda": analizar_segunda(clasificaciones.get("segunda", [])),
    }
    guardar_json(MEMORIA / "contexto_competitivo.json", salida)
    print(MEMORIA / "contexto_competitivo.json")


if __name__ == "__main__":
    main()
