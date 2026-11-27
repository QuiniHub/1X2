# Auditoria 26/11 - paquete P9 (tests y documentacion)

Ningun cambio de este paquete toca numeros de la prediccion ni del boleto: solo
tests, documentacion, el skill y `requirements.txt`.

## Arreglado

| Hallazgo | Que se hizo | Test |
|---|---|---|
| 106 (tests con datos vivos) | `test_revulsivo`: el caso real Racing-Valencia ya no lee `ceses_actuales.json` ni los calendarios del repo; usa una copia fija en un directorio temporal y fija los efectos del estudio. `test_senal_valiente`: el estudio del Madrid es una foto fija y el backtest que incrusta el bloque sale de un fixture. | `tests.test_revulsivo`, `tests.test_senal_valiente` |
| 206 (NaN e Infinity) | `test_datos_web_validos` valida como `JSON.parse`: rechaza NaN, Infinity y -Infinity, recorre tambien las subcarpetas de `data/` y comprueba que toda ruta fija de `getJson` cae en una carpeta validada. | `tests.test_datos_web_validos` |
| 207 (test tautologico) | El test de orden cronologico llama ahora a `control_calidad_actualizacion.jornadas_estado()` y a `diagnostico_sistema.diagnosticar_jornadas()` sobre un directorio temporal con J76 (agosto) y J4 (septiembre). Comprobado que falla si se ordena por numero. | `tests.test_auditoria_reparaciones` |
| 208 y 251 (`unittest.main()` a mitad) | Movido al final en 8 de los 9 ficheros. | ejecutar el fichero suelto da el mismo numero de tests que con `-m unittest` |
| 110 y 211 (skill) | `/analizar-jornada` reescrito al metodo vigente: mercado manda (0,85), prediccion congelada al cierre, jornada por fecha con `cronologia_jornadas`, optimizador como base, tabla de rachas en casa y fuera, sorpresas nombradas y cubrir lo nombrado, protocolo de bote, Elige 8 como calculadora, presentacion "futbol primero". | `tests.test_aud_P9_skill_analizar_jornada` |
| 212 (README y brief) | README: dependencias reales (con scipy, sin pandas), Liga 26/27 en juego, criterio real del Elige 8, 78 scripts, mercado 0,85, congelado y jornadas por fecha. Brief: nota de vigencia, Gemini, Malmoe, fecha de arranque y seccion "Que ha cambiado desde agosto". | `tests.test_aud_P9_requirements` (README frente a requirements) |
| 213 (requirements) | Fuera pandas; minimos y tope de version mayor, sin versiones exactas. | `tests.test_aud_P9_requirements` |
| 241 (estudio sin tests) | 9 tests nuevos: `extraer_candidatas`, lectura de mercado pre-cierre y de masa LAE en directorio temporal, y dos de ausencia de fuga de futuro en las rachas. | `tests.test_estudio_ver_sorpresas` |
| 252 (multicolumna) | 7 tests nuevos que si llaman a `calcular_premio_multicolumna` con la tabla real de la J70. | `tests.test_aud_P9_premios_multicolumna` |

Ademas: `MarcadorValienteTests` (en `test_senal_valiente.py`, fichero de este
paquete) fallaba porque otro equipo cambio `actualizar_marcador_valiente` para
leer del snapshot pre-cierre. Se adaptaron los fixtures a la nueva lectura y se
anadieron dos tests (sin snapshot no se registra; la temporada sale de la fecha).

## No arreglado

- **208/251, `tests/test_motor_prediccion.py`**: sigue con `unittest.main()` en
  la linea 930 y tres clases detras. Es de otro paquete.
- **197 y 210 (tests de frontend que solo buscan cadenas, sin test de XSS)**:
  aplazado. Probar `calculateCost` o el escapado de verdad exige ejecutar el
  JavaScript, y no hay Node en este PC ni se pueden anadir dependencias. Un test
  estatico de `innerHTML` por expresiones regulares no distingue las plantillas
  HTML de los textos del chat (44 interpolaciones dudosas, la mayoria del prompt)
  y `index.html` lo esta editando otro equipo.
- **205** (`test_jornada_objetivo_quiniela` con fecha local frente a UTC) y
  **209/253** (`test_radar_tormenta` escribe en `data/`): ficheros de otros paquetes.
- **107** (21 scripts sin test): los modulos son de otros paquetes; de la lista
  propuesta solo se cubre aqui lo de los hallazgos 241 y 252.
- **106, resto**: `test_publicar_optimizador_boleto`, `test_elige8_modos`,
  `test_jornada_activa`, `test_control_calidad_actualizacion`,
  `test_modelo_metricas_1x2`, `test_optimizador_ev_premio`, `test_ranker_favoritos`,
  `test_sorpresa_nombrada` y `test_tercero_valor` siguen leyendo datos vivos:
  no son de este paquete.
- **207, parte de `test_construir_memoria_ia.py`**: fichero de otro paquete.
- **215** (`.claude/launch.json` versionado con ruta local): solo informe. Sigue
  en el repo con la ruta `C:/Users/marcr/...`.
- **254** (el informe del 26/11 confunde el 0,7 de Dixon-Coles con el peso del
  mercado): ese informe no es de este paquete. La aclaracion queda escrita en el
  brief ("Que ha cambiado desde agosto").

## Pendiente para otros

- `.github/workflows/main.yml` linea 48 sigue instalando a mano
  `requests beautifulsoup4 lxml joblib numpy pandas scikit-learn` despues de
  `requirements.txt`: instala pandas, que no se usa, y es redundante. Conviene borrarla.
- `.github/workflows/main.yml`, paso "Comprobar el boleto recien generado":
  anadir `tests.test_datos_web_validos` a la lista. Con `QUINIELA_POST_PIPELINE=1`
  ese modulo hace el barrido completo de NaN/Infinity sobre `data/`, y un fallo
  impide el commit del ciclo que lo genera. Mientras no se anada, el barrido
  completo solo corre en local y en `ci-pr.yml` (lo que la web carga se sigue
  validando en todos los ciclos).
- El brief decia que Gemini estaba desactivado; el codigo lo llama. Si la clave
  funciona o no, no se puede saber desde el repo.

## Segunda pasada (tras la revision)

- **Tests que podian parar el cron.** `main.yml` ejecuta toda la carpeta `tests`
  antes del pipeline. Ahora, cuando `GITHUB_EVENT_NAME` es `schedule` o
  `workflow_dispatch`, se saltan: el barrido de NaN sobre todo `data/` y el test
  de rutas `getJson` (salvo con `QUINIELA_POST_PIPELINE=1`), y los tests
  documentales (`test_aud_P9_skill_analizar_jornada`, y `RequirementsTests` de
  `test_aud_P9_requirements`). Siguen corriendo en local y en `ci-pr.yml`. La
  validacion estricta de las carpetas que la web carga corre siempre.
- **Peso del mercado.** El test del skill ya no exige el literal 0.85: lee
  `PESO_MERCADO_MANDA` del motor y pide que el skill cite ese mismo numero. Si
  Marc cambia el peso, el test falla en local o en PR con un mensaje que dice
  que fichero actualizar, y nunca en el cron.
- **Rutas en plantilla.** El test de rutas `getJson` comprueba tambien la carpeta
  de las rutas en plantilla (`data/jornadas/jornada_${n}.json`). Al integrar,
  volver a ejecutar `tests.test_datos_web_validos` con el `index.html` final.
- **Lecturas de datos vivos que quedan en ficheros de este paquete (106).**
  `test_senal_valiente.py` (`test_experimento_v2_documentado_en_el_backtest` y
  `test_backtest_prerregistrado_documentado`) lee
  `data/memoria_ia/backtest_valiente.json`: comprueban que ese fichero versionado
  documenta el experimento, y solo cambia al relanzar el backtest a mano.
  `test_auditoria_reparaciones.py` (smoke de `predecir()` y
  `PrioridadesExportadasTests`) lee `data/estado_jornada_objetivo.json` y los
  datos reales a proposito: es un smoke del boleto que se publicaria. No se han
  convertido en fixtures.
- **Brief.** Aclarado: primer partido de LaLiga 26/27 el 15/08/2026; la jornada 1
  de La Quiniela lleva fecha del domingo 16.
