# Quiniela IA Pro

Web y motor de analisis para La Quiniela. El flujo activo se centra en datos reales de jornadas, resultados, clasificaciones, memoria de quinielas jugadas, contexto competitivo y prediccion.

## Flujo activo

El workflow real esta en:

`.github/workflows/main.yml`

Ese workflow ejecuta:

`python actualizar_todo.py`

`actualizar_todo.py` solo llama a scripts activos y falla si uno de ellos falla. Asi se evitan actualizaciones silenciosas con datos incompletos.

## Scripts activos

- `actualizar_jornadas_detalle.py`
- `actualizar_resultados_directo.py`
- `aplicar_correcciones_resultados.py`
- `actualizar_clasificaciones_oficiales.py`
- `actualizar_contexto_equipos.py`
- `actualizar_analisis_ia.py`
- `actualizar_aprendizaje_ia.py`
- `construir_historial_quinielas.py`
- `construir_memoria_ia.py`
- `generar_contexto_competitivo.py`
- `motor_prediccion_quiniela.py`
- `generar_estado_vivo_ia.py`
- `diagnostico_sistema.py`

## Memoria de quinielas jugadas

La memoria persistente debe estar en:

- `data/quinielas_jugadas.json`
- `data/historial_quinielas.json`

Una jugada guardada solo en el navegador no entra en el aprendizaje automatico hasta que quede persistida en esos archivos.

## Limpieza aplicada

Se han retirado demos, duplicados y conectores antiguos que generaban datos inventados, tenian nombres cruzados o podian pisar informacion buena. El motor valido de prediccion es `motor_prediccion_quiniela.py`; `generar_quiniela_ia.py` queda solo como compatibilidad y delega en ese motor.
