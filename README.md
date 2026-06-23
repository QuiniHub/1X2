# Quiniela IA Pro

Web y motor de analisis para La Quiniela. El flujo activo se centra en datos reales de jornadas, resultados, clasificaciones, memoria de quinielas jugadas, contexto competitivo y prediccion.

## Flujo activo

El workflow real esta en:

`.github/workflows/main.yml`

Ese workflow ejecuta:

`python actualizar_todo.py`

`actualizar_todo.py` solo llama a scripts activos y falla si uno de ellos falla. Asi se evitan actualizaciones silenciosas con datos incompletos.

Las dependencias Python estan fijadas en:

`requirements.txt`

Antes de actualizar datos en GitHub Actions se ejecuta:

`python -m unittest discover -s tests`

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
- `modelo_metricas_1x2.py`
- `motor_prediccion_quiniela.py`
- `generar_estado_vivo_ia.py`
- `guardar_snapshot_prediccion.py`
- `backtesting_pre_cierre.py`
- `diagnostico_sistema.py`

## Capa predictiva entrenable

`modelo_metricas_1x2.py` aporta una primera capa profesional y auditable de prediccion 1X2:

- construye un dataset temporal desde jornadas cerradas;
- calcula un baseline Elo/Poisson;
- entrena un modelo 1X2 si `scikit-learn` esta disponible y la muestra es suficiente;
- ejecuta backtesting rolling sin mirar el futuro;
- publica Brier Score, Log Loss, curva de calibracion, acierto top1 y metricas por competicion/signo;
- versiona salidas en `data/modelo_predictivo/`.

Si `scikit-learn` no esta instalado, el pipeline no rompe la actualizacion: degrada a baseline Elo/Poisson y deja constancia en `metricas_modelo.json`.

## Datos profesionales vivos

`actualizar_datos_profesionales.py` crea y mantiene `data/datos_profesionales.json`.

La capa acepta un JSON normalizado desde GitHub Secrets:

- `QUINIHUB_PRO_DATA_URL`: endpoint autorizado con cuotas 1X2, bajas/sanciones, alineaciones probables, calendario y clasificaciones.
- `QUINIHUB_PRO_DATA_TOKEN`: token bearer opcional para ese endpoint.

Tambien puede conectarse directamente a API-Football/API-SPORTS:

- `QUINIHUB_PRO_DATA_URL=https://v3.football.api-sports.io`
- `QUINIHUB_PRO_DATA_TOKEN=<clave API-Football>`

Variables opcionales de GitHub Actions `vars`:

- `QUINIHUB_PRO_DATA_PROVIDER=api_football`
- `QUINIHUB_PRO_DATA_LEAGUES=140:LaLiga EA Sports,141:LaLiga Hypermotion,1:FIFA World Cup`
- `QUINIHUB_PRO_DATA_SEASON=2026`
- `QUINIHUB_PRO_DATA_TIMEZONE=Europe/Madrid`
- `QUINIHUB_PRO_DATA_BOOKMAKER=<id bookmaker>`
- `QUINIHUB_PRO_DATA_MAX_JORNADAS=2`

Si esos secretos no existen, el workflow no falla: conserva un esqueleto auditable y marca las fuentes como pendientes. Cuando el endpoint este configurado, `motor_prediccion_quiniela.py` mezcla las cuotas de mercado con su probabilidad propia, penaliza bajas/sanciones estructuradas, sube riesgo si el once probable es dudoso y deja trazabilidad por partido.

El formato esperado por partido es:

```json
{
  "jornada": 1,
  "num": 1,
  "local": "Equipo Local",
  "visitante": "Equipo Visitante",
  "cuotas": {"1": 1.8, "X": 3.4, "2": 4.8, "fuente": "proveedor"},
  "bajas": {
    "local": {"lesiones": [{"jugador": "Nombre", "impacto": 2.0, "titular": true}], "sanciones": [], "dudas": []},
    "visitante": {"lesiones": [], "sanciones": [], "dudas": []}
  },
  "alineaciones": {
    "local": {"titulares_probables": ["Jugador 1"], "confianza": 0.8},
    "visitante": {"titulares_probables": ["Jugador 1"], "confianza": 0.8}
  },
  "calendario": {"fecha": "2026-08-16", "hora": "21:00", "temporada": "2026/2027", "fuente": "oficial"},
  "clasificacion": {"temporada": "2026/2027", "local": {"posicion": 4, "puntos": 18}, "visitante": {"posicion": 14, "puntos": 9}}
}
```

## Prediccion y backtesting

Cuando no se pasan dobles/triples manuales, `motor_prediccion_quiniela.py` aplica cobertura automatica segun incertidumbre, margen de probabilidad, empate alto, sorpresa y necesidad competitiva. Esto evita publicar por defecto 14 fijos en jornadas abiertas.

`guardar_snapshot_prediccion.py` guarda una foto pre-cierre de la prediccion solo si la jornada aun no tiene resultados oficiales. No sobrescribe snapshots existentes.

`backtesting_pre_cierre.py` compara solo esas fotos pre-cierre contra resultados reales, para no mezclar predicciones regeneradas despues de jugarse la jornada.

## Memoria de quinielas jugadas

La memoria persistente debe estar en:

- `data/quinielas_jugadas.json`
- `data/historial_quinielas.json`

Una jugada guardada solo en el navegador no entra en el aprendizaje automatico hasta que quede persistida en esos archivos.
Las quinielas manuales cargadas en Historial cuentan igual que las generadas en Quinielas cuando `data/historial_quinielas.json` contiene `nuestra_quiniela`.

## Limpieza aplicada

Se han retirado demos, duplicados y conectores antiguos que generaban datos inventados, tenian nombres cruzados o podian pisar informacion buena. El motor valido de prediccion es `motor_prediccion_quiniela.py`; `generar_quiniela_ia.py` queda solo como compatibilidad y delega en ese motor.
