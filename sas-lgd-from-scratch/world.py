"""El mundo del curso: cartera, flujos, gastos y garantías.

Todo va en céntimos y puntos básicos. El alumno nunca edita este archivo: es el
contrato de datos que el corrector entrega a cada etapa. Cada tabla está
diseñada para que el caso límite sea visible:

- P5 está fuera de default en la etapa 1 y no debe aparecer.
- P3 ya lleva el gasto añadido dentro del dispuesto: capitalizarlo otra vez es
  el error clásico.
- El gasto repercutido de P1 tiene una parte cobrada y otra no; solo la cobrada
  es recuperación.
- P1 tiene tres MRP, no un pago único.
- P5 recupera más que su EAD y P6 no recupera nada: los dos topes de LGD.
"""


def portfolio():
    """Exposición al default: dispuesto, no dispuesto y CCF."""
    return [
        {"prestamo": "P1", "segmento": "Hipoteca", "incumplido": 1,
         "dispuesto_cents": 12_000_000, "no_dispuesto_cents": 4_000_000, "ccf_bp": 5000},
        {"prestamo": "P2", "segmento": "Consumo", "incumplido": 1,
         "dispuesto_cents": 8_000_000, "no_dispuesto_cents": 0, "ccf_bp": 5000},
        {"prestamo": "P3", "segmento": "Hipoteca", "incumplido": 1,
         "dispuesto_cents": 25_000_000, "no_dispuesto_cents": 5_000_000, "ccf_bp": 5000},
        {"prestamo": "P4", "segmento": "Consumo", "incumplido": 1,
         "dispuesto_cents": 5_000_000, "no_dispuesto_cents": 3_000_000, "ccf_bp": 5000},
        {"prestamo": "P5", "segmento": "Comercial", "incumplido": 0,
         "dispuesto_cents": 3_000_000, "no_dispuesto_cents": 1_000_000, "ccf_bp": 5000},
    ]


def cashflows_mrp():
    """Pagos parciales (MRP) por préstamo y periodo, en céntimos."""
    return [
        {"prestamo": "P1", "periodo": 1, "mrp_cents": 100_000},
        {"prestamo": "P1", "periodo": 2, "mrp_cents": 150_000},
        {"prestamo": "P1", "periodo": 3, "mrp_cents": 50_000},
        {"prestamo": "P2", "periodo": 1, "mrp_cents": 0},
        {"prestamo": "P3", "periodo": 1, "mrp_cents": 1_000_000},
        {"prestamo": "P3", "periodo": 2, "mrp_cents": 500_000},
        {"prestamo": "P4", "periodo": 1, "mrp_cents": 200_000},
        {"prestamo": "P4", "periodo": 2, "mrp_cents": 0},
        {"prestamo": "P4", "periodo": 3, "mrp_cents": 100_000},
    ]


def ead_con_gastos():
    """EAD ya calculado, más el gasto añadido y si ya estaba en el dispuesto."""
    return [
        {"prestamo": "P1", "ead_cents": 14_000_000,
         "gasto_anadido_cents": 200_000, "ya_en_dispuesto": 0},
        {"prestamo": "P2", "ead_cents": 8_000_000,
         "gasto_anadido_cents": 0, "ya_en_dispuesto": 0},
        {"prestamo": "P3", "ead_cents": 27_500_000,
         "gasto_anadido_cents": 300_000, "ya_en_dispuesto": 1},
        {"prestamo": "P4", "ead_cents": 6_500_000,
         "gasto_anadido_cents": 100_000, "ya_en_dispuesto": 0},
    ]


def repercutidos():
    """Gastos repercutidos al deudor: solo cuentan cuando se cobran."""
    return [
        {"prestamo": "P1", "gasto_repercutido_cents": 100_000, "cobrado": 1},
        {"prestamo": "P1", "gasto_repercutido_cents": 50_000, "cobrado": 0},
        {"prestamo": "P2", "gasto_repercutido_cents": 0, "cobrado": 0},
        {"prestamo": "P3", "gasto_repercutido_cents": 200_000, "cobrado": 1},
        {"prestamo": "P4", "gasto_repercutido_cents": 75_000, "cobrado": 0},
    ]


def ead_base():
    """EAD de cada préstamo, ya con los gastos añadidos bien tratados."""
    return [
        {"prestamo": "P1", "ead_cents": 14_200_000},
        {"prestamo": "P2", "ead_cents": 8_000_000},
        {"prestamo": "P3", "ead_cents": 27_500_000},
        {"prestamo": "P4", "ead_cents": 6_600_000},
    ]


def mrp_base():
    """MRP acumulado por préstamo, ya sumado (una fila por préstamo)."""
    return [
        {"prestamo": "P1", "mrp_total_cents": 300_000},
        {"prestamo": "P2", "mrp_total_cents": 0},
        {"prestamo": "P3", "mrp_total_cents": 1_500_000},
        {"prestamo": "P4", "mrp_total_cents": 300_000},
    ]


def lgd_base():
    """Recuperaciones y costes para calcular la LGD de cada préstamo."""
    return [
        {"prestamo": "P1", "ead_cents": 14_200_000, "mrp_cents": 300_000,
         "recuperacion_final_cents": 8_000_000,
         "gasto_repercutido_cobrado_cents": 100_000, "coste_directo_cents": 200_000},
        {"prestamo": "P2", "ead_cents": 8_000_000, "mrp_cents": 0,
         "recuperacion_final_cents": 2_000_000,
         "gasto_repercutido_cobrado_cents": 0, "coste_directo_cents": 100_000},
        {"prestamo": "P3", "ead_cents": 27_500_000, "mrp_cents": 1_500_000,
         "recuperacion_final_cents": 20_000_000,
         "gasto_repercutido_cobrado_cents": 200_000, "coste_directo_cents": 500_000},
        {"prestamo": "P4", "ead_cents": 6_600_000, "mrp_cents": 300_000,
         "recuperacion_final_cents": 4_000_000,
         "gasto_repercutido_cobrado_cents": 0, "coste_directo_cents": 100_000},
        {"prestamo": "P5", "ead_cents": 1_000_000, "mrp_cents": 0,
         "recuperacion_final_cents": 1_200_000,
         "gasto_repercutido_cobrado_cents": 0, "coste_directo_cents": 0},
        {"prestamo": "P6", "ead_cents": 1_000_000, "mrp_cents": 0,
         "recuperacion_final_cents": 0,
         "gasto_repercutido_cobrado_cents": 0, "coste_directo_cents": 0},
    ]


def flujos():
    """Flujos de recuperación con su factor de descuento al default, en pb."""
    return [
        {"prestamo": "P1", "periodo": 1, "importe_cents": 100_000, "factor_bp": 9500},
        {"prestamo": "P1", "periodo": 2, "importe_cents": 200_000, "factor_bp": 9000},
        {"prestamo": "P2", "periodo": 1, "importe_cents": 500_000, "factor_bp": 9800},
        {"prestamo": "P3", "periodo": 1, "importe_cents": 1_000_000, "factor_bp": 8000},
        {"prestamo": "P3", "periodo": 2, "importe_cents": 1_000_000, "factor_bp": 7000},
    ]


def garantias():
    """Garantía, haircut y coste de ejecución."""
    return [
        {"prestamo": "P1", "ead_cents": 14_200_000, "valor_garantia_cents": 10_000_000,
         "haircut_bp": 2000, "coste_ejecucion_cents": 200_000},
        {"prestamo": "P2", "ead_cents": 8_000_000, "valor_garantia_cents": 3_000_000,
         "haircut_bp": 5000, "coste_ejecucion_cents": 100_000},
        {"prestamo": "P3", "ead_cents": 27_500_000, "valor_garantia_cents": 30_000_000,
         "haircut_bp": 3000, "coste_ejecucion_cents": 1_000_000},
    ]


def garantias_contagio():
    """Garantías compartidas: el garante también puede haber caído."""
    return [
        {"prestamo": "P1", "valor_garantia_cents": 10_000_000,
         "haircut_bp": 2000, "garante_incumplido": 1, "contagio_bp": 3000},
        {"prestamo": "P2", "valor_garantia_cents": 5_000_000,
         "haircut_bp": 1000, "garante_incumplido": 0, "contagio_bp": 3000},
        {"prestamo": "P3", "valor_garantia_cents": 2_000_000,
         "haircut_bp": 0, "garante_incumplido": 1, "contagio_bp": 3000},
    ]


def estados():
    """Cura, castigo y venta: el estado decide si hay pérdida."""
    return [
        {"prestamo": "P1", "estado": "CURA", "ead_cents": 10_000_000,
         "recuperacion_cents": 9_000_000},
        {"prestamo": "P2", "estado": "CASTIGO", "ead_cents": 8_000_000,
         "recuperacion_cents": 2_000_000},
        {"prestamo": "P3", "estado": "VENTA", "ead_cents": 20_000_000,
         "recuperacion_cents": 15_000_000},
        {"prestamo": "P4", "estado": "CURA", "ead_cents": 5_000_000,
         "recuperacion_cents": 4_000_000},
        {"prestamo": "P5", "estado": "CASTIGO", "ead_cents": 4_000_000,
         "recuperacion_cents": 3_200_000},
    ]


def cartera():
    """EAD y pérdida ya calculada, para la LGD ponderada por segmento."""
    return [
        {"prestamo": "P1", "segmento": "Hipoteca", "ead_cents": 14_200_000,
         "perdida_cents": 6_000_000},
        {"prestamo": "P2", "segmento": "Consumo", "ead_cents": 8_000_000,
         "perdida_cents": 6_100_000},
        {"prestamo": "P3", "segmento": "Hipoteca", "ead_cents": 27_500_000,
         "perdida_cents": 6_300_000},
        {"prestamo": "P4", "segmento": "Consumo", "ead_cents": 6_600_000,
         "perdida_cents": 2_400_000},
    ]
