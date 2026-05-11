import os
import sys

# ORDEN CRÍTICO CORREGIDO: Primero estructuramos la base, LUEGO raspamos los goles de internet, y AL FINAL calculamos posiciones e IA
scripts = [
    "actualizar_jornadas_detalle.py",       # 1. Crea la estructura base de la Quiniela de la semana
    "actualizar_calendario.py",             # 2. Raspa internet y mete los goles reales (NUNCA debe ser pisado)
    "actualizar_clasificaciones.py",        # 3. Lee esos goles y calcula la tabla de posiciones en tiempo real
    "actualizar_clima.py",                  # 4. Actualiza variables externas del fin de semana
    "actualizar_arbitros.py",               # 5. Vincula los colegiados asignados
    "actualizar_analisis_ia.py",            # 6. Ejecuta las predicciones con los datos frescos
    "actualizar_aprendizaje_ia.py"          # 7. Guarda la experiencia en la red neuronal
]

errores = []

print("🚀 Iniciando Orquestador Maestro de Quiniela IA Pro...")

for script in scripts:
    if not os.path.exists(script):
        print(f"⚠️ Saltando {script} porque no existe en la raíz.")
        continue

    print(f"\n==========================================")
    print(f"🔄 Ejecutando módulo: {script}...")
    print(f"==========================================")
    
    # Ejecución segura del proceso hijo
    resultado = os.system(f"python {script}")

    if resultado != 0:
        print(f"❌ Alerta: Fallo en {script}. Saltando al siguiente módulo para evitar congelar la web...")
        errores.append(script)
    else:
        print(f"✅ {script} procesado con éxito.")

print("\n==========================================")
if errores:
    print(f"⚠️ Proceso finalizado. Algunos módulos fallaron: {', '.join(errores)}")
    # Dejamos que termine en ÉXITO (0) para que GitHub Pages publique lo que sí se haya podido salvar
    sys.exit(0)
else:
    print("🚀 ¡Enhorabuena! Toda la base de datos y la web se han actualizado al unísono.")
print("==========================================")
