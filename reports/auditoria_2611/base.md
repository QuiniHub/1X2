# Auditoria 26/11 - paquete "base comun"

## Que se ha hecho

- `cronologia_jornadas.py` (NUEVO): modulo comun, solo lectura de `data/`, sin red,
  sin escritura y sin reloj del sistema (`hoy` es siempre un parametro opcional).
- `tests/test_cronologia_jornadas.py` (NUEVO): 61 tests (fixtures temporales + datos reales).
  `python -m unittest tests.test_cronologia_jornadas` -> OK.

No se ha tocado ningun otro fichero ni ningun dato. No cambia ningun numero de la
prediccion ni del boleto: el modulo todavia no lo importa nadie; lo cambiaran los
equipos que sustituyan sus `max(numero)` / `sorted(por numero)` por estas funciones.

## API

| Funcion | Devuelve |
|---|---|
| `parsear_fecha(texto, anio_por_defecto=None)` | `date` o `None`. ISO, `dd/mm/yyyy`, `d/m/yyyy,`, `La Quiniela Domingo, 14 de diciembre de 2025`, `13 de Mayo` (sin anio -> `None` salvo `anio_por_defecto`), mojibake |
| `fecha_real_jornada(datos)` / `fecha_fin_jornada(datos)` | fecha del primer / ultimo partido; si no hay, la de la cabecera |
| `temporada_de_fecha(fecha, numero=None)` | `'2026_2027'`; corte 12 de agosto, y el numero desambigua julio/agosto |
| `clave_jornada(numero, fecha)` | `(temporada, numero)` |
| `jornada_cerrada(datos)` | 14 signos oficiales validos |
| `indice_jornadas(dir_jornadas=None)` | lista de `{numero, fecha, temporada, cerrada, ruta, fecha_fin, estado}` en orden cronologico |
| `jornadas_cronologicas(solo_cerradas=False, temporada=None, dir_jornadas=None)` | el indice filtrado |
| `ultima_jornada_cerrada(hoy=None, temporada=None, dir_jornadas=None)` | la cerrada mas reciente por fecha |
| `jornada_en_curso_o_proxima(hoy=None, temporada=None, dir_jornadas=None)` | la primera no cerrada por fecha |
| `cargar_jornada(numero, dir_jornadas=None)` | el dict de `jornada_N.json` o `None` |
| `misma_jornada(a, b)` / `mismo_equipo(a, b)` / `normalizar_equipo(n)` | comparacion por equipos |
| `snapshot_del_cierre(numero, ...)` / `prediccion_del_cierre(numero, dir_snapshots=None, dir_jornadas=None)` | la foto pre-cierre solo si es de la misma jornada real |

## Comprobado contra los datos reales (27/11/2026)

- 76 ficheros `jornada_N.json`, los 76 con fecha. Orden cronologico estricto:
  J28 (14/12/2025) ... J76 (07/08/2026), J1 (15/08/2026) ... J27 (05/12/2026).
- J1-J27 -> `2026_2027`; J28-J76 -> `2025_2026`.
- Ultima cerrada: J24. En curso o proxima: J25. Con `hoy=2026-08-10` la ultima cerrada es la J76.
- `prediccion_del_cierre(24)` devuelve la foto generada el 2026-11-24 15:02 UTC
  (primer partido 20:00 UTC).
- Los 36 snapshots de `data/backtesting/pre_cierre` se reconocen como de su jornada.
- Ninguna pareja de jornadas reales distintas comparte 3 o mas partidos (umbral de
  `misma_jornada`: 7 partidos y la mitad).

## Decisiones que conviene conocer

1. **Primer partido = el mas temprano**, no el `num` 1. En J6, J26, J74 y J75 el partido 1
   no es el primero que se juega (J26: partido 1 el 02/12, pero hay partidos el 01/12).
2. **Fecha de partido a mas de 10 dias de la cabecera se ignora** (errata de anio).
3. **Agosto**: sin numero, del 1 al 11 de agosto es temporada vieja. Con numero,
   en julio/agosto `numero <= 15` es temporada nueva y `numero >= 40` es la vieja.
4. **`cerrada` = 14 signos validos**, no el campo `estado` (J28-J60 no tienen `estado`).
5. **`jornada_en_curso_o_proxima(hoy)`** salta las abiertas cuyo ultimo partido fue hace
   mas de 3 dias; sin `hoy` devuelve la primera abierta posterior a la ultima cerrada.
6. **`prediccion_del_cierre`** devuelve `None` si no existe `jornada_N.json` (no se puede
   comprobar). Acepta el snapshot si coinciden los equipos o, si no, si
   `primer_partido_utc` cae a 2 dias o menos de la fecha real.

## Avisos para los demas equipos

- Las fechas de J28-J63 son la del dia de la jornada (domingo), no la del primer partido:
  esos ficheros no traen fecha por partido. El orden sigue siendo correcto.
- Cuando la 26/27 llegue a J28 el pipeline pisara `jornada_28.json`. Los tests de datos
  reales estan anclados a fechas, no a numeros, para no romperse ese dia.
- Los tres primeros dias tras una jornada, si no se ha cerrado, `jornada_en_curso_o_proxima(hoy)`
  la sigue devolviendo; quien necesite "la siguiente a jugar" debe mirar tambien `fecha`.
