# Elige 8 (La Quiniela): reglas, economía del fondo, matemáticas y estrategia

Fecha de la investigación: 2026-11-25. Nota de método: las páginas de loteriasyapuestas.es (escrutinios y notas de prensa PDF) devuelven HTTP 403 al fetcher automático; sus cifras se han tomado de los fragmentos indexados por el buscador y se han cruzado con dos agregadores que replican el escrutinio oficial (eduardolosilla.es y tulotero.es). Donde una cifra viene sólo de un fragmento de búsqueda se indica.

## 1. Reglas oficiales y fracción del fondo que va a premios

### Takeaway
Elige 8 es una apuesta adicional sobre el boleto de La Quiniela (0,50 € por apuesta, mínimo total 2 €), con una única categoría (8 aciertos) a la que va el 55 % de su recaudación propia en régimen puramente pari-mutuel (reparto a partes iguales). Los dobles/triples de los 8 partidos elegidos multiplican el nº de apuestas de Elige 8 (×2 y ×3 cada uno). Si nadie acierta 8, el fondo baja a 7 aciertos (versión divulgada por SELAE/Losilla); las normas escritas que cita Losilla dicen en cambio que pasaría a la jornada siguiente; nunca hay bote en la práctica.

### Cited Findings
- SELAE (centro de ayuda): "con cada apuesta que realices, tienes la oportunidad de jugar a Elige8 por 0,50 € más, con premios para todos tus boletos que acierten los 8 partidos que elijas"; La Quiniela destina el 55 % de la recaudación a premios — [SELAE, Cómo jugar a La Quiniela](https://www.loteriasyapuestas.es/es/centro-de-ayuda/como-se-juega/como-jugar-a-la-quiniela)
- Texto de las condiciones de SELAE reproducido por el editor de casasdeapuestas.com (comentario de Pau Sisternas, 07/04/2026): "El 55 por 100 de la recaudación íntegra en esta modalidad de participación adicional se distribuirá a partes iguales entre todas las apuestas que tengan acertado el mayor número de pronósticos" (máximo 8); no existe categoría "Elige 7" como tal, pero paga un nivel inferior si nadie acierta 8; si ninguna apuesta tuviera ni un acierto, el fondo pasaría a la jornada siguiente — [casasdeapuestas.com, blog Elige8](https://www.casasdeapuestas.com/blog/elige8/)
- eduardolosilla.es: 8 de los 14 partidos combinables, el pronóstico se replica de la columna de La Quiniela; no incluye el Pleno al 15; NO disponible en Reducidas ni Condicionadas; apuesta Quiniela 0,75 €, apuesta Elige 8 0,50 €, mínimo total 2 €; el 55 % de la recaudación del Elige 8 se reparte entre los acertantes de 8 (única categoría), ejemplo: 100.000 € recaudados → 55.000 € a repartir; si no hay acertantes de 8 pasa a los de 7, luego 6, etc.; "El ELIGE8 nunca genera Bote". La misma página advierte que las normas oficiales dicen que el fondo sin acertantes "pasa a incrementar la misma categoría de la jornada siguiente" (las dos versiones no coinciden) — [eduardolosilla.es, boleto Elige8](https://www.eduardolosilla.es/quiniela/boletos/elige8)
- Losilla, ejemplo de coste multiplicado: Quiniela con 2 dobles y 1 triple = 9 €; si uno de los dobles cae entre los 8 elegidos, Elige 8 = 2 apuestas = 1 €, total 10 € — [eduardolosilla.es, boleto Elige8](https://www.eduardolosilla.es/quiniela/boletos/elige8)
- Comprobación empírica del 55 %: nota de prensa SELAE jornada del 20/09/2026: recaudación Elige8 105.613,00 €, 1.070 apuestas acertantes de 8 a 54,29 € (1.070 × 54,29 = 58.090 € = 55,0 % de 105.613 €); jornada del 9-10/09/2026: recaudación 43.559,00 €, 9.284 acertantes a 2,58 € (= 23.953 € = 55,0 %) — [SELAE nota de prensa 20/9/26](https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/NOTA_DE_PRENSA_LA_QUINIELA_20_9_26.pdf); [SELAE nota de prensa 9/09/26](https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/NOTA_DE_PRENSA_LA_QUINIELA_9_09_26.pdf) (cifras vía fragmento de búsqueda; PDF 403 al fetcher)
- El juego arrancó en la jornada del 20/10/2019 (temporada 2019/20) — [eduardolosilla.es](https://www.eduardolosilla.es/quiniela/boletos/elige8); [casasdeapuestas.com](https://www.casasdeapuestas.com/blog/elige8/)
- Normas generales de La Quiniela (documento SELAE "Normas sobre los concursos de pronósticos a partir de la temporada 2017-2018", alojado en Hacienda): precio 0,75 €/apuesta; 55 % a premios; 16 % cat. 1ª (14), 7,5 % cat. 2ª-4ª (13, 12, 11), 9 % cat. 5ª (10), 7,5 % categoría especial (Pleno al 15). Este texto es anterior a Elige 8 y NO contiene su norma — [Hacienda, 58018anexo.pdf](https://www.hacienda.gob.es/DocLeyes/REPOSITORIO%20NORMATIVA/58018anexo.pdf)
- Losilla replica el reparto por categorías con la jornada 23 (21/11/2026): recaudación 2.940.306,75 €, 15 aciertos 7,5 % + bote, 14 aciertos 16 %, 13/12/11 7,5 % cada una, 10 aciertos 9 %; 10 aciertos pasa a bote si < 1,50 € (J23: 455.229 acertantes → 0,00 €); retención 20 % > 40.000 € — [eduardolosilla.es, ayuda escrutinio](https://www.eduardolosilla.es/quiniela/ayudas/escrutinio)

### Inferences
- Al ser una sola categoría y pari-mutuel puro, el premio por acertante es exactamente 0,55 × R / N (R = recaudación Elige 8, N = apuestas con 8/8). Como cada apuesta cuesta 0,50 €, el premio también se puede escribir como 0,275 € × (nº total de apuestas) / N, es decir, el retorno de una apuesta ganadora es 0,55 / (fracción de apuestas ganadoras). La fracción de apuestas ganadoras (N / total) es el único número que importa: si gana más del 55 % de las apuestas, el premio es inferior al coste de la apuesta (0,50 €).
- La devolución teórica del juego es 55 % (igual que La Quiniela), sin bote que la infle: a diferencia de 14/15 aciertos, nunca hay traslado de fondo que haga EV+ a toda la masa. El EV+ sólo puede venir de acertar con más frecuencia que la masa o de estar en combinaciones poco jugadas.
- Que Losilla señale la contradicción entre su explicación divulgativa (baja a 7) y las normas (traslado a la jornada siguiente) indica que la norma escrita de Elige 8 no está publicada en abierto de forma accesible; lo operativo en los escrutinios 2026 es que siempre hay acertantes de 8 (mínimo observado: 2 acertantes, 09/08/2026).

### Gaps
- No se ha localizado el texto íntegro y vigente de la norma de Elige 8 (ni en BOE ni en loteriasyapuestas.es accesible al fetcher). El 55 % está confirmado por tres fuentes independientes y por la aritmética de dos escrutinios oficiales, pero el redactado oficial sólo lo tenemos citado de segunda mano.
- pizarra15.es afirma que "LAE designa cada semana 8 de los 15 partidos" y que hay "cinco categorías, de 5 a 8 aciertos" — esto contradice a SELAE, Losilla y casasdeapuestas (el jugador elige los 8; una sola categoría). Se considera fuente no fiable y no se usa — [pizarra15.es](https://pizarra15.es/guia/elige-8/)

## 2. Estadísticas históricas de premios: jornadas de Liga vs semanas europeas (2024-2026)

### Takeaway
En la temporada 2026/27 el premio de 8/8 oscila entre 1,82 € (7.885 acertantes, jueves 29/10/2026) y 6.095,10 € (2 acertantes, 09/08/2026); mediana aproximada en el rango 20-100 €. Las jornadas de jueves (semanas europeas) recaudan la mitad (~26-52 k€ frente a 90-110 k€ en fin de semana) y, cuando los favoritos ganan, concentran a muchos acertantes (9-15 % de las apuestas) con premios de 1,8-2,9 €; cuando hay sorpresas (14/10/2026) pagan 849 €. No hay ningún patrón "Europa paga más"; lo que paga es la jornada con sorpresas en los partidos que la masa elige.

### Cited Findings
Serie 2026/27 (acertantes de 8 × premio por acertante). Fuentes: tulotero.es (tabla de escrutinios J15-J23, replica el oficial) y Losilla para J23; notas de prensa SELAE vía fragmentos de búsqueda para el resto:
- J15, jueves 22/10/2026 (semana europea): 882 acertantes, 32,31 € — [tulotero.es](https://tulotero.es/resultados-quiniela/)
- J16, 25-26/10/2026: 590 acertantes, 94,33 € — [tulotero.es](https://tulotero.es/resultados-quiniela/); [SELAE escrutinio 25/10/2026](https://www.loteriasyapuestas.es/es/la-quiniela/escrutinios/la-quiniela-premios-y-ganadores-del-25-de-octubre-de-2026)
- J17, jueves 29/10/2026: 7.885 acertantes, 1,82 € (recaudación Quiniela 601.491 €) — [tulotero.es](https://tulotero.es/resultados-quiniela/)
- J18, 1-2/11/2026: 2.801 acertantes, 21,66 € — [tulotero.es](https://tulotero.es/resultados-quiniela/)
- J19, jueves 5/11/2026 (semana europea): 1.272 acertantes, 21,63 € — [tulotero.es](https://tulotero.es/resultados-quiniela/); [SELAE escrutinio 04/11/2026](https://www.loteriasyapuestas.es/en/la-quiniela/escrutinios/la-quiniela-premios-y-ganadores-del-04-de-noviembre-de-2026)
- J20, 8/11/2026: 258 acertantes, 214,66 € (la misma jornada repartió 1.647.986,55 € a un Pleno al 15) — [tulotero.es](https://tulotero.es/resultados-quiniela/); [SELAE escrutinio 08/11/2026](https://www.loteriasyapuestas.es/es/la-quiniela/escrutinios/la-quiniela-premios-y-ganadores-del-08-de-noviembre-de-2026)
- J21, 15/11/2026: 49 acertantes, 666,36 € (jornada sin Pleno al 15 y con sólo 4 de 14) — [tulotero.es](https://tulotero.es/resultados-quiniela/)
- J22, jueves 19/11/2026 (semana europea, Champions): 5.390 acertantes, 2,85 € (recaudación Quiniela 621.900 €) — [tulotero.es](https://tulotero.es/resultados-quiniela/); [betbrothers.es](https://betbrothers.es/pronosticos-deportivos/elige-8-quiniela/)
- J23, 21-22/11/2026: 7.235 acertantes, 7,05 € (recaudación Quiniela 2.940.306,75 €) — [eduardolosilla.es escrutinio](https://www.eduardolosilla.es/quiniela/ayudas/escrutinio); [tulotero.es](https://tulotero.es/resultados-quiniela/)
- Miércoles 14/10/2026 (semana Champions, J13): 29 acertantes, 849,19 € — [SELAE escrutinio 14/10/2026](https://www.loteriasyapuestas.es/es/la-quiniela/escrutinios/la-quiniela-premios-y-ganadores-del-14-de-octubre-de-2026) (fragmento de búsqueda)
- 21/10/2026: 882 acertantes, 32,31 € (= J15; el fragmento lo fecha 21/10 e incluye Oporto, Liverpool y Manchester City) — [SELAE escrutinio 21/10/2026](https://www.loteriasyapuestas.es/en/la-quiniela/escrutinios/la-quiniela-premios-y-ganadores-del-21-de-octubre-de-2026)
- Miércoles 30/09/2026: 69 acertantes, 243,41 € — [SELAE nota de prensa 30/09/26](https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/NOTA_DE_PRENSA_LA_QUINIELA_30_09_26.pdf) (fragmento)
- 20/09/2026: 1.070 acertantes, 54,29 €, recaudación Elige8 105.613 € — [SELAE nota de prensa 20/9/26](https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/NOTA_DE_PRENSA_LA_QUINIELA_20_9_26.pdf) (fragmento)
- 14/09/2026: 144 acertantes, 312,29 € — [SELAE nota de prensa 13/9/26](https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/NOTA_DE_PRENSA_LA_QUINIELA_13_9_26.pdf) (fragmento)
- 9-10/09/2026 (jueves, internacionales): 9.284 acertantes, 2,58 €, recaudación Elige8 43.559 € — [SELAE nota de prensa 9/09/26](https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/NOTA_DE_PRENSA_LA_QUINIELA_9_09_26.pdf) (fragmento)
- 16/08/2026 (J1 26/27): 23 acertantes, 1.392,60 € — [SELAE nota de prensa 16/08/26](https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/NOTA_DE_PRENSA_LA_QUINIELA_16_08_26.pdf) (fragmento); confirmado en [pizarra15.es](https://pizarra15.es/guia/elige-8/)
- 09/08/2026: 2 acertantes, 6.095,10 € — [SELAE nota de prensa 9/8/26](https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/NOTA_DE_PRENSA_LA_QUINIELA_9_8_26.pdf) (fragmento)
- 12/07/2026: 2.520 acertantes, 5,86 € — [SELAE nota de prensa 12/7/26](https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/NOTA_DE_PRENSA_LA_QUINIELA_12_7_26.pdf) (fragmento)
- Junio 2026 (nota 24/06/26): 368 acertantes, 30,39 € — [SELAE nota de prensa 24/06/26](https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/NOTA_DE_PRENSA_LA_QUINIELA_24_06_26.pdf) (fragmento)
- Jornada 65 (domingo 31/05/2026): 3.125 acertantes, 11,73 € — [lotopia.com](https://www.lotopia.com/quiniela) (fragmento)
- Temporada 2025/26, jornada 11 (5/10/2025): 39 acertantes, 1.565,86 € (misma jornada: un 14 con bote de 2.461.188,75 €) — [SELAE noticia "premio de 2,4 millones"](https://www.loteriasyapuestas.es/es/noticias/premios/premio-de-2-4-millones-en-la-quiniela)
- Jornada 71 (5/07/2025): 502 acertantes de 8 — [SELAE nota de prensa 05/07/26 (encabezado 2026, contenido 2025)](https://www.loteriasyapuestas.es/f/loterias/documentos/Quiniela/Notas%20de%20prensa/NOTA_DE_PRENSA_LA_QUINIELA_05_07_26.pdf) (fragmento, sin premio unitario)
- Histórico 2021/22 (35 jornadas, casasdeapuestas.com): premio máximo de 8 aciertos 18.104 € (jornada 34), mínimo 2 € (jornada 12), 3 € (j. 14), 4,28-4,60 € (j. 28 y 30); ratio premio-14/premio-Elige8 medio 246,6, mínimo 16,57 (j. 34), máximo 1.557,36 (j. 18: 165.080 € vs 106 €); en las 10 jornadas sin acertantes de 14 el Elige 8 pagó entre 1.277 € y 18.104 € — [casasdeapuestas.com](https://www.casasdeapuestas.com/blog/elige8/)
- Primeras 50 jornadas (20/10/2019 - 27/10/2020): recaudación media 86.314,42 €, mínima 22.386,98 €, máxima 175.605,75 €; premio de 8 más bajo 4,84 €, más alto 74.143 € — [eduardolosilla.es](https://www.eduardolosilla.es/quiniela/boletos/elige8)

### Inferences
- Recaudación implícita (R = acertantes × premio / 0,55) y fracción de apuestas ganadoras (N / (R/0,50)) para 2026/27, calculadas a partir de las cifras citadas:
  | Jornada | Acert. | Premio | R implícita | Apuestas | % apuestas ganadoras |
  |---|---|---|---|---|---|
  | J13 mié 14/10 (Champions) | 29 | 849,19 | 44.775 € | 89.551 | 0,03 % |
  | J15 jue 22/10 (Europa) | 882 | 32,31 | 51.813 € | 103.627 | 0,85 % |
  | J16 dom 25/10 | 590 | 94,33 | 101.190 € | 202.381 | 0,29 % |
  | J17 jue 29/10 | 7.885 | 1,82 | 26.092 € | 52.184 | 15,1 % |
  | J18 lun 2/11 | 2.801 | 21,66 | 110.308 € | 220.617 | 1,27 % |
  | J19 jue 5/11 (Europa) | 1.272 | 21,63 | 50.024 € | 100.049 | 1,27 % |
  | J20 dom 8/11 | 258 | 214,66 | 100.695 € | 201.390 | 0,13 % |
  | J21 dom 15/11 | 49 | 666,36 | 59.367 € | 118.733 | 0,04 % |
  | J22 jue 19/11 (Europa) | 5.390 | 2,85 | 27.930 € | 55.860 | 9,65 % |
  | J23 dom 22/11 | 7.235 | 7,05 | 92.740 € | 185.479 | 3,90 % |
  | mié 30/09 | 69 | 243,41 | 30.537 € | 61.074 | 0,11 % |
  | dom 20/09 | 1.070 | 54,29 | 105.613 € (oficial) | 211.237 | 0,51 % |
  | jue 10/09 | 9.284 | 2,58 | 43.559 € (oficial) | 87.101 | 10,7 % |
- Las jornadas entre semana recaudan en Elige 8 la mitad o menos (26-52 k€) que las de fin de semana (93-110 k€), así que el fondo máximo a repartir ronda 15-28 k€ frente a 50-60 k€.
- La dispersión del % de apuestas ganadoras (0,03 % a 15 %) es enorme y domina el premio: en las tres jornadas de jueves "sin sorpresas" (J17, J22, 10/09) ganó entre el 9,6 % y el 15 % de las apuestas y el premio quedó en 1,8-2,9 € (3,6-5,7 veces el precio de la apuesta de 0,50 €); en J13 (Champions con sorpresas) ganó el 0,03 % y el premio fue 1.698 veces el precio.
- Hay una correlación visible entre jornadas con pocos 14 aciertos y Elige 8 alto (J21: 4 de 14 → 666 €; J20: 6 de 14 → 215 €; 2021/22: las jornadas sin 14 pagaron 1.277-18.104 €) y a la inversa (J23: 152 de 14 → 7,05 €; J17: 319 de 14 → 1,82 €). Es la misma variable latente: "la masa acertó o no".
- Datos propios del repositorio (data/premios/historial_premios.json, 28 jornadas con Elige 8 jugado, 2025/26-2026/27): 2 de 28 con 8/8 (7 %), 12 con 7/8, 8 con 6/8, 6 con ≤5/8. Precisión por partido elegido 182/237 = 76,8 % (resumen_temporada 2026/27). Con una precisión por partido de 0,77 e independencia, P(8/8) = 0,77^8 ≈ 12 %, coherente con 2/28 observado dada la muestra pequeña. En las semanas europeas 26/27 el Elige 8 propio hizo 7/8, 6/8, 6/8 y ≤6/8 (CUADERNO_OJEADOR.md, J5/J13/J15/J24).

### Gaps
- No existe (que se haya encontrado) una serie publicada y descargable de premios de Elige 8 por jornada 2023-2026 con etiqueta "europea/doméstica"; la tabla anterior está reconstruida de escrutinios sueltos. Las notas de prensa 2025 indexadas tienen encabezados de fecha inconsistentes (año 2026 con contenido 2025), lo que impide fechar con seguridad la jornada 71 "5/07/2025".
- La recaudación de Elige 8 sólo se publica en las notas de prensa (no en las tablas de escrutinio replicadas por tulotero/Losilla), de ahí que casi toda la columna R sea implícita.

## 3. Matemáticas: P(8/8) con dobles/triples, EV, break-even y ejemplo numérico

### Takeaway
Con 8 partidos fijos P(8/8) = producto de las 8 probabilidades del signo marcado; cubrir un partido con triple lo saca del producto (probabilidad 1) a cambio de triplicar el coste, con doble lo sustituye por la masa de los dos signos y duplica el coste. Para el ejemplo pedido (6 fijos 0,80·0,78·0,77·0,73·0,73·0,70 + 2 triples) P(8/8) = 17,9 %, coste 4,50 € y break-even 25,11 € de premio por acertante; con los premios observados en 2026/27 el ticket es EV+ en 10 de 13 jornadas listadas pero muy EV- en las tres de jueves sin sorpresas.

### Cited Findings
- Cada doble/triple dentro de los 8 elegidos multiplica el nº de apuestas de Elige 8 por 2/3; cada apuesta cuesta 0,50 € — [eduardolosilla.es](https://www.eduardolosilla.es/quiniela/boletos/elige8); [SELAE](https://www.loteriasyapuestas.es/es/centro-de-ayuda/como-se-juega/como-jugar-a-la-quiniela)
- Cubrir los 3 signos en los 8 partidos = 3^8 = 6.561 apuestas = 3.280,50 € sólo de Elige 8; un lector (Jorge, 04/02/2023) matiza que los 8 triples directos en la Quiniela base elevan el total a más de 8.000 € — [casasdeapuestas.com](https://www.casasdeapuestas.com/blog/elige8/)
- betbrothers.es sitúa la probabilidad "a ciegas" de 8/8 en 1 entre 6.561 (= 1/3^8) — [betbrothers.es](https://betbrothers.es/pronosticos-deportivos/elige-8-quiniela/)
- Premio por acertante = 0,55 × R / N (único nivel, a partes iguales) — [eduardolosilla.es](https://www.eduardolosilla.es/quiniela/boletos/elige8); [casasdeapuestas.com](https://www.casasdeapuestas.com/blog/elige8/)

### Inferences (derivación propia, sin fuente externa; la aritmética se ha ejecutado en Python)
- Notación: partidos elegidos i = 1..8, con cobertura c_i ∈ {1,2,3} signos y probabilidad cubierta q_i = suma de las probabilidades de los signos marcados (q_i = 1 si triple). Entonces:
  - Nº de apuestas de Elige 8: K = ∏ c_i. Coste C = 0,50 € × K.
  - Exactamente una apuesta puede acertar 8/8 (las combinaciones son mutuamente excluyentes), así que P(cobrar) = ∏ q_i y el nº de apuestas ganadoras propias es 0 o 1.
  - EV = (∏ q_i) × Premio − 0,50 × K, donde Premio = 0,55 × R / N (N incluye tu propia apuesta ganadora).
  - Break-even: Premio* = 0,50 × K / ∏ q_i. Equivalentemente, se cobra más de lo apostado si la fracción de apuestas ganadoras N/(R/0,5) < 0,55 × ∏ q_i / K.
  - Sustituir un fijo de probabilidad p por un triple multiplica P por 1/p y el coste por 3: compensa sólo si p < 1/3 (nunca en un favorito); por un doble de masa q multiplica P por q/p y el coste por 2: compensa sólo si q/p > 2, es decir, si el signo fijo tenía p < 0,5 y el doble recoge casi toda la masa. Conclusión: en términos de EV por euro, cubrir favoritos con dobles/triples siempre empeora el ratio P/coste; la cobertura sólo tiene sentido para subir la probabilidad absoluta de cobrar (varianza), no el EV.
- Ejemplo pedido: 6 fijos con p = 0,80, 0,78, 0,77, 0,73, 0,73, 0,70 → ∏ = 0,1792. Dos partidos con triple (q = 1, c = 3 cada uno): K = 9, C = 4,50 €, P(8/8) = 17,92 %, Premio break-even = 25,11 €. Variantes:
  - Los dos partidos con doble (masa cubierta 0,90 cada uno): K = 4, C = 2,00 €, P = 14,5 %, break-even 13,78 € (con masa 0,85: P 12,9 %, break-even 15,44 €).
  - Un triple + un doble (0,90): K = 6, C = 3,00 €, P = 16,1 %, break-even 18,60 €.
  - Ocho fijos (los dos extra a 0,65 y 0,60): K = 1, C = 0,50 €, P = 6,99 %, break-even 7,15 €. Es el mejor ratio P/coste (13,98 % por cada 0,50 €... frente a 1,99 % por cada 0,50 € con los dos triples), pero cobra una de cada 14 jornadas.
- EV del ticket 2 triples (4,50 €) con los premios reales 2026/27: premio 2,58 € → EV −4,04 € (retorno 10 %); 21,63 € → −0,62 € (86 %); 54,29 € → +5,23 € (216 %); 94,33 € → +12,41 € (376 %); 243,41 € → +39,13 €; 849,19 € → +147,70 €; 1.565,86 € → +276 €; 6.095,10 € → +1.088 €. Con la tabla de 13 jornadas de 2026/27, el premio superó el break-even de 25,11 € en 9 de 13 (todas menos J17 1,82, J22 2,85, J23 7,05, 10/09 2,58). Advertencia: esto supone que el ticket propio acierta con la misma P independientemente de si la jornada fue "loca" o no, lo cual es falso: la P real de acertar 8/8 es menor precisamente en las jornadas que pagan bien (ver §4).
- Media geométrica observada del premio importa menos que su distribución: el EV real es E[1{acierto} × Premio], y acierto y Premio están negativamente correlacionados (cuando aciertas, muchos otros también aciertan). La estimación honesta del EV exige condicionar: EV ≈ Σ_jornadas P(acierto | jornada) × Premio(jornada) / nº jornadas, usando premios históricos y el propio acierto histórico, no el producto de medias.

### Gaps
- No se ha encontrado ninguna calculadora pública de EV o P(8/8) para Elige 8; Losilla ofrece porcentajes de la masa por partido (VP, % signo, 7 pronósticos) pero explícitamente no tiene calculadora de probabilidad ni recomendación de partidos — [eduardolosilla.es](https://www.eduardolosilla.es/quiniela/boletos/elige8).
- No existe dato oficial de cuántas apuestas de Elige 8 incluyen cada partido (SELAE no publica qué partidos elige la masa; casasdeapuestas.com lo señala), así que N esperado sólo se puede modelar, no observar a priori.

## 4. ¿Los 8 más probables o los que la masa infrajuega? Dilución pari-mutuel y nº óptimo de "riesgos"

### Takeaway
Hay evidencia empírica directa de dilución: cuando los favoritos ganan, 4-15 % de las apuestas aciertan 8/8 y el premio cae por debajo de 3 €; cuando caen uno o dos favoritos muy jugados, el premio sube a cientos o miles de euros con el mismo fondo. La teoría de pools (Clair & Letscher 2007) formaliza la regla "apostar al borde": en un pool grande el favorito sólo es mejor si su probabilidad real supera la fracción de la masa que lo juega (a > p); los analistas españoles recomiendan dejar fuera 1-2 partidos "muy fáciles" y elegir partidos donde probabilidad real y masa estén alineadas. Ninguna fuente aporta un backtest del nº óptimo de picks arriesgados en Elige 8.

### Cited Findings
- casasdeapuestas.com (Pau Sisternas): "la clave no es acertar, es acertar cuando los demás no"; los jugadores tienden a elegir los mismos partidos, lo que da premios minúsculos cuando sale el resultado obvio; en La Quiniela el acierto arriesgado paga más, en Elige 8 dos jugadores con picks de dificultad opuesta cobran lo mismo; recomendación: elegir partidos donde probabilidad real y probabilidad implícita de la masa estén alineadas, no evitar partidos bastante probables, y dejar fuera 1-2 partidos que parezcan muy fáciles ("apuestas tanto a los partidos que dejas fuera como a los que eliges"); cierre: "La esencia del Elige 8 está en saber elegir los partidos y los pronósticos" — [casasdeapuestas.com](https://www.casasdeapuestas.com/blog/elige8/)
- Contraargumento de una lectora (Isa, 27/11/2023): elegir partidos difíciles no mejora tus opciones porque los demás seguirán eligiendo los fáciles y repartiendo el premio; propone elegir los fáciles y reducir triples para abaratar — [casasdeapuestas.com](https://www.casasdeapuestas.com/blog/elige8/)
- Interpretación del autor con datos 2021/22: Elige 8 paga mejor cuando no hay acertantes de 14, porque los jugadores eligen los mismos partidos y el premio se adelgaza cuando salen los resultados obvios — [casasdeapuestas.com](https://www.casasdeapuestas.com/blog/elige8/)
- betbrothers.es: sus selecciones de Elige 8 son "normalmente los partidos más seguros a priori", con criterios de forma, localía, H2H y cuotas; en su jornada 23 cita 5.390 acertantes y 2,85 € — [betbrothers.es](https://betbrothers.es/pronosticos-deportivos/elige-8-quiniela/)
- Clair & Letscher, "Optimal Strategies for Sports Betting Pools", Operations Research 55(6), 2007, pp. 1163-1177: "teams that are popularly perceived as 'favorites' gain a disproportionate share of entries. In large pools there can be a significant advantage to picking upsets that differentiate [...]"; "A good score is worthless if most of the pool entrants also score well"; "pool participants overbet favorites, leaving plenty of room for strategic improvements. In larger (thousands of players) pools, crowd avoidance is essential—picking all favorites is one of the few losing bets"; las estrategias de retorno esperado superan a las de maximizar aciertos "often by orders of magnitude"; "picking more conservatively in small pools and choosing more upsets in larger pools" — [Clair & Letscher 2007, PDF](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf); [INFORMS](https://pubsonline.informs.org/doi/fpi/10.1287/opre.1070.0448)
- Clair & Letscher, pool de un partido con N → ∞: si el favorito gana con probabilidad a y la fracción de la masa que lo juega es p, el retorno esperado de apostar al favorito es a/p y al no favorito (1−a)/(1−p); "the favorite is better when a > p and the underdog is better when a < p. We call this strategy betting the edge" — [Clair & Letscher 2007, PDF](https://www.stat.berkeley.edu/~aldous/157/Papers/clair.pdf)
- Estudio del Toto austriaco (pool pari-mutuel con botes): dada la probabilidad relativamente alta de bote, es óptimo sobreapostar a los favoritos, y los apostantes reales los sobreapuestan aún más de lo que predice el modelo — [core.ac.uk](https://core.ac.uk/works/3021126) (sólo resumen; texto 403)
- Losilla publica, para cada partido, el % de veces que es pronosticado (VP) y el reparto 1/X/2 de quienes lo eligen, con fuentes 1X2, PROB (casas), LAE, QUIN y TEC — [eduardolosilla.es](https://www.eduardolosilla.es/quiniela/boletos/elige8)

### Inferences
- Traducción de "betting the edge" a Elige 8: con una categoría única y miles de apuestas, el retorno por euro de incluir el partido i con el signo s es aproximadamente a_i(s)/p_i(s), donde a es la probabilidad real y p la fracción de apuestas de Elige 8 que incluyen ese partido con ese signo. Como SELAE no publica p_i para Elige 8, el proxy disponible es el % de la masa Quiniela/LAE que Losilla muestra; un favorito jugado al 85 % por la masa con probabilidad real 75 % tiene edge negativo (0,88) aunque sea el "más probable"; un partido con masa 55 % y probabilidad real 60 % tiene edge 1,09.
- El objetivo "8 más probables" maximiza P(8/8) pero no EV: la dilución observada (J17 15,1 %, 10/09 10,7 %, J22 9,65 % de apuestas ganadoras) se produce exactamente en las jornadas en las que los 8 favoritos más claros ganan todos, que es cuando el ticket "más probable" cobra. El ticket "más probable" cobra a menudo y cobra poco (1,8-7 € por 0,50 €, es decir, retorno 4-14× cuando acierta, que con P ≈ 10-18 % da EV ≈ 0,4-2,5× el coste: en el límite, sólo es claramente rentable si tu P(8/8) real es ≥ 2-3 veces la de la masa).
- El nº óptimo de picks "no masa" no está documentado para Elige 8. De la teoría de Clair-Letscher (más upsets cuanto mayor el pool; 50-220 k apuestas por jornada aquí = pool grande) y del consejo de Sisternas (dejar fuera 1-2 "muy fáciles") se infiere una regla prudente: 6 partidos con edge ≥ 1 (probabilidad real ≥ masa) y 1-2 partidos donde el signo del ticket tenga a/p claramente > 1 (favorito "despreciado" por la masa o X/2 infrajugado), evitando los favoritos con masa ≥ 80 % cuya probabilidad real sea < masa. Sustituir un partido con masa 85 %/real 75 % por otro con masa 55 %/real 60 % baja P(8/8) un 20 % pero multiplica por ~1,25 el edge de ese hueco; el beneficio neto depende de que la correlación entre tu acierto y el de la masa baje, que es lo que sube el premio condicional.
- Datos propios 2026/27 (CUADERNO_OJEADOR.md, J24): en las 4 Champions 26/27 (56 partidos), el favorito de la masa ≥ 80 % acertó 10/10, 70-80 % 9/12, 60-70 % 4/7, 50-60 % 7/13; los gigantes 65-79 % cayeron 6 de 19. Elige 8 construido sobre los 8 favoritos más claros en semana europea dio 7/8, 6/8, 6/8, ≤6/8 (0 de 4 pagos), y la conclusión registrada fue "no volver a jugarlo en semana europea". Esto es coherente con la tabla del §2: cuando esos favoritos ganan todos, el premio es de 1,8-2,9 €; cuando cae uno, no cobras. El perfil riesgo/retorno del "8 más probables" en jueves es el peor de los observados.

### Gaps
- No se ha encontrado ningún backtest publicado (español ni académico) del nº óptimo de picks arriesgados en Elige 8, ni de la elasticidad premio vs nº de favoritos incluidos; la tabla del §2 permite estimarla a posteriori pero faltan los porcentajes de masa por partido de cada jornada (Losilla los tiene en su web, no descargables aquí).
- No se ha podido leer el texto completo del paper del Toto austriaco (core.ac.uk 403) ni la parte de Clair-Letscher con el umbral a(N) para N finito; el fetch del PDF se hizo por extracción local de texto y las tablas 3-5 (nº de upsets óptimos por tamaño de pool) no se han transcrito.
- No se han localizado hilos de foro (quinielista.es, laquiniela.es) sobre estrategia de Elige 8; las búsquedas sólo devolvieron blogs comerciales (casasdeapuestas, betbrothers, laps4, pizarra15) y la ayuda de Losilla. quinielista.es no apareció con contenido propio de Elige 8.

## 5. Herramientas y calculadoras publicadas

### Takeaway
No existe calculadora pública de EV/P(8/8) para Elige 8. Lo más cercano son los porcentajes por partido de eduardolosilla.es (masa, cuotas, LAE, Quinielista, técnica) y los escrutinios replicados por tulotero.es/lotopia.com; el resto son guías comerciales sin herramienta.

### Cited Findings
- Losilla: selector de porcentajes por partido con 5 fuentes (1X2, PROB, LAE, QUIN, TEC), porcentaje VP de veces pronosticado y reparto por los 7 pronósticos (1, X, 2, 1X, X2, 12, 1X2); "No hay calculadora de probabilidad de acierto ni recomendaciones de partidos"; el escrutinio con recaudación, nº de acertantes de 8 y premio se publica 1-2 horas tras el último partido — [eduardolosilla.es, boleto Elige8](https://www.eduardolosilla.es/quiniela/boletos/elige8)
- Losilla, página de ayuda de escrutinio con el reparto por categorías y la fila Elige 8 de cada jornada — [eduardolosilla.es, escrutinio](https://www.eduardolosilla.es/quiniela/ayudas/escrutinio)
- tulotero.es replica el escrutinio oficial (categorías, acertantes, premio, Elige 8) por jornada — [tulotero.es](https://tulotero.es/resultados-quiniela/)
- Clair & Letscher publican el software CLOP que "generally implements algorithms from our Optimal Strategies for Sports Betting Pools article" (pools NFL/NCAA, no Quiniela) — [cs.slu.edu/~clair/pools](https://cs.slu.edu/~clair/pools)
- betbrothers.es publica pronósticos semanales de Elige 8 (sin herramienta de cálculo) y los escrutinios — [betbrothers.es](https://betbrothers.es/pronosticos-deportivos/elige-8-quiniela/)

### Inferences
- Una calculadora propia es trivial con las fórmulas del §3 (P = ∏ q_i, coste 0,50 × ∏ c_i, premio = 0,55 R/N) y el repositorio ya dispone de precisión histórica por partido y de los % de masa LAE; lo que falta para estimar N esperado es un modelo de "qué 8 partidos elige la masa", que puede aproximarse con los VP de Losilla.

### Gaps
- No se ha podido acceder a los VP de Losilla en formato de datos; sólo consta su existencia en la página.
