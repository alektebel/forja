# SAS y LGD From Scratch

Doce etapas para calcular una LGD que un comité de riesgo pueda defender. El
curso empieza con la pregunta más simple —qué parte de un préstamo no vuelve— y
va añadiendo una pieza por etapa: EAD, MRP, gastos añadidos, gastos
repercutidos, unión uno a uno, recuperación neta, descuento de flujos,
garantías con recorte, contagio del garante, cura contra castigo y, al final,
la LGD ponderada de la cartera. Lo simple primero; cada complicación llega
cuando la anterior ya está resuelta.

El lenguaje es **SAS**. Cada etapa se resuelve con un `DATA` step o un `PROC`
que el corrector ejecuta; no hay que escribir la respuesta en Python. No hace
falta licencia de SAS para seguir el curso: `sasmini.py` es un intérprete
pequeño y determinista del subconjunto que las soluciones usan.

Todo el dinero va en **céntimos** y todas las tasas en **puntos básicos**
(10000 pb = 100%). No hay `float`, ni reloj, ni aleatoriedad, ni red. Donde hay
una división, el contrato fija el truncamiento con `int()`.

## Las doce etapas, de simple a complejo

| Etapa | Archivo | Mecanismo | Salida que se comprueba |
|---:|---|---|---|
| 1 | `stage_01.sas` | LGD simple: pérdida sobre EAD, sin gastos ni garantías | `S1=7000, S2=0, S3=10000` pb |
| 2 | `stage_02.sas` | EAD = dispuesto + no dispuesto × CCF; filtro de incumplidos | `P1=14.0M, P2=8.0M, P3=27.5M, P4=6.5M` |
| 3 | `stage_03.sas` | MRP acumulado con `RETAIN` y `FIRST`/`LAST` | `P1=300k, P2=0, P3=1.5M, P4=300k` |
| 4 | `stage_04.sas` | Gasto añadido: capitalizar solo lo que no estaba dispuesto | `P1=14.2M, P2=8.0M, P3=27.5M, P4=6.6M` |
| 5 | `stage_05.sas` | Gasto repercutido: recuperación solo si se cobra | P1 cobra 100k de 150k; P4 no cobra 75k |
| 6 | `stage_06.sas` | `MERGE` uno a uno: el MRP no multiplica el EAD | 4 filas; EAD y MRP en columnas distintas |
| 7 | `stage_07.sas` | LGD = 1 − recuperación neta / EAD, con topes 0 y 10000 | `P1=4226, P2=7625, P3=2291, P4=3637, P5=0, P6=10000` pb |
| 8 | `stage_08.sas` | Descontar cada flujo con su propio factor | `P1=(95k,180k), P2=490k, P3=(800k,700k)` |
| 9 | `stage_09.sas` | Garantía: recorte y coste de ejecución | `P1=4508, P2=8250, P3=2728` pb |
| 10 | `stage_10.sas` | Contagio: si el garante cayó, la garantía vale menos | `P1=5.6M, P2=4.5M, P3=1.4M` |
| 11 | `stage_11.sas` | Cura contra castigo/venta | `P1=0, P2=7500, P3=2500, P4=0, P5=2000` pb |
| 12 | `stage_12.sas` | LGD de cartera ponderada por EAD, no promedio de LGD | `Hipoteca=2949, Consumo=5821` pb |

Cada etapa trae su propia tabla de entrada. No hay dependencia de la etapa
anterior: se puede hacer la 10 sin haber hecho la 6. El orden propuesto cuenta
la historia completa de un expediente, pero no es un candado.

## El mundo es dato, la etapa es tuya

`world.py` es el contrato de datos. No se edita. Sus tablas están construidas
para que el caso límite sea visible:

- **P5** no está incumplido en la etapa 2: el filtro debe excluirlo.
- **P3** ya lleva el gasto añadido dentro del dispuesto: capitalizarlo otra vez
  es el error clásico.
- **P1** tiene un gasto repercutido cobrado y otro impagado: solo el cobrado es
  recuperación.
- **P1** tiene tres MRP, no un pago único: el `RETAIN` es la etapa.
- **P5** recupera más que su EAD y **P6** no recupera nada: los dos topes de la
  LGD.
- **Hipoteca** tiene dos préstamos con LGD distintas: el promedio simple no es
  la LGD del segmento.

## Qué significa MRP aquí

En este curso **MRP = monto recuperado parcial**: los pagos que el deudor
alcanza a hacer después del incumplimiento y antes del cierre del expediente. No es el
MRP de una tabla regulatoria concreta ni una sigla universal: es la definición
operativa que el curso usa para enseñar acumulación, unión uno a uno y
recuperación neta.

La etapa 3 los acumula. La etapa 6 los une al EAD sin sumarlos al EAD. La etapa
7 los cuenta **una sola vez** en la recuperación neta.

## Cómo se verifica

| Qué | Comando | Resultado |
|---|---|---|
| plantillas | `python3 codecraft/cli.py run sas-lgd-from-scratch` | las 12 fallan con una causa de negocio, ninguna rompe el intérprete |
| soluciones | `python3 _build/run_mutations.py` | `baseline: 12/12 PASS` |
| batería de mutaciones | `python3 _build/run_mutations.py` | `MISSED: 0/12` |

La batería planta un error de negocio por etapa y exige que el `check_N` lo
rechace. No prueba el intérprete: prueba que el corrector distingue la respuesta
correcta de la que escribiría alguien que aún no domina el mecanismo.

```bash
cd sas-lgd-from-scratch
python3 _build/run_mutations.py
```

## Las leyes de una etapa

- Un mecanismo por etapa; si el corrector falla, el mensaje nombra la causa.
- Solo se usan las columnas de la tabla de esa etapa y las funciones SAS que
  `sasmini.py` documenta.
- Nada de `float`, `random`, reloj, red ni estado global mutable.
- `int()` trunca; los valores fijados el valor exacto en céntimos o pb.
- El archivo del alumno empieza con un `TODO:` y una plantilla que produce una
  tabla válida pero incorrecta, para que el primer error sea de negocio, no de
  sintaxis.

## Límites

El curso no modela: carteras reales de millones de préstamos, PD ni migraciones
de rating, escenarios macroeconómicos, IFRS 9 completo, el modelo interno IRB,
titulizaciones, derivados de crédito, ni la normativa de cada jurisdicción. Es
una versión docente y determinista del cálculo de LGD, no un sistema de
producción. `sasmini.py` implementa el subconjunto de SAS que las doce etapas
necesitan; no es un compilador de SAS.
