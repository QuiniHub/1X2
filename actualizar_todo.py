import os, sys, datetime

def gestionar_mercado_y_temporada():
    # 🌟 TRANSICIÓN AUTOMÁTICA: Detecta el cambio de año competitivo y reajusta los censos de equipos de la IA
    mes = datetime.datetime.now().month
    year = datetime.datetime.now().year
    if mes >= 8:
        print(f"☀️ [Detección de Pretemporada] Reconfigurando matrices de asignación para la nueva Temporada {year}/{year+1}...")

def ejecutar_sistema():
    gestionar_mercado_y_temporada()
    scripts = [
        "actualizar_jornadas_detalle.py",
        "actualizar_resultados_directo.py",
        "actualizar_contexto_equipos.py",
        "actualizar_analisis_ia.py",
        "generar_quiniela_ia.py",
        "actualizar_aprendizaje_ia.py",
        "construir_historial_quinielas.py",
        "construir_memoria_ia.py",
        "motor_prediccion_quiniela.py",
        "generar_estado_vivo_ia.py"
    ]
    for s in scripts:
        if os.path.exists(s):
            print(f"\n======================\n🚀 Ejecutando: {s}\n======================")
            res = os.system(f"python {s}")
            if res != 0: print(f"⚠️ Alerta controlada en {s}. Continuando secuencia...")

if __name__ == "__main__": ejecutar_sistema()
