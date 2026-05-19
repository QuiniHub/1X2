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

ESTADOS_VIVOS = {
    "defiende_liderato",
    "defiende_plaza",
    "aspira_matematicamente",
    "aspira_por_desempate_o_fallo_ajeno",
    "en_descenso_con_opciones",
    "riesgo_descenso",
    "permanencia_por_cerrar",
}

PRIORIDAD_OBJETIVO = {
    "en_descenso_con_opciones": 120,
    "riesgo_descenso": 115,
    "permanencia_por_cerrar": 105,
    "defiende_liderato": 100,
    "defiende_plaza": 90,
    "aspira_matematicamente": 82,
    "aspira_por_desempate_o_fallo_ajeno": 78,
    "ventaja_por_permanencia": 45,
    "campeon_matematico": 38,
    "asegurado_matematicamente": 34,
    "salvado_matematicamente": 28,
    "descendido_matematicamente": 26,
    "sin_opciones_matematicas": 18,
    "no_se_juega_nada_clasificatorio": 5,
}


OBJETIVOS_AMPLIOS = {
    "europa_league": "Europa League",
    "conference": "Conference",
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


def reparar_mojibake(texto):
    texto = str(texto or "")
    try:
        reparado = texto.encode("latin1").decode("utf-8")
        if "�" not in reparado:
            return reparado
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return texto


def normalizar_nombre(nombre):
    texto = unicodedata.normalize("NFKD", reparar_mojibake(nombre))
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
            "partidos_restantes": restantes,
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


def texto_puntos(puntos):
    return f"{puntos} punto" if puntos == 1 else f"{puntos} puntos"


def nombre_objetivo(objetivo):
    return OBJETIVOS_AMPLIOS.get(objetivo, objetivo.replace("_", " "))


def evaluar_plaza(equipo, equipos, fin, objetivo):
    dentro, perseguidor = frontera_superior(equipos, fin)
    if not dentro:
        return None

    pos = equipo["posicion"]
    puntos = equipo["puntos"]
    maximo = equipo["maximo_puntos"]
    puntos_en_juego = equipo["puntos_en_juego"]
    etiqueta = nombre_objetivo(objetivo)

    if pos <= fin:
        if not perseguidor:
            return {
                "objetivo": objetivo,
                "estado": "asegurado_matematicamente",
                "vivo": False,
                "terminal": True,
                "distancia_o_colchon": None,
                "puntos_necesarios_para_asegurar": 0,
                "lectura": f"Tiene plaza de {etiqueta} asegurada por puntos.",
            }

        colchon = puntos - perseguidor["puntos"]
        asegurado = puntos > perseguidor["maximo_puntos"]
        puntos_para_asegurar = max(0, perseguidor["maximo_puntos"] + 1 - puntos)
        if asegurado:
            estado = "asegurado_matematicamente"
            lectura = (
                f"Tiene {etiqueta} asegurado: suma {puntos} puntos y "
                f"{perseguidor['equipo']} solo puede llegar a {perseguidor['maximo_puntos']}."
            )
        else:
            estado = "defiende_plaza"
            lectura = (
                f"Defiende plaza de {etiqueta} con {texto_puntos(colchon)} sobre "
                f"{perseguidor['equipo']}. Para asegurarla por puntos necesita "
                f"{texto_puntos(puntos_para_asegurar)} más."
            )
        return {
            "objetivo": objetivo,
            "estado": estado,
            "vivo": estado in ESTADOS_VIVOS,
            "terminal": estado == "asegurado_matematicamente",
            "distancia_o_colchon": colchon,
            "corte_equipo": perseguidor["equipo"],
            "corte_puntos_actuales": perseguidor["puntos"],
            "corte_maximo_puntos": perseguidor["maximo_puntos"],
            "puntos_necesarios_para_asegurar": puntos_para_asegurar,
            "lectura": lectura,
        }

    distancia = max(dentro["puntos"] + 1 - puntos, 0)
    puede_superar = maximo > dentro["puntos"]
    puede_igualar = maximo >= dentro["puntos"]
    if puede_superar:
        estado = "aspira_matematicamente"
        lectura = (
            f"Está fuera de {etiqueta}, pero puede alcanzarlo: necesita "
            f"{texto_puntos(distancia)} para superar sin desempates el corte de {dentro['equipo']}."
        )
    elif puede_igualar:
        estado = "aspira_por_desempate_o_fallo_ajeno"
        lectura = (
            f"Solo puede igualar el corte de {etiqueta}; necesita pleno y dependería "
            f"de desempates o fallos de {dentro['equipo']}."
        )
    else:
        estado = "sin_opciones_matematicas"
        lectura = (
            f"No llega por puntos a {etiqueta}: su máximo es {maximo} y "
            f"el corte actual de {dentro['equipo']} está en {dentro['puntos']}."
        )

    return {
        "objetivo": objetivo,
        "estado": estado,
        "vivo": estado in ESTADOS_VIVOS,
        "terminal": estado == "sin_opciones_matematicas",
        "distancia_o_colchon": -distancia,
        "corte_equipo": dentro["equipo"],
        "corte_puntos_actuales": dentro["puntos"],
        "puntos_necesarios_para_entrar": distancia,
        "depende_de_rivales": distancia > puntos_en_juego or estado == "aspira_por_desempate_o_fallo_ajeno",
        "lectura": lectura,
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
        campeon = equipo["puntos"] > segundo["maximo_puntos"]
        puntos_para_titulo = max(0, segundo["maximo_puntos"] + 1 - equipo["puntos"])
        estado = "campeon_matematico" if campeon else "defiende_liderato"
        lectura = (
            f"Ya es campeón matemático: suma {equipo['puntos']} puntos y "
            f"{segundo['equipo']} solo puede llegar a {segundo['maximo_puntos']}."
            if campeon else
            f"Lidera con {texto_puntos(colchon)} sobre {segundo['equipo']} y necesita "
            f"{texto_puntos(puntos_para_titulo)} para cerrar el título por puntos."
        )
        return {
            "objetivo": "titulo_liga",
            "estado": estado,
            "vivo": estado in ESTADOS_VIVOS,
            "terminal": campeon,
            "distancia_o_colchon": colchon,
            "puntos_necesarios_para_asegurar": puntos_para_titulo,
            "lectura": lectura,
        }

    distancia = max(lider["puntos"] + 1 - equipo["puntos"], 0)
    if equipo["maximo_puntos"] > lider["puntos"]:
        estado = "aspira_matematicamente"
        lectura = (
            f"Aún puede pelear el título por puntos: necesita {texto_puntos(distancia)} "
            f"para superar al líder {lider['equipo']}."
        )
    elif equipo["maximo_puntos"] >= lider["puntos"]:
        estado = "aspira_por_desempate_o_fallo_ajeno"
        lectura = f"Solo puede igualar al líder {lider['equipo']} y dependería de desempates."
    else:
        estado = "sin_opciones_matematicas"
        lectura = (
            f"No puede alcanzar el título: su máximo es {equipo['maximo_puntos']} y "
            f"{lider['equipo']} ya tiene {lider['puntos']}."
        )
    return {
        "objetivo": "titulo_liga",
        "estado": estado,
        "vivo": estado in ESTADOS_VIVOS,
        "terminal": estado == "sin_opciones_matematicas",
        "distancia_o_colchon": -distancia,
        "puntos_necesarios_para_entrar": distancia,
        "lectura": lectura,
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
        puntos_para_salir = max(equipo_safe["puntos"] + 1 - equipo["puntos"], 0)
        if equipo["maximo_puntos"] < equipo_safe["puntos"]:
            return {
                "objetivo": "situacion_final",
                "estado": "descendido_matematicamente",
                "vivo": False,
                "terminal": True,
                "distancia_o_colchon": -puntos_para_salir,
                "corte_equipo": equipo_safe["equipo"],
                "corte_puntos_actuales": equipo_safe["puntos"],
                "maximo_puntos": equipo["maximo_puntos"],
                "puntos_necesarios_para_salvarse": puntos_para_salir,
                "lectura": (
                    f"Descendido matemáticamente por puntos: aunque gane todo solo llega a "
                    f"{equipo['maximo_puntos']} y el corte de permanencia ya está en "
                    f"{equipo_safe['puntos']} ({equipo_safe['equipo']})."
                ),
            }

        depende = puntos_para_salir > equipo["puntos_en_juego"]
        lectura = (
            f"Está en descenso, pero aún tiene opciones. Necesita {texto_puntos(puntos_para_salir)} "
            f"para superar sin desempates el corte de {equipo_safe['equipo']} ({equipo_safe['puntos']})."
        )
        if depende:
            lectura += " Con los puntos que le quedan no le basta solo ganar: depende de rivales o desempates."
        return {
            "objetivo": nombre_objetivo,
            "estado": "en_descenso_con_opciones",
            "vivo": True,
            "terminal": False,
            "distancia_o_colchon": -puntos_para_salir,
            "corte_equipo": equipo_safe["equipo"],
            "corte_puntos_actuales": equipo_safe["puntos"],
            "puntos_necesarios_para_salvarse": puntos_para_salir,
            "depende_de_rivales": depende,
            "lectura": lectura,
        }

    colchon = equipo["puntos"] - equipo_descenso["puntos"]
    puntos_para_salvarse = max(equipo_descenso["maximo_puntos"] + 1 - equipo["puntos"], 0)
    salvado = equipo["puntos"] > equipo_descenso["maximo_puntos"]
    if salvado:
        estado = "salvado_matematicamente"
        objetivo = "situacion_final"
        lectura = (
            f"Salvado matemáticamente: tiene {equipo['puntos']} puntos y "
            f"{equipo_descenso['equipo']} solo puede llegar a {equipo_descenso['maximo_puntos']}."
        )
    elif colchon <= 3:
        estado = "riesgo_descenso"
        objetivo = nombre_objetivo
        lectura = (
            f"Riesgo de descenso: solo tiene {texto_puntos(colchon)} sobre "
            f"{equipo_descenso['equipo']}. Necesita {texto_puntos(puntos_para_salvarse)} "
            "para salvarse por puntos sin depender de otros."
        )
    elif colchon <= equipo_descenso["puntos_en_juego"]:
        estado = "permanencia_por_cerrar"
        objetivo = nombre_objetivo
        lectura = (
            f"Tiene ventaja, pero la permanencia no está cerrada. Colchón: "
            f"{texto_puntos(colchon)} sobre {equipo_descenso['equipo']}; necesita "
            f"{texto_puntos(puntos_para_salvarse)} para cerrarla por puntos."
        )
    else:
        estado = "ventaja_por_permanencia"
        objetivo = nombre_objetivo
        lectura = (
            f"Tiene {texto_puntos(colchon)} de margen sobre {equipo_descenso['equipo']}. "
            "No está marcado como salvado por puntos puros, pero el riesgo es bajo."
        )

    return {
        "objetivo": objetivo,
        "estado": estado,
        "vivo": estado in ESTADOS_VIVOS,
        "terminal": estado == "salvado_matematicamente",
        "distancia_o_colchon": colchon,
        "corte_equipo": equipo_descenso["equipo"],
        "corte_puntos_actuales": equipo_descenso["puntos"],
        "corte_maximo_puntos": equipo_descenso["maximo_puntos"],
        "puntos_necesarios_para_salvarse": puntos_para_salvarse,
        "lectura": lectura,
    }


def nivel_motivacion(objetivos):
    score = 0
    for objetivo in objetivos:
        estado = objetivo.get("estado")
        if estado in {"en_descenso_con_opciones", "riesgo_descenso", "defiende_liderato", "defiende_plaza"}:
            score += 3
        elif estado in {"aspira_matematicamente", "permanencia_por_cerrar"}:
            score += 2
        elif estado in {"aspira_por_desempate_o_fallo_ajeno", "ventaja_por_permanencia"}:
            score += 1

    if score >= 7:
        return "maxima"
    if score >= 4:
        return "alta"
    if score >= 1:
        return "media"
    return "baja"


def elegir_objetivo_principal(objetivos):
    if not objetivos:
        return None
    return sorted(
        objetivos,
        key=lambda objetivo: PRIORIDAD_OBJETIVO.get(objetivo.get("estado"), 0),
        reverse=True,
    )[0]


def cerrar_equipo(equipo, objetivos):
    visibles = [objetivo for objetivo in objetivos if objetivo]
    equipo["objetivos"] = visibles
    equipo["objetivos_vivos"] = [objetivo for objetivo in visibles if objetivo.get("vivo")]
    equipo["objetivo_principal"] = elegir_objetivo_principal(visibles)

    if not equipo["objetivos_vivos"] and not equipo["objetivo_principal"]:
        equipo["objetivo_principal"] = {
            "objetivo": "situacion_final",
            "estado": "no_se_juega_nada_clasificatorio",
            "vivo": False,
            "terminal": True,
            "lectura": "Por puntos no tiene un objetivo clasificatorio vivo claro para la jornada.",
        }
        equipo["objetivos"] = [equipo["objetivo_principal"]]

    equipo["motivacion_competitiva"] = nivel_motivacion(equipo["objetivos_vivos"])
    equipo["motivacion"] = equipo["motivacion_competitiva"]
    principal = equipo.get("objetivo_principal") or {}
    equipo["lectura_resumen"] = principal.get("lectura", "Sin lectura competitiva clara.")
    equipo["situacion_competitiva"] = principal.get("estado", "no_se_juega_nada_clasificatorio")
    return equipo


def resumen_frontera(equipos, fin, etiqueta):
    dentro, fuera = frontera_superior(equipos, fin)
    if not dentro or not fuera:
        return None
    diferencia = dentro["puntos"] - fuera["puntos"]
    if dentro["puntos"] > fuera["maximo_puntos"]:
        return (
            f"{etiqueta}: {dentro['equipo']} tiene el corte asegurado por puntos; "
            f"{fuera['equipo']} solo puede llegar a {fuera['maximo_puntos']}."
        )
    return (
        f"{etiqueta}: {dentro['equipo']} marca el corte con {dentro['puntos']} puntos; "
        f"{fuera['equipo']} persigue a {texto_puntos(diferencia)}."
    )


def resumen_titulo(equipos):
    if len(equipos) < 2:
        return None
    lider, segundo = equipos[0], equipos[1]
    if lider["puntos"] > segundo["maximo_puntos"]:
        return (
            f"Título: {lider['equipo']} ya es campeón matemático con {lider['puntos']} puntos; "
            f"{segundo['equipo']} solo puede llegar a {segundo['maximo_puntos']}."
        )
    diferencia = lider["puntos"] - segundo["puntos"]
    return f"Título: {lider['equipo']} lidera con {lider['puntos']} puntos; {segundo['equipo']} está a {texto_puntos(diferencia)}."


def resumen_descenso(equipos, plazas, etiqueta):
    total = len(equipos)
    if total <= plazas:
        return None
    safe = equipos[total - plazas - 1]
    drop = equipos[total - plazas]
    matematicos = [e["equipo"] for e in equipos[total - plazas:] if e["maximo_puntos"] < safe["puntos"]]
    diferencia = safe["puntos"] - drop["puntos"]
    base = f"{etiqueta}: {safe['equipo']} está justo fuera con {safe['puntos']}; {drop['equipo']} está dentro a {texto_puntos(diferencia)}."
    if matematicos:
        base += f" Descendidos matemáticos por puntos: {', '.join(matematicos)}."
    return base


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
        analizados.append(cerrar_equipo(equipo, objetivos))

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
        analizados.append(cerrar_equipo(equipo, objetivos))

    lecturas = [
        resumen_frontera(equipos, fin_directo, "Ascenso directo"),
        resumen_frontera(equipos, fin_playoff, "Promoción de ascenso"),
        resumen_descenso(equipos, reglas["descenso"], "Descenso a Primera Federación"),
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
        "version": "1.1",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": "Contexto de objetivos, puntos en juego y presión competitiva para calibrar predicciones de final de temporada.",
        "reglas": REGLAS,
        "primera": analizar_primera(clasificaciones.get("primera", [])),
        "segunda": analizar_segunda(clasificaciones.get("segunda", [])),
    }
    guardar_json(MEMORIA / "contexto_competitivo.json", salida)
    print(MEMORIA / "contexto_competitivo.json")


if __name__ == "__main__":
    main()
