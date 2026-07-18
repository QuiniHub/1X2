import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia"
OUT = DATA / "fuentes_profesionales.json"
DATOS_PROFESIONALES = DATA / "datos_profesionales.json"
FUENTE_LOSILLA = MEMORIA / "fuente_losilla.json"
FUENTE_LESIONES_LALIGA = MEMORIA / "fuente_lesiones_laliga.json"

FUENTES = {
    "resultados_directo_consenso": {
        "estado": "conectado_fragil",
        "prioridad": "critica",
        "uso": "cerrar jornadas, validar signos oficiales y activar aprendizaje real",
        "siguiente_paso": "comparar fuente actual contra segunda fuente o API oficial/licenciada",
    },
    "cuotas_mercado": {
        "estado": "pendiente_api",
        "prioridad": "critica",
        "uso": "transformar mercado en probabilidad base y detectar favoritos mal valorados",
        "siguiente_paso": "conectar proveedor de cuotas 1X2 con snapshots antes del cierre",
    },
    "movimiento_cuotas": {
        "estado": "pendiente_api",
        "prioridad": "alta",
        "uso": "detectar cambios de informacion antes del cierre",
        "siguiente_paso": "guardar apertura, 48h, 24h, 6h y cierre",
    },
    "xg_xga": {
        "estado": "pendiente_fuente",
        "prioridad": "alta",
        "uso": "medir calidad real ofensiva y defensiva mas alla del marcador",
        "siguiente_paso": "cargar xG/xGA por equipo, condicion local/visitante y ultimos partidos",
    },
    "lesiones_sanciones": {
        "estado": "parcial_no_estructurado",
        "prioridad": "critica",
        "uso": "evitar fijos debiles por bajas clave o sanciones",
        "siguiente_paso": "estructurar parte medico y sanciones por jugador e impacto",
    },
    "alineaciones_probables": {
        "estado": "pendiente_fuente",
        "prioridad": "alta",
        "uso": "detectar rotaciones y titulares dudosos",
        "siguiente_paso": "cargar once probable y probabilidad de titularidad",
    },
    "calendario_oficial_2026_2027": {
        "estado": "pendiente_publicacion_o_api",
        "prioridad": "critica",
        "uso": "memorizar calendario nuevo de Primera/Segunda cuando este publicado oficialmente",
        "siguiente_paso": "inyectar calendario oficial 2026/2027 por QUINIHUB_PRO_DATA_URL o proveedor autorizado",
    },
    "ranking_elo": {
        "estado": "pendiente_dataset",
        "prioridad": "alta",
        "uso": "comparar fuerza entre selecciones, ligas y equipos de distinto nivel",
        "siguiente_paso": "versionar ELO por fecha y equipo/seleccion",
    },
    "forma_vs_rivales": {
        "estado": "pendiente_modelado",
        "prioridad": "media",
        "uso": "ponderar forma reciente por dificultad del rival",
        "siguiente_paso": "ajustar forma por ELO, posicion y condicion local/visitante",
    },
    "descanso_fatiga": {
        "estado": "pendiente_modelado",
        "prioridad": "media",
        "uso": "medir dias de descanso, viajes y carga competitiva",
        "siguiente_paso": "calcular dias desde ultimo partido y carga acumulada",
    },
    "clasificacion_real_competicion": {
        "estado": "conectado_parcial",
        "prioridad": "critica",
        "uso": "saber objetivos reales por liga, grupo o eliminatoria",
        "siguiente_paso": "ampliar tablas a Mundial, ligas extranjeras y copas",
    },
    "motivacion_matematica": {
        "estado": "parcial",
        "prioridad": "critica",
        "uso": "calcular titulo, ascenso, playoff, descenso, clasificacion o eliminacion",
        "siguiente_paso": "calcular puntos en juego y estados vivos/cerrados por competicion",
    },
    "arbitros_clima": {
        "estado": "pendiente_fuente",
        "prioridad": "media",
        "uso": "ajustar ritmo, tarjetas, penaltis y condiciones externas",
        "siguiente_paso": "conectar asignaciones arbitrales y clima/sede",
    },
    "porcentajes_publicos_quiniela": {
        "estado": "pendiente_fuente",
        "prioridad": "alta",
        "uso": "detectar signos populares y sorpresas con mayor valor estrategico",
        "siguiente_paso": "guardar distribucion publica 1/X/2 por casilla si la fuente existe",
    },
}


def ahora():
    return datetime.now(timezone.utc).isoformat()


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def copiar_fuentes():
    return json.loads(json.dumps(FUENTES, ensure_ascii=False))


def mensaje_error_conexion_api_football(errores_api_football, estado_cuenta):
    """Construye un mensaje accionable para un 403/fallo de API-Football.
    Antes solo se citaba el error crudo de un fixture concreto -no decia si
    el token estaba mal, caducado, o si simplemente el plan (a menudo el
    gratuito) no cubre esa liga/temporada. estado_cuenta viene de
    datos_profesionales.estado_cuenta_api_football() (endpoint /status,
    barato y disponible incluso en el plan gratuito)."""
    ejemplo = errores_api_football[0] if errores_api_football else "sin detalle"
    if not (estado_cuenta or {}).get("ok"):
        error_status = (estado_cuenta or {}).get("error") or "sin respuesta"
        return (
            f"token/URL configurados pero la API no responde datos (ej: {ejemplo}); "
            f"tampoco se pudo consultar /status ({error_status}) -revisar si el token es valido."
        )
    plan = estado_cuenta.get("plan") or "desconocido"
    activa = estado_cuenta.get("activa")
    usadas = estado_cuenta.get("peticiones_usadas")
    limite = estado_cuenta.get("peticiones_limite")
    return (
        f"Cuenta API-Football: plan '{plan}', activa={activa}, "
        f"peticiones hoy {usadas}/{limite}. El token es valido pero la API sigue "
        f"sin dar datos de fixtures (ej: {ejemplo}) -revisar si el plan '{plan}' "
        f"cubre la temporada/ligas configuradas (subir de plan si no)."
    )


def aplicar_estado_conector(fuentes, datos, fuente_losilla=None, fuente_lesiones_laliga=None):
    resumen = datos.get("resumen") or {}
    estado_global = str(datos.get("estado_global") or "").lower()
    configuracion = datos.get("configuracion") or {}
    errores_api_football = (((datos.get("proveedores") or {}).get("api_football") or {}).get("errores") or [])
    estado_cuenta_api_football = ((datos.get("proveedores") or {}).get("api_football") or {}).get("estado_cuenta") or {}
    # Token/URL configurados pero la API sigue sin dar ni un solo partido: es
    # un fallo de conexion real (token invalido, plan sin cobertura de la
    # temporada/liga...), muy distinto de "pendiente_secret" (nunca
    # configurado). Sin distinguirlos, un token roto se ve identico a un
    # token que nunca se puso.
    error_conexion_api_football = (
        bool(configuracion.get("token_configurado"))
        and not int(resumen.get("cuotas") or 0)
        and bool(errores_api_football)
    )

    # porcentajes_publicos_quiniela venia marcada "pendiente_fuente" a mano y
    # nunca se comprobaba contra el estado real de fuente_losilla.json -que
    # ya lleva desde el 2026-07-08 scrapeando el % de jugados/probables/LAE
    # de eduardolosilla.es (ajustar_por_mercado_losilla lo usa desde el
    # 2026-07-14)-. Sin esto, este diagnostico decia "pendiente" de una
    # fuente que ya estaba conectada y en uso real.
    partidos_porcentaje = (((fuente_losilla or {}).get("probabilidades") or {}).get("partidos") or [])
    if len(partidos_porcentaje) >= 10:
        fuentes["porcentajes_publicos_quiniela"]["estado"] = "conectado_scraper"
        fuentes["porcentajes_publicos_quiniela"]["siguiente_paso"] = (
            "ya integrado como señal directa (ajustar_por_mercado_losilla, peso 0.18); "
            "recalibrar el peso con mas jornadas reales."
        )

    if int(resumen.get("cuotas") or 0) > 0:
        fuentes["cuotas_mercado"]["estado"] = "conectado_api"
        fuentes["cuotas_mercado"]["siguiente_paso"] = "guardar snapshots apertura, 48h, 24h, 6h y cierre"
        fuentes["movimiento_cuotas"]["estado"] = "base_snapshot"
    elif estado_global == "pendiente_secrets":
        fuentes["cuotas_mercado"]["estado"] = "pendiente_secret"
    elif error_conexion_api_football:
        fuentes["cuotas_mercado"]["estado"] = "error_conexion"
        fuentes["cuotas_mercado"]["siguiente_paso"] = mensaje_error_conexion_api_football(
            errores_api_football, estado_cuenta_api_football
        )

    if int(resumen.get("bajas_estructuradas") or 0) > 0:
        fuentes["lesiones_sanciones"]["estado"] = "conectado_estructurado"
        fuentes["lesiones_sanciones"]["siguiente_paso"] = "medir impacto por titularidad y minutos esperados"
    elif estado_global == "pendiente_secrets":
        fuentes["lesiones_sanciones"]["estado"] = "pendiente_secret"
    elif error_conexion_api_football:
        fuentes["lesiones_sanciones"]["estado"] = "error_conexion"
        fuentes["lesiones_sanciones"]["siguiente_paso"] = mensaje_error_conexion_api_football(
            errores_api_football, estado_cuenta_api_football
        )

    # lesiones_sanciones estaba atascada en "error_conexion" porque
    # API-Football (de pago) no cubre la temporada en el plan Free -pero
    # desde el 2026-07-18 tenemos actualizar_fuente_lesiones_laliga.py
    # scrapeando futbolfantasy.com, una fuente real e independiente. Si
    # tiene equipos con datos, la critica esta resuelta sin depender de
    # que API-Football se arregle o se pague.
    equipos_lesiones_laliga = ((fuente_lesiones_laliga or {}).get("equipos") or {})
    if len(equipos_lesiones_laliga) >= 10:
        fuentes["lesiones_sanciones"]["estado"] = "conectado_scraper"
        fuentes["lesiones_sanciones"]["siguiente_paso"] = (
            "ya integrado como señal directa (ajustar_por_lesiones_laliga, LaLiga/Hypermotion); "
            "ampliar a otras ligas y pesar por titularidad real cuando haya alineaciones probables."
        )

    if int(resumen.get("alineaciones_probables") or 0) > 0:
        fuentes["alineaciones_probables"]["estado"] = "conectado_estructurado"
        fuentes["alineaciones_probables"]["siguiente_paso"] = "comparar once probable contra once confirmado y aprender errores"
    elif estado_global == "pendiente_secrets":
        fuentes["alineaciones_probables"]["estado"] = "pendiente_secret"
    elif error_conexion_api_football:
        fuentes["alineaciones_probables"]["estado"] = "error_conexion"
        fuentes["alineaciones_probables"]["siguiente_paso"] = mensaje_error_conexion_api_football(
            errores_api_football, estado_cuenta_api_football
        )

    if int(resumen.get("calendario_oficial") or 0) > 0:
        fuentes["calendario_oficial_2026_2027"]["estado"] = "conectado_normalizado"
        fuentes["calendario_oficial_2026_2027"]["siguiente_paso"] = "validar cambios de fechas/horarios y congelar snapshot por jornada"

    if int(resumen.get("clasificacion_oficial") or 0) > 0:
        fuentes["clasificacion_real_competicion"]["estado"] = "conectado_normalizado"
        fuentes["clasificacion_real_competicion"]["siguiente_paso"] = "versionar tablas por fecha para medir objetivos vivos"

    return fuentes


def main():
    datos = cargar_json(DATOS_PROFESIONALES, {})
    fuente_losilla = cargar_json(FUENTE_LOSILLA, {})
    fuente_lesiones_laliga = cargar_json(FUENTE_LESIONES_LALIGA, {})
    fuentes = aplicar_estado_conector(copiar_fuentes(), datos, fuente_losilla, fuente_lesiones_laliga)
    estados = Counter(item["estado"] for item in fuentes.values())
    # "error_conexion" tampoco cuenta como resuelto: es una fuente critica
    # configurada pero que no entrega datos, no menos urgente que una que
    # nunca se configuro -si solo se mirara el prefijo "pendiente", una API
    # rota desaparecia de esta lista y el estado global diria erroneamente
    # que las fuentes criticas ya estan cubiertas.
    criticas_pendientes = [
        clave for clave, item in fuentes.items()
        if item.get("prioridad") == "critica"
        and (str(item.get("estado", "")).startswith("pendiente") or item.get("estado") == "error_conexion")
    ]
    salida = {
        "version": "1.0",
        "generado_en": ahora(),
        "objetivo": "motor autonomo con datos profesionales, aprendizaje real y probabilidades calibradas",
        "estado_global": "en_construccion" if criticas_pendientes else "base_critica_cubierta",
        "fuentes": fuentes,
        "datos_profesionales": {
            "estado_global": datos.get("estado_global"),
            "temporada_objetivo": datos.get("temporada_objetivo"),
            "generado_en": datos.get("generado_en"),
            "resumen": datos.get("resumen", {}),
            "configuracion": datos.get("configuracion", {}),
        },
        "resumen": {
            "total": len(fuentes),
            "estados": dict(estados),
            "criticas_pendientes": criticas_pendientes,
            "lectura": "Mientras existan fuentes criticas pendientes, las probabilidades deben marcarse como no plenamente calibradas.",
        },
    }
    guardar_json(OUT, salida)
    print(f"Fuentes profesionales auditadas: {len(FUENTES)} fuentes, {len(criticas_pendientes)} criticas pendientes.")


if __name__ == "__main__":
    main()
