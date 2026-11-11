"""Batería de mutaciones de sas-lgd-from-scratch.

Cada entrada planta un error de negocio en una copia de la solución y exige
que el `check_N` de la etapa lo rechace. No se prueba a `sasmini`: se prueba
que el corrector distingue la respuesta correcta de la que un analista
principiante escribiría.

Ejecutar:

    python3 _build/run_mutations.py

Una entrada MISSED es un check débil, no una mutación débil: se arregla el
check, nunca se borra el error.
"""

MUTATIONS = [
    # --- etapa 1: LGD simple --------------------------------------------------
    ("la LGD se calcula como recuperación sobre EAD, no como pérdida",
     "stage_01.sas",
     "lgd_bp = int((ead_cents - recuperacion_cents) * 10000 / ead_cents);",
     "lgd_bp = int(recuperacion_cents * 10000 / ead_cents);",
     1),

    # --- etapa 2: EAD ---------------------------------------------------------
    ("el CCF se aplica a una división por 10000 en vez de al no dispuesto",
     "stage_02.sas",
     "ead_cents = dispuesto_cents + int(no_dispuesto_cents * ccf_bp / 10000);",
     "ead_cents = dispuesto_cents + int(no_dispuesto_cents / 10000);",
     2),

    # --- etapa 3: MRP ---------------------------------------------------------
    ("el acumulado se reinicia en LAST en vez de FIRST",
     "stage_03.sas",
     "  if first.prestamo then mrp_total_cents = 0;",
     "  if last.prestamo then mrp_total_cents = 0;",
     3),

    # --- etapa 4: gastos añadidos --------------------------------------------
    ("todo gasto añadido se capitaliza, aunque ya estuviera dispuesto",
     "stage_04.sas",
     "  if ya_en_dispuesto = 0 then",
     "  if 1 = 1 then",
     4),

    # --- etapa 5: gastos repercutidos ----------------------------------------
    ("el gasto repercutido se cuenta como recuperación aunque no se cobre",
     "stage_05.sas",
     "  if cobrado = 1 then recuperado_cents = gasto_repercutido_cents;\n"
     "  else recuperado_cents = 0;",
     "  recuperado_cents = gasto_repercutido_cents;",
     5),

    # --- etapa 6: MERGE -------------------------------------------------------
    ("el MERGE se hace por posición sobre las tablas sin ordenar",
     "stage_06.sas",
     "  merge work.ead_sorted work.mrp_sorted;\n  by prestamo;",
     "  merge ead_base mrp_base;",
     6),

    # --- etapa 7: LGD con recuperación neta ----------------------------------
    ("la LGD no tiene tope inferior y P5 queda negativa",
     "stage_07.sas",
     "  if lgd_bp < 0 then lgd_bp = 0;\n",
     "",
     7),

    # --- etapa 8: descuento ---------------------------------------------------
    ("el valor presente ignora el factor de descuento",
     "stage_08.sas",
     "vp_cents = int(importe_cents * factor_bp / 10000);",
     "vp_cents = importe_cents;",
     8),

    # --- etapa 9: garantía ----------------------------------------------------
    ("la ejecución de la garantía no cuesta nada",
     "stage_09.sas",
     "  recuperacion_cents = int(valor_garantia_cents * (10000 - haircut_bp) / 10000)\n"
     "    - coste_ejecucion_cents;",
     "  recuperacion_cents = int(valor_garantia_cents * (10000 - haircut_bp) / 10000);",
     9),

    # --- etapa 10: contagio ---------------------------------------------------
    ("el contagio se aplica aunque el garante siga sano",
     "stage_10.sas",
     "  if garante_incumplido = 1 then",
     "  if 1 = 1 then",
     10),

    # --- etapa 11: cura -------------------------------------------------------
    ("una cura se trata como pérdida total",
     "stage_11.sas",
     "    lgd_bp = 0;",
     "    lgd_bp = 10000;",
     11),

    # --- etapa 12: cartera ----------------------------------------------------
    ("la LGD de cartera divide por un EAD fijo en vez del EAD del segmento",
     "stage_12.sas",
     "  lgd_bp = int(perdida_total_cents * 10000 / ead_total_cents);",
     "  lgd_bp = int(perdida_total_cents * 10000 / 1000000);",
     12),
]
