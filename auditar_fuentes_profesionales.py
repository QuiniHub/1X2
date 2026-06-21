import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
MEMORIA = DATA / "memoria_ia"
OUT = DATA / "fuentes_profesionales.json"

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


def main():
    estados = Counter(item["estado"] for item in FUENTES.values())
    criticas_pendientes = [
        clave for clave, item in FUENTES.items()
        if item.get("prioridad") == "critica" and str(item.get("estado", "")).startswith("pendiente")
    ]
    salida = {
        "version": "1.0",
        "generado_en": ahora(),
        "objetivo": "motor autonomo con datos profesionales, aprendizaje real y probabilidades calibradas",
        "estado_global": "en_construccion" if criticas_pendientes else "base_critica_cubierta",
        "fuentes": FUENTES,
        "resumen": {
            "total": len(FUENTES),
            "estados": dict(estados),
            "criticas_pendientes": criticas_pendientes,
            "lectura": "Mientras existan fuentes criticas pendientes, las probabilidades deben marcarse como no plenamente calibradas.",
        },
    }
    guardar_json(OUT, salida)
    print(f"Fuentes profesionales auditadas: {len(FUENTES)} fuentes, {len(criticas_pendientes)} criticas pendientes.")


if __name__ == "__main__":
    main()
