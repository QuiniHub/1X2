import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
CORRECCIONES = DATA / "correcciones_resultados.json"


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


def normalizar(texto):
    texto = reparar_mojibake(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|club|real|de|del|la|el|balompie|futbol)\b", " ", texto)
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def activa(correccion):
    hasta = correccion.get("aplicar_hasta_utc")
    if not hasta:
        return True
    try:
        limite = datetime.fromisoformat(str(hasta).replace("Z", "+00:00"))
    except ValueError:
        return True
    return datetime.now(timezone.utc) <= limite


def mismos_equipos(partido, correccion, tolerante=False):
    if (
        normalizar(partido.get("local")) == normalizar(correccion.get("local"))
        and normalizar(partido.get("visitante")) == normalizar(correccion.get("visitante"))
    ):
        return True
    if not tolerante:
        return False
    # La fuente de resultados reescribe nombres ('Real Racing Club de Santander'
    # pasa a 'R. Santander'): comparacion tolerante comun del proyecto.
    import cronologia_jornadas

    return (
        cronologia_jornadas.mismo_equipo(partido.get("local"), correccion.get("local"))
        and cronologia_jornadas.mismo_equipo(partido.get("visitante"), correccion.get("visitante"))
    )


def mismo_partido(partido, correccion, num_partido=None):
    """Una correccion casa con un partido si coinciden los EQUIPOS.

    Auditoria 26/11 (hallazgo 56): bastaba con que coincidiera 'num', asi que
    una correccion de la J62 de 25/26 (sin caducidad) se habria aplicado al
    partido 8 de la J62 de 26/27 aunque fueran otros equipos. Ahora:
      * si la correccion trae equipos, tienen que coincidir siempre;
      * si ademas trae 'num' y el partido tiene numero, tambien el numero;
      * solo una correccion SIN equipos se casa por numero.
    """
    numero = partido.get("num") if num_partido is None else num_partido
    num_correccion = correccion.get("num")
    con_equipos = bool(correccion.get("local") and correccion.get("visitante"))
    if not con_equipos:
        return bool(num_correccion) and int(numero or 0) == int(num_correccion)
    if num_correccion and numero:
        if int(numero) != int(num_correccion):
            return False
        # Mismo numero de casilla: se toleran las variantes de nombre.
        return mismos_equipos(partido, correccion, tolerante=True)
    # Sin numero (calendarios de Liga): solo el nombre exacto normalizado.
    return mismos_equipos(partido, correccion)


def vigente_para_calendario(correccion):
    """Una correccion ligada a una jornada de La Quiniela solo se lleva al
    calendario de Liga mientras jornada_N.json siga siendo ESA jornada (mismo
    partido). Cuando el numero se reutiliza en la temporada siguiente, la
    correccion vieja deja de aplicarse sola (p. ej. 'Real Madrid - Oviedo 2-0'
    de la J62 de 25/26 no puede pisar el Real Madrid - Oviedo de otra liga)."""
    jornada = correccion.get("jornada")
    if not jornada:
        return True
    data = cargar_json(JORNADAS / f"jornada_{jornada}.json", {})
    if not data or not temporada_compatible(data, correccion, jornada):
        return False
    partidos = list(data.get("partidos", []))
    pleno = data.get("pleno15") or {}
    if pleno:
        partidos.append({**pleno, "num": pleno.get("num") or 15})
    return any(mismo_partido(p, correccion) for p in partidos)


def temporada_compatible(data, correccion, numero):
    """Si la correccion declara 'temporada' ('2025_2026', '2025/2026'...), el
    fichero jornada_N.json tiene que ser de esa temporada (por fecha real)."""
    declarada = correccion.get("temporada")
    if not declarada:
        return True
    import cronologia_jornadas

    fecha = cronologia_jornadas.fecha_real_jornada(data)
    if fecha is None:
        return False
    real = cronologia_jornadas.temporada_de_fecha(fecha, numero)
    digitos = re.findall(r"\d+", str(declarada))
    if len(digitos) < 2:
        return False
    inicio = int(digitos[0])
    return real == f"{inicio}_{inicio + 1}"


def aplicar_en_jornadas(correcciones):
    cambios = 0
    for correccion in correcciones:
        jornada = correccion.get("jornada")
        if not jornada:
            continue
        path = JORNADAS / f"jornada_{jornada}.json"
        data = cargar_json(path, {})
        if not data:
            continue
        if not temporada_compatible(data, correccion, jornada):
            continue
        cambios_antes = cambios
        for partido in data.get("partidos", []):
            if not mismo_partido(partido, correccion):
                continue
            resultado = correccion.get("resultado", "Pendiente")
            signo = correccion.get("signo_oficial", "Pendiente")
            estado_partido = correccion.get("estado_calendario")
            if (partido.get("resultado") != resultado or partido.get("signo_oficial") != signo
                    or (estado_partido and partido.get("estado") != estado_partido)):
                partido["resultado"] = resultado
                partido["signo_oficial"] = signo
                if estado_partido:
                    # p.ej. "Aplazado": la compuerta lo necesita en la jornada,
                    # no solo en el calendario (caso Levante-Athletic 16/09/2026)
                    partido["estado"] = estado_partido
                partido.pop("actualizado_en", None)
                partido["corregido_en"] = datetime.now(timezone.utc).isoformat()
                partido["correccion_motivo"] = correccion.get("motivo", "")
                cambios += 1
        pleno = data.get("pleno15") or {}
        if pleno and mismo_partido(pleno, correccion, num_partido=pleno.get("num") or 15):
            resultado = correccion.get("resultado", "Pendiente")
            signo = correccion.get("signo_oficial", "Pendiente")
            if pleno.get("resultado") != resultado or pleno.get("signo_oficial") != signo:
                pleno["resultado"] = resultado
                pleno["signo_oficial"] = signo
                pleno.pop("actualizado_en", None)
                pleno["corregido_en"] = datetime.now(timezone.utc).isoformat()
                pleno["correccion_motivo"] = correccion.get("motivo", "")
                cambios += 1
        if cambios == cambios_antes:
            # Sin cambios no se reescribe el fichero ni se recalcula su estado
            # (antes se guardaba en cada ciclo, hubiera o no correccion).
            continue
        data["estado"] = "cerrada" if all(
            str(p.get("signo_oficial", "")).upper() in ("1", "X", "2")
            for p in data.get("partidos", [])
        ) else "en_juego"
        guardar_json(path, data)
    return cambios


def aplicar_en_calendarios(correcciones):
    cambios = 0
    for archivo in (DATA / "calendario_primera.json", DATA / "calendario_segunda.json"):
        data = cargar_json(archivo, {})
        if not data:
            continue
        cambios_antes = cambios
        for correccion in correcciones:
            for jornada in data.get("jornadas", []):
                for partido in jornada.get("partidos", []):
                    if not mismo_partido(partido, correccion):
                        continue
                    resultado = correccion.get("resultado", "Pendiente")
                    nuevo_resultado = "" if str(resultado).lower() == "pendiente" else resultado
                    nuevo_estado = correccion.get("estado_calendario") or ("Programado" if not nuevo_resultado else "Jugado")
                    if partido.get("resultado") != nuevo_resultado or partido.get("estado") != nuevo_estado:
                        partido["resultado"] = nuevo_resultado
                        partido["estado"] = nuevo_estado
                        partido.pop("actualizado_en", None)
                        partido["corregido_en"] = datetime.now(timezone.utc).isoformat()
                        partido["correccion_motivo"] = correccion.get("motivo", "")
                        cambios += 1
        if cambios != cambios_antes:
            guardar_json(archivo, data)
    return cambios


def main():
    correcciones = [
        c for c in cargar_json(CORRECCIONES, {"correcciones": []}).get("correcciones", [])
        if activa(c)
    ]
    if not correcciones:
        print("Sin correcciones activas.")
        return
    cambios = aplicar_en_jornadas(correcciones) + aplicar_en_calendarios(
        [c for c in correcciones if vigente_para_calendario(c)]
    )
    print(f"Correcciones de resultados aplicadas: {cambios}")


if __name__ == "__main__":
    main()
