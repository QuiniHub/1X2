import json
import os
import subprocess
import sys
import traceback
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
HISTORIAL_FALLOS = ROOT / "data" / "diagnostico_fallos_cronicos.json"
UMBRAL_FALLO_CRONICO = 3

# Auditoria 26/11/2026 (hallazgo 169): ningun subproceso tenia timeout y el job
# tampoco (360 min por defecto). Un fetcher colgado bloqueaba el ciclo entero.
# El ciclo completo dura unos 5 minutos; 15 minutos por script es holgura de
# sobra. Se puede cambiar con la variable ACTUALIZAR_TODO_TIMEOUT_SEG.
TIMEOUT_SCRIPT_SEG_DEFECTO = 900
SCRIPT_CONGELAR = "congelar_bloques_sombra.py"


def timeout_script_seg():
    try:
        valor = int(os.environ.get("ACTUALIZAR_TODO_TIMEOUT_SEG") or 0)
    except (TypeError, ValueError):
        valor = 0
    return valor if valor > 0 else TIMEOUT_SCRIPT_SEG_DEFECTO


class ErrorCriticoPrediccion(Exception):
    """Fallo que debe detener el proceso por datos de prediccion."""


SCRIPTS_CRITICOS_PREDICCION = {
    "motor_prediccion_objetivo.py",
    "validar_publicacion_autonoma.py",
}

SCRIPTS_ACTIVOS = [
    # --- Fuente oficial prioritaria ---
    "actualizar_fuente_lae.py",

    # --- Datos base ---
    "actualizar_jornadas_detalle.py",
    # actualizar_resultados_libres.py corre aqui (antes de actualizar_boleto_vivo.py)
    # para que este pueda usar ESPN/TheSportsDB como respaldo con datos frescos
    # del mismo ciclo, no del ciclo anterior.
    "actualizar_resultados_libres.py",
    "actualizar_boleto_vivo.py",
    "asegurar_proxima_jornada.py",
    "buscar_resultados_google.py",
    "actualizar_resultados_directo.py",
    "aplicar_correcciones_resultados.py",
    "actualizar_monitor_temporadas.py",
    "actualizar_clasificaciones_oficiales.py",
    "corregir_clasificacion_segunda.py",
    "actualizar_ligas_football_data.py",
    "cargar_historico_ligas_espana.py",
    "cargar_historico_quinielas_lae.py",
    "actualizar_detalles_partidos.py",
    "recalcular_dinamicas_calendario.py",
    "actualizar_fuente_losilla.py",
    # Versiona el % de apostantes LAE por jornada (columna "lae" de Losilla)
    # y captura el escrutinio real de jornadas cerradas: insumos del
    # optimizador de EV del premio y de su backtest (candidato 3).
    "actualizar_porcentajes_lae.py",
    "actualizar_fuente_lesiones_laliga.py",
    "actualizar_fuente_lesiones_jornadaperfecta.py",
    # Liga F real (Wikipedia, gratis): clasificacion + resultados para que los
    # partidos "(F)" dejen de ir a ciegas (auditoria 16/11/2026).
    "actualizar_liga_f.py",
    "actualizar_contexto_equipos.py",
    "actualizar_analisis_ia.py",
    "construir_historial_quinielas.py",
    "actualizar_aprendizaje_ia.py",
    "generar_artefactos_compuerta_aprendizaje.py",
    # Cuadernos del Laboratorio 26/11/2026 (walk-forward sin fuga de futuro,
    # ~15 s en total): calibracion de la X, prior europeo y mezcla de Benter
    # se re-miden con cada jornada cerrada; sus veredictos prerregistrados
    # mandan sobre si actuan (hoy: calibracion DESPLEGAR en traza; prior y
    # Benter NO_DESPLEGAR, no-op).
    "calibracion_x.py",
    "prior_europeo.py",
    "mezcla_benter.py",
    # generar_diario_aprendizaje.py retirado (01/09/2026): escribia el
    # diario y construir_memoria_ia.py lo REESCRIBIA una linea despues -el
    # archivo publicado ni siquiera era el que consumian sorpresas/pesos/
    # compuerta. Un solo escritor canonico: construir_memoria_ia.py.
    "construir_memoria_ia.py",
    # Equipos empatadores + nuestra fiabilidad por equipo (06/10/2026): el
    # panel de avisos de la web consume equipos_x_fiabilidad.json (chips
    # "empatador"/"nemesis"); sin regenerarlo cada ciclo, los porcentajes se
    # quedarian congelados en la foto del 05/10. Va despues de
    # construir_memoria_ia porque lee el diario de aprendizaje recien escrito.
    "estudio_equipos_x_y_fiabilidad.py",
    "aprender_de_historial_resultados.py",
    "memoria_autonoma_quiniela.py",
    "sincronizar_dinamicas_memoria.py",

    # --- Fuente unica de verdad competitiva ---
    "generar_contexto_competitivo.py",
    # aplicar_objetivos_oficiales_json.py retirado de la cadena (auditoria
    # 26/11/2026, hallazgo 170): aplicaba el MISMO fichero de overrides que
    # forzar_overrides.py, que corre justo despues y pisa su resultado
    # (objetivos = [override]). El resultado final era siempre el de forzar.
    # El modulo se conserva porque exporta overrides_vigentes().
    "forzar_overrides.py",
    "validar_contexto_actual.py",
    "construir_fuente_verdad_competitiva.py",

    # --- Competiciones internacionales y datos profesionales ---
    # --- Resultados via APIs (BallDontLie, API-Football, openfootball) ---
    "actualizar_resultados_apis.py",
    "actualizar_datos_profesionales.py",
    "auditar_fuentes_profesionales.py",
    "resolver_competiciones_profesionales.py",

    # --- Capa predictiva entrenable ---
    "modelo_metricas_1x2.py",

    # --- Comp puerta de resultados antes de predecir ---
    "sincronizar_resultados_jornada.py",
    "compuerta_jornada.py",

    # --- Motor predictivo y salidas ---
    "aprender_patrones_competitivos.py",
    "alimentar_sorpresas_mercado.py",
    "motor_prediccion_objetivo.py",
    "alinear_boleto_con_analisis.py",
    # Congelacion TEMPRANA (auditoria 26/11/2026, hallazgo 118): con la jornada
    # en juego el motor acaba de reescribir la prediccion sin mercado; si solo
    # se congela al final, todo lo que se deriva entre medias (estado vivo,
    # premios, diagnostico, memoria historica) se calcula con una prediccion
    # que no es la publicada. El snapshot pre-cierre ya es inmutable desde el
    # primer partido, asi que se puede restaurar aqui. Con la jornada sin
    # empezar no hace nada. La congelacion FINAL (abajo) sigue haciendo falta:
    # los modulos en sombra y calibrar reescriben bloques despues.
    "congelar_bloques_sombra.py",
    "generar_estado_vivo_ia.py",
    "ajustar_estado_vivo_motivacion.py",
    "corregir_emparejamiento_equipos.py",
    # Boleto EV del premio (candidato 3): lee la prediccion ya corregida y
    # anade el bloque boleto_ev_premio sin tocar la recomendacion conservadora.
    "optimizador_ev_premio.py",
    # La Valiente (modo sombra, 14/10/2026): una sorpresa formal por jornada
    # con señal contextual dura + filtro de pago, publicada y medida SIN
    # dinero (bloque "valiente"). Corre tras el optimizador EV: lee la misma
    # prediccion corregida y los mismos % de apostantes LAE.
    "senal_valiente.py",
    # Tercero de Valor (modo sombra, 19/10/2026): el tercero (signo de menor
    # probabilidad) mejor pagado de la jornada -prob CALIBRADA por signo muy
    # por encima del % de masa LAE- publicado y medido SIN dinero (bloque
    # "tercero_valor"). Corre tras La Valiente: misma prediccion y misma masa.
    "tercero_valor.py",
    # Radar de Tormenta (modo sombra, 21/10/2026): hasta 3 partidos en "zona
    # de tormenta" (sin dueño / equipos del caos del estudio de terceros) con
    # su signo del rayo (no-X de menor masa), publicado y medido SIN dinero
    # (bloque "radar_tormenta"). Corre tras Tercero de Valor: misma masa.
    "radar_tormenta.py",
    # Sorpresa Nombrada (modo sombra, 22/11/2026, regla de Marc tras Athletic
    # 0-1 Espanyol y Rayo 0-1 Valencia): UNA sorpresa por jornada dicha ANTES
    # del cierre, en la franja 20-33% y con señal calculable (especialista de
    # rol, banquillo nuevo, H2H adverso reciente, empatador, mercado mas alto),
    # publicada y medida SIN dinero (bloque "sorpresa_nombrada"). Corre tras
    # el radar: misma prediccion.
    "sorpresa_nombrada.py",
    # Ranker de favoritos en riesgo (26/11/2026, informe 'Algoritmos contra
    # nuestros fallos', punto 6): SOLO SOMBRA (walk-forward NO_SEPARA con n=42);
    # publica el bloque "favoritos_en_riesgo" con UN favorito nombrado por
    # jornada y lo mide en marcador_ranker_favoritos.json. Usa las señales de
    # sorpresa_nombrada: corre despues.
    "ranker_favoritos.py",
    # Columna valiente europea (23/11/2026, bronca de Marc "de que sirve anotar
    # si no lo aplicas"): en jornadas europeas publica la columna sencilla con
    # las sorpresas puestas (X en los sin dueno, espanol favorito fuera, la
    # sorpresa nombrada) y la mide contra la columna de la masa (bloque
    # "columna_valiente", marcador_columna_valiente.json). Usa el bloque
    # sorpresa_nombrada: corre despues.
    "columna_valiente.py",
    "publicar_optimizador_boleto.py",

    # --- Premios ---
    "calcular_premios.py",

    # --- Control de calidad ---
    "calibrar_probabilidades.py",
    "evaluar_valor_senales.py",
    "diagnostico_sistema.py",
    "control_calidad_actualizacion.py",
    "normalizar_diagnostico_control.py",
    "normalizar_textos_generados.py",

    # --- Cierre final: web y publicacion ---
    "ajustar_aprendizaje_elige8.py",
    "aplicar_elige8_seguro.py",
    # Elige 8 EV (26/11/2026, punto 5 del informe): calculadora informativa
    # (P(8/8), coste, break-even, premio esperado condicionado a la jornada,
    # reglas 'mas probables' / 'edge' / 'triples dentro'); la bandera
    # 'recomendado' no se despliega (backtest NO_DESPLEGAR). Lee elige8_seguro.
    "elige8_ev.py",
    "construir_memoria_historica_profunda.py",
    "limpiar_prediccion_bloqueada.py",
    "seleccionar_pleno15.py",
    # El snapshot y el backtesting se congelan DESPUES de calibrar,
    # aplicar Elige8 y elegir el Pleno al 15 -antes se congelaban justo
    # despues del motor, asi que la "precision pre-cierre" media un boleto
    # que no era el finalmente publicado (auditoria 01/09/2026). Calibrar
    # lee snapshots de ciclos ANTERIORES, asi que moverlos aqui no le
    # afecta.
    "guardar_snapshot_prediccion.py",
    "backtesting_pre_cierre.py",
    # Congela la prediccion ENTERA de la jornada EN JUEGO desde el snapshot
    # pre-cierre (decision de Marc 26/11/2026): Losilla pasa a la jornada
    # siguiente al arrancar la actual, el motor se queda sin mercado y
    # reescribia probabilidades y bloques; desde aqui solo cambian los
    # resultados. Va DESPUES del refresco del snapshot y de Elige 8/pleno.
    "congelar_bloques_sombra.py",
    "validar_publicacion_autonoma.py",
]

# Auditoria 26/11/2026 (hallazgos 167, 217, 222): SCRIPTS_NO_CRITICOS_RED era
# una lista escrita a mano que nadie consultaba (tenia un duplicado, un script
# que no existe y le faltaban 17 activos). Ahora se DERIVA de la regla real:
# no critico = cualquier paso que ejecutar_script no trata como critico. Asi
# la pertenencia al conjunto dice la verdad y no puede desincronizarse.
SCRIPT_PRETEMPORADA_PLANTILLA = "preparar_temporada_{inicio}_{fin}.py"
SCRIPTS_NO_CRITICOS_RED = frozenset(
    s for s in SCRIPTS_ACTIVOS if s not in SCRIPTS_CRITICOS_PREDICCION
)


def es_critico(nombre):
    """Unica regla de criticidad: la que aplica ejecutar_script."""
    return nombre in SCRIPTS_CRITICOS_PREDICCION


def hoy_utc():
    return datetime.now(timezone.utc).date()


def anio_inicio_temporada(hoy=None):
    """Anio en que EMPIEZA la temporada a la que pertenece `hoy` (corte 1/7)."""
    hoy = hoy or hoy_utc()
    return hoy.year if hoy.month >= 7 else hoy.year - 1


def etiqueta_temporada(hoy=None):
    inicio = anio_inicio_temporada(hoy)
    return f"{inicio}/{inicio + 1}"


def _fecha_primer_partido(datos):
    """Fecha real del primer partido de una jornada (None si no se sabe)."""
    try:
        from cronologia_jornadas import fecha_real_jornada
        return fecha_real_jornada(datos)
    except Exception:
        return None


def temporada_ya_iniciada(hoy=None):
    """Comprueba si ya hay resultados reales de la jornada 1 de la temporada
    nueva -antes esto se decidia solo por el mes (julio/agosto = pretemporada
    siempre), pero LaLiga arranca DENTRO de agosto, asi que ese gatillo
    seguia reiniciando la clasificacion a 0 cada ciclo del pipeline incluso
    con partidos ya jugados y cerrados (ej. Alaves 3-0 Getafe el 15/08).

    Auditoria 26/11/2026 (hallazgos 117 y 138): jornada_1.json no identifica
    una temporada por si sola (la numeracion se reinicia cada agosto). En
    julio de 2027 ese fichero seguira teniendo los resultados de la J1 de
    agosto de 2026 y la pretemporada no se detectaria nunca. Ahora se mira la
    FECHA REAL de esa J1: solo cuenta si es de la temporada en curso (primer
    partido el 1 de julio o despues). Si la J1 no trae fecha se mantiene el
    comportamiento prudente de antes (no se reinicia nada)."""
    jornada1 = ROOT / "data" / "jornadas" / "jornada_1.json"
    if not jornada1.exists():
        return False
    try:
        datos = json.loads(jornada1.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not isinstance(datos, dict):
        return False
    con_resultados = any(
        p.get("resultado") not in (None, "", "Pendiente")
        for p in datos.get("partidos", [])
        if isinstance(p, dict)
    )
    if not con_resultados:
        return False
    fecha_j1 = _fecha_primer_partido(datos)
    if fecha_j1 is None:
        return True
    return fecha_j1 >= date(anio_inicio_temporada(hoy), 7, 1)


def script_pretemporada(hoy=None):
    inicio = anio_inicio_temporada(hoy)
    return SCRIPT_PRETEMPORADA_PLANTILLA.format(inicio=inicio, fin=inicio + 1)


def aviso_visible(mensaje):
    """AVISO en el log y, en GitHub Actions, anotacion visible en la ejecucion
    (hallazgos 122 y 139: las alarmas iban a un log que nadie lee)."""
    print(f"AVISO: {mensaje}")
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::warning title=Quiniela IA::{mensaje}")


def gestionar_mercado_y_temporada(hoy=None):
    hoy = hoy or hoy_utc()
    temporada = etiqueta_temporada(hoy)
    if hoy.month in {7, 8} and not temporada_ya_iniciada(hoy):
        # El script de preparacion lleva la temporada en el nombre y en sus
        # datos (equipos, TEMPORADA). Nunca se ejecuta el de otra temporada:
        # reiniciaria la clasificacion con los equipos equivocados.
        script = script_pretemporada(hoy)
        print(f"Pretemporada detectada: preparar temporada {temporada} ({script}).")
        if not (ROOT / script).exists():
            aviso_visible(
                f"Pretemporada {temporada} detectada pero falta {script}: "
                "no se prepara la temporada nueva. Hay que crear ese script."
            )
            registrar_resultado_script(script, False)
            return False
        return ejecutar_script(script)
    print(f"Temporada {temporada} en marcha o mercado cerrado: flujo normal.")
    return True


def cargar_historial_fallos():
    if not HISTORIAL_FALLOS.exists():
        return {}
    try:
        return json.loads(HISTORIAL_FALLOS.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def guardar_historial_fallos(historial):
    HISTORIAL_FALLOS.parent.mkdir(parents=True, exist_ok=True)
    HISTORIAL_FALLOS.write_text(
        json.dumps(historial, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def registrar_resultado_script(nombre, exito):
    """Lleva la cuenta de fallos consecutivos por script no critico.

    No cambia la tolerancia existente (los no criticos siguen sin bloquear
    el pipeline); solo hace ruidoso en el log un fallo que lleva varias
    ejecuciones seguidas repitiendose, que hasta ahora quedaba invisible
    detras del AVISO normal.
    """
    historial = cargar_historial_fallos()
    if exito:
        if nombre in historial:
            del historial[nombre]
            guardar_historial_fallos(historial)
        return

    entrada = historial.get(nombre, {"fallos_consecutivos": 0})
    entrada["fallos_consecutivos"] = entrada.get("fallos_consecutivos", 0) + 1
    entrada["ultimo_fallo"] = datetime.now(timezone.utc).isoformat()
    historial[nombre] = entrada
    guardar_historial_fallos(historial)
    if entrada["fallos_consecutivos"] >= UMBRAL_FALLO_CRONICO:
        print(
            f"ALERTA_FALLO_CRONICO: {nombre} lleva {entrada['fallos_consecutivos']} "
            "ejecuciones seguidas fallando. Revisar cuanto antes."
        )
        if os.environ.get("GITHUB_ACTIONS"):
            print(
                f"::warning title=Fallo cronico::{nombre} lleva "
                f"{entrada['fallos_consecutivos']} ejecuciones seguidas fallando."
            )


def jornada_en_juego():
    """True si la jornada de la prediccion publicada ya ha empezado y no ha
    cerrado. Si no se puede saber, se responde True (lo prudente es NO
    publicar una prediccion que quiza deberia estar congelada)."""
    try:
        import validar_publicacion_autonoma as vpa
        pred = vpa.cargar_json(vpa.PREDICCIONES / "ultima_prediccion.json", {})
        return bool(vpa.estado_congelacion(pred).get("en_juego"))
    except Exception as exc:
        print(f"AVISO: no se pudo comprobar si la jornada esta en juego: {exc}")
        return True


def _fallo_script(nombre, mensaje, exc=None):
    """Trata el fallo de un paso segun la UNICA regla de criticidad.

    Auditoria 26/11/2026 (hallazgo 112): congelar_bloques_sombra.py es
    critico SOLO con la jornada en juego. Si falla entonces, lo que quedaria
    publicado es la prediccion sin mercado que el motor acaba de reescribir
    (justo lo que congelar deshace): se detiene el ciclo y no se publica."""
    if es_critico(nombre):
        raise ErrorCriticoPrediccion(
            f"Error critico de prediccion en {nombre}: {mensaje}."
        ) from exc
    print(f"AVISO: {nombre}: {mensaje}; se continua.")
    registrar_resultado_script(nombre, False)
    if nombre == SCRIPT_CONGELAR and jornada_en_juego():
        raise ErrorCriticoPrediccion(
            f"{nombre} ha fallado ({mensaje}) con la jornada en juego: "
            "no se publica una prediccion sin congelar."
        ) from exc
    return False


def ejecutar_script(nombre):
    ruta = ROOT / nombre
    if not ruta.exists():
        return _fallo_script(nombre, f"falta el script activo {nombre}")

    print(f"\n=== Ejecutando {nombre} ===")
    limite = timeout_script_seg()
    try:
        subprocess.run([sys.executable, str(ruta)], cwd=ROOT, check=True, timeout=limite)
    except subprocess.CalledProcessError as exc:
        return _fallo_script(nombre, f"termino con codigo {exc.returncode}", exc)
    except subprocess.TimeoutExpired as exc:
        return _fallo_script(nombre, f"supero el limite de {limite} s y se ha cortado", exc)
    except Exception as exc:
        traceback.print_exc()
        return _fallo_script(nombre, f"excepcion {type(exc).__name__}: {exc}", exc)
    registrar_resultado_script(nombre, True)
    return True


def ejecutar_sistema():
    gestionar_mercado_y_temporada()
    for script in SCRIPTS_ACTIVOS:
        ejecutar_script(script)
    print("\nActualizacion completa; cualquier fallo no critico queda avisado en el log.")


def main():
    try:
        ejecutar_sistema()
    except ErrorCriticoPrediccion:
        print("ERROR_CRITICO_PREDICCION: se detiene por validacion de prediccion.")
        traceback.print_exc()
        raise
    except Exception as exc:
        print("AVISO_GLOBAL_ACTUALIZACION: excepcion no critica capturada en actualizar_todo.py")
        print(f"Tipo: {type(exc).__name__}")
        print(f"Detalle: {exc}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
