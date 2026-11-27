# Auditoria 26/11 - paquete P6_fuentes

Estado: codigo y tests terminados. Sin acceso a red: todo probado con datos
sinteticos; ningun arreglo se ha visto funcionar contra las fuentes reales.

Tests del paquete (94 OK junto con test_datos_profesionales; 251 OK con todos
los tests que importan modulos del paquete):

- tests/test_aud_P6_fuentes_google_losilla.py
- tests/test_aud_P6_fuentes_cronologia.py
- tests/test_aud_P6_fuentes_conservar.py
- tests/test_jornada_objetivo_quiniela.py (ya existia)

Falla 1 test ajeno: tests.test_fuente_losilla_por_jornada
(test_mercado_de_la_misma_jornada_se_usa). Prueba motor_prediccion_quiniela
(paquete del motor), no modulos de P6.

## Arreglado

| Indices | Que |
|---|---|
| 6, 126 | buscar_resultados_google: sin variante de primera palabra, palabra completa, solo partidos en fechas del Mundial, la URL debe nombrar a los dos equipos, sin candidatos no hay red. Borradas de data/mundial_2026_resultados.json las 2 entradas de clubes (Racing 2-0 R. Sociedad falso y Levante 4-2 Athletic). sincronizar_resultados_jornada ignora 'confirmados' con fecha fuera del Mundial. |
| 8 | Losilla: fusionar_probabilidades / fusionar_cuotas solo fusionan si es la misma jornada y los mismos equipos. |
| 34, 63 | cargar_historico_ligas_espana y cargar_historico_quinielas_lae conservan el dato previo si falla la descarga y nunca guardan menos de lo que habia; las temporadas cerradas de La Quiniela se leen de cache (antes ~225 POST por ciclo). |
| 54 | resultados_libres: con 0 partidos no pisa el fichero y deja aviso y contador de ciclos; prorroga/penaltis no cuentan como final; formato plano de OpenFootball. |
| 55, 132, 143 | Respaldo Libertad Digital: proximas jornadas por fecha (28-30, no 77-79). |
| 142, 168 | asegurar_proxima_jornada decide por fecha y temporada; un fichero del mismo numero de otra temporada no bloquea. |
| 76, 144 | actualizar_boleto_vivo.jornada_objetivo: respaldo = jornada en curso por fecha, o None. |
| 87 | datos_profesionales: jornadas por fecha; error de plan corta a la primera peticion y los 7 dias siguientes hace 0 peticiones. |
| 189, 242 | temporada_objetivo(): enero-junio ya no da la temporada siguiente. |
| 56 | Correcciones: casan por equipos (y numero si lo hay), respetan 'temporada', no reescriben sin cambios, y una correccion vieja no llega al calendario cuando su jornada ya es otra. |
| 58 | Escrutinio Losilla: jornada leida del JSON, maximo 3 candidatos (antes barrido 90..1), comprobacion de monotonia de acertantes. |
| 59 | actualizar_fuente_lae: fecha en texto convertida a AAAAMMDD, combinacion aislada, jornada de la pagina debe coincidir, historial y fichero casados por fecha. |
| 60, 244 | actualizar_resultados_directo: la jornada nombrada por la fuente debe estar abierta y ser reciente, desempates por fecha, no pisa signos fijados por otra fuente, sin utcnow(). |
| 61, 125 | Liga F: User-Agent honesto de cliente automatizado (sin datos personales), no insiste tras 429 (6 h), no redescarga un dato de menos de 3 h, marca dias_sin_actualizar y dato_caducado (> 8 dias). |
| 62 | Temporada derivada de la fecha en resultados_libres, liga_f y cargar_historico_quinielas_lae. |
| 100 | boleto vivo no reescribe el nombre canonico cuando es el mismo cruce con otra grafia; alias nuevos en resolver_competiciones. |
| 86 (parte), 113, 188 | resolver_competiciones: no reetiqueta jornadas de otra temporada, no toca espejos cerrados/congelados, solo guarda si cambia algo ademas de generado_en. |
| 171 | detalles: campo prob_tecnicos (prob_lae se mantiene por compatibilidad). |
| 172 | clasificaciones: validado_en ya no se resella si no se pudo refrescar; correccion Leganes-Huesca limitada a 25/26. |
| 191, 227 | Monitor de temporadas: los indicios de laliga.com solo cuentan desde el 15 de junio del anio de inicio. |
| 193 (parte) | preparar_temporada: canonico() reconoce Real Madrid y Real Sociedad. |
| 204 | ultima_jornada_aprendida: el respaldo ya no devuelve max(numero); test con reloj fijo. |
| 219 | actualizar_detalles_partidos usa la jornada objetivo. |
| 248 | resultados_apis y Losilla no sobrescriben si el fichero previo existe pero no se puede leer. |

## Pendiente de decision de Marc

- **57** Losilla 'probabilidad' = media de 4 tablas; 2 son masa (lae,
  quinielista). Solo documentado. J25: diferencia maxima por partido entre
  tecnicos+real y masa = 13,5 puntos de media, 32,5 de maximo.
  Ejemplos (1/X/2): Betis-Rayo 62/22/16 frente a masa 80/14/6 (publicada
  70,5/18,25/11,25); Las Palmas-Andorra 42/28/30 frente a 74/16/10
  (publicada 58,25/21,75/20); Granada-Ceuta 59/24/18 frente a 85/10/6
  (publicada 72/16,5/11,5).
- **86 (resto)** Categoria propia para Champions/Europa/Copa: modelo_metricas
  usa la competicion como variable con una lista cerrada; es modelado.
- **61 (resto)** User-Agent de navegador en los demas fetchers del paquete
  (Losilla, quiniela15/dondeverlo, quinielafutbol, AS, webprincipal). No se ha
  tocado: sin red no se puede comprobar que esas webs sigan respondiendo.

## No arreglado (fuera del paquete o aplazado)

- **101** Datos de data/jornadas (J1 P5, J7 P7, J12 P1) y falta de
  'jornada'/'num' en la correccion Rayo-Athletic: ficheros de otro paquete.
- **173** Retirar sincronizar_resultados_jornada / actualizar_legado del
  pipeline: actualizar_todo.py no es de este paquete.
- **203** Pleno al 15 guardado como marcador: cambiar el formato afecta a
  lectores de otros paquetes (historial, premios, web).
- **228** Ficheros de diagnostico sin lector: decision por fichero, fuera del
  paquete.
- **193 (resto)** Parametrizar preparar_temporada para 27/28.
- **62 (resto)** detectar_temporada sigue guiandose por 'Racing en Primera';
  actualizar_ligas_football_data no es de este paquete.
- **58 (resto)** Claves de escrutinio sin temporada y resellado de extraido_en.
- Carpeta data/temporadas/2027_2028 creada por el falso positivo: sigue ahi.

## Efecto en la prediccion publicada

Ninguno directo sobre los numeros de la J25. Indirecto, en el proximo ciclo:
resolver_competiciones reetiquetara 13 partidos ya cerrados (9 a
primera_division, 4 a segunda_division; todos del Racing o de la Real
Sociedad B, J1-J23) que estaban como liga_extranjera. modelo_metricas usa esa
etiqueta como variable; el efecto no se ha medido.

## Segunda pasada (27/11): problemas del revisor

Tests nuevos en tests/test_aud_P6_fuentes_revision.py (12). Con todos los
tests que importan modulos del paquete: 418 OK.

| Fichero | Que se ha hecho |
|---|---|
| actualizar_jornadas_detalle.py | main() ya no fusiona la jornada nueva con un jornada_N.json de OTRA temporada (existente_de_otra_temporada, por fecha real + temporada). Antes la J28 de 26/27 heredaba equipos en placeholders y resultados del fichero de 12/2025. El fichero viejo se archiva antes de pisarlo. |
| asegurar_proxima_jornada.py | Antes de sobrescribir un jornada_N.json de otra temporada lo copia a data/temporadas/<temporada>/jornadas/jornada_N.json (no pisa un archivo ya guardado). |
| cargar_historico_ligas_espana.py | La guardia "menos partidos que antes" compara solo las temporadas presentes en el historico nuevo: desplazar la ventana TEMPORADAS ya no congela el fichero. |
| actualizar_resultados_directo.py | Si otra fuente puso el signo SIN marcador y el signo de directo coincide, rellena solo 'resultado' (marca marcador_fuente; no toca signo ni fuente_resultado). Los partidos sin marcador ya no se pasan al calendario. |
| actualizar_fuente_losilla.py | Un fuente_losilla.json ilegible ya no para la fuente en cada ciclo: se guarda copia en fuente_losilla.json.corrupto-AAAAMMDD, se emite ::warning:: y se sigue con previo vacio. Solo se aborta si no se puede hacer la copia. |
| cargar_historico_quinielas_lae.py | Las jornadas locales de temporadas anteriores a la 25/26 se ignoran con aviso (antes se habrian mezclado por numero). |

No aplica:

- actualizar_resultados_directo.py, TypeError al ordenar por primer_inicio:
  resumen_temporal_jornada devuelve texto ISO o "" (nunca None), asi que la
  comparacion es siempre texto con texto. Queda un test que lo fija
  (dos jornadas en juego, una sin horas).

Anotado, sin cambio de codigo:

- **Clasificaciones / validar_contexto_actual** (no es de este paquete): al no
  resellar validado_en cuando la fuente falla, validar_contexto_actual.py
  (MAX_EDAD_MIN = 120) dara 'clasificacion no validada recientemente' si la
  fuente lleva mas de 2 horas caida. No bloquea la prediccion, pero saldra
  como paso fallido. Opciones: aceptarlo como aviso honesto, o que ese
  validador lea conserva_datos_previos / ultimo_intento y avise en vez de
  fallar. Decision del paquete del pipeline.
- **Liga F (61 / 125): SIN VERIFICAR CON RED.** El User-Agent nuevo es
  generico y no lleva contacto ni URL; la politica de Wikimedia pide un medio
  de contacto y puede seguir respondiendo 429/403. Antes de darlo por cerrado
  hay que lanzar una ejecucion real con --forzar. Si sigue fallando, Marc
  decide si pone en el UA la URL publica del proyecto o se cambia a la API
  REST. El fichero quedaria marcado dato_caducado, pero el motor aun no lo
  lee (la mitad del 125 que es del motor).
- **Archivo de jornadas 25/26**: el archivado crea
  data/temporadas/2025_2026/jornadas/ en el primer cambio. Si Marc prefiere
  no guardar esas copias, basta con quitar la llamada; lo que no tiene vuelta
  atras es perder el fichero.
- tests.test_fuente_losilla_por_jornada (test_mercado_de_la_misma_jornada_se_usa)
  sigue fallando: prueba motor_prediccion_quiniela, paquete del motor.
