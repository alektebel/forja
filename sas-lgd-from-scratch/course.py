"""SAS y LGD: del expediente al número que provisiona el banco.

Curso de once etapas sobre una cartera pequeña, escrito para quien ya sabe
mirar un balance pero todavía no ha tenido que defender una LGD delante de un
comité. El lenguaje es SAS: cada etapa se resuelve con un DATA step o un PROC
que el corrector ejecuta de verdad, no con una respuesta escrita en Python.

La regla del curso: una etapa, una decisión. El EAD no se mezcla con los
gastos; los gastos añadidos no se mezclan con los repercutidos; el MRP no se
resta dos veces; la garantía no vale lo mismo si el garante también cayó. Cada
etapa tiene su propia tabla de entrada, así que se puede hacer en cualquier
orden, aunque el orden propuesto cuenta la historia de un expediente.

Todo el dinero va en céntimos y todos los tipos en puntos básicos. No hay
float, no hay reloj, no hay red. El contrato de cada etapa está en `action`,
`predict` y `hints`; la verdad está en las tablas de `world.py`.

    python3 codecraft/cli.py run sas-lgd-from-scratch
"""

import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import sasmini
import world
from codecraft.api import stage

TITLE = "SAS y LGD From Scratch"
DESCRIPTION = (
    "Once etapas de SAS para calcular una LGD defendible: EAD, MRP, gastos "
    "añadidos y repercutidos, merge uno a uno, recuperación neta, descuento "
    "de flujos, garantías con haircut, contagio del garante, cura contra "
    "castigo y LGD ponderada por EAD. Cada etapa es un DATA step o un PROC "
    "que se ejecuta; cada número está en céntimos y puntos básicos."
)
LEVEL = "advanced"
ORDER = 43


def _run(filename, tables):
    """Ejecuta el SAS del alumno y devuelve sus tablas."""
    try:
        return sasmini.run_file(
            Path(HERE) / filename,
            {name: sasmini.Table(rows) for name, rows in tables.items()},
        )
    except sasmini.SasError as exc:
        raise AssertionError(f"{filename}: el SAS no compila — {exc}") from exc


def _table(result, name):
    if name not in result:
        raise AssertionError(
            f"falta la tabla work.{name}; el DATA step debe crearla con ese nombre")
    return result[name].rows


def check_1():
    rows = _table(_run("stage_01.sas", {"portfolio": world.portfolio()}), "ead")
    assert len(rows) == 4, f"esperaba cuatro préstamos incumplidos, hay {len(rows)}"
    got = {row["prestamo"]: row["ead_cents"] for row in rows}
    expected = {"P1": 14_000_000, "P2": 8_000_000,
                "P3": 27_500_000, "P4": 6_500_000}
    assert got == expected, f"EAD incorrecto: {got!r}; esperado {expected!r}"
    assert "P5" not in got, "P5 no está incumplido: el filtro debe excluirlo"


def check_2():
    rows = _table(_run("stage_02.sas", {"cashflows_mrp": world.cashflows_mrp()}),
                  "mrp_total")
    got = {row["prestamo"]: row["mrp_total_cents"] for row in rows}
    expected = {"P1": 300_000, "P2": 0, "P3": 1_500_000, "P4": 300_000}
    assert got == expected, f"MRP acumulado incorrecto: {got!r}; esperado {expected!r}"
    assert len(rows) == 4, "debe haber una fila por préstamo, no una por pago"
    assert got["P1"] == 300_000, "P1 tiene tres pagos: 100k + 150k + 50k"


def check_3():
    rows = _table(_run("stage_03.sas", {"ead_con_gastos": world.ead_con_gastos()}),
                  "ead_gastos")
    got = {row["prestamo"]: row["ead_final_cents"] for row in rows}
    expected = {"P1": 14_200_000, "P2": 8_000_000,
                "P3": 27_500_000, "P4": 6_600_000}
    assert got == expected, f"EAD con gastos incorrecto: {got!r}; esperado {expected!r}"
    assert got["P3"] == 27_500_000, (
        "P3 ya tenía el gasto dentro del dispuesto: sumarlo otra vez lo duplica")


def check_4():
    rows = _table(_run("stage_04.sas", {"repercutidos": world.repercutidos()}),
                  "repercutido_cobrado")
    got = [(row["prestamo"], row["recuperado_cents"]) for row in rows]
    expected = [("P1", 100_000), ("P1", 0), ("P2", 0), ("P3", 200_000), ("P4", 0)]
    assert sorted(got) == sorted(expected), f"gastos repercutidos incorrectos: {got!r}"
    assert sum(value for _, value in got) == 300_000, (
        "solo lo cobrado recupera: P1 deja 50k impagados y P4 deja 75k")


def check_5():
    rows = _table(_run("stage_05.sas", {
        "ead_base": world.ead_base(), "mrp_base": world.mrp_base(),
    }), "merge_ead_mrp")
    assert len(rows) == 4, f"el MERGE duplicó filas: hay {len(rows)}"
    got = {row["prestamo"]: (row["ead_cents"], row["mrp_total_cents"])
           for row in rows}
    expected = {
        "P1": (14_200_000, 300_000), "P2": (8_000_000, 0),
        "P3": (27_500_000, 1_500_000), "P4": (6_600_000, 300_000),
    }
    assert got == expected, f"merge incorrecto: {got!r}; esperado {expected!r}"


def check_6():
    rows = _table(_run("stage_06.sas", {"lgd_base": world.lgd_base()}), "lgd")
    got = {row["prestamo"]: row["lgd_bp"] for row in rows}
    expected = {"P1": 4226, "P2": 7625, "P3": 2291,
                "P4": 3637, "P5": 0, "P6": 10000}
    assert got == expected, f"LGD incorrecta: {got!r}; esperado {expected!r}"
    assert got["P5"] == 0, "P5 recupera más que el EAD: la LGD no puede ser negativa"
    assert got["P6"] == 10000, "P6 no recupera nada: la LGD no puede pasar de 10000 pb"


def check_7():
    rows = _table(_run("stage_07.sas", {"flujos": world.flujos()}), "flujos_vp")
    got = {(row["prestamo"], row["periodo"]): row["vp_cents"] for row in rows}
    expected = {
        ("P1", 1): 95_000, ("P1", 2): 180_000,
        ("P2", 1): 490_000, ("P3", 1): 800_000, ("P3", 2): 700_000,
    }
    assert got == expected, f"valor presente incorrecto: {got!r}; esperado {expected!r}"
    assert sum(got.values()) == 2_265_000, (
        "sumar los flujos sin descontar daría 2.8M: el tiempo importa")


def check_8():
    rows = _table(_run("stage_08.sas", {"garantias": world.garantias()}), "garantia")
    got = {row["prestamo"]: (row["recuperacion_cents"], row["lgd_bp"])
           for row in rows}
    expected = {
        "P1": (7_800_000, 4508),
        "P2": (1_400_000, 8250),
        "P3": (20_000_000, 2728),
    }
    assert got == expected, f"garantía incorrecta: {got!r}; esperado {expected!r}"


def check_9():
    rows = _table(_run("stage_09.sas", {
        "garantias_contagio": world.garantias_contagio(),
    }), "contagio")
    got = {row["prestamo"]: row["recuperacion_cents"] for row in rows}
    expected = {"P1": 5_600_000, "P2": 4_500_000, "P3": 1_400_000}
    assert got == expected, f"contagio incorrecto: {got!r}; esperado {expected!r}"
    assert got["P1"] < 8_000_000, "P1 tiene garante incumplido: el haircut no basta"
    assert got["P2"] == 4_500_000, "P2 no tiene contagio: el haircut es el único ajuste"


def check_10():
    rows = _table(_run("stage_10.sas", {"estados": world.estados()}), "estados_lgd")
    got = {row["prestamo"]: row["lgd_bp"] for row in rows}
    expected = {"P1": 0, "P2": 7500, "P3": 2500, "P4": 0, "P5": 2000}
    assert got == expected, f"cura/castigo incorrecto: {got!r}; esperado {expected!r}"
    assert got["P1"] == 0 and got["P4"] == 0, (
        "una cura devuelve el préstamo a cumplimiento: no genera LGD")


def check_11():
    rows = _table(_run("stage_11.sas", {"cartera": world.cartera()}), "cartera_lgd")
    got = {row["segmento"]: row["lgd_bp"] for row in rows}
    expected = {"Hipoteca": 2949, "Consumo": 5821}
    assert got == expected, f"LGD ponderada incorrecta: {got!r}; esperado {expected!r}"
    assert got["Hipoteca"] != 2114, (
        "2114 es el promedio simple de las LGD de Hipoteca; la cartera se pondera por EAD")


STAGES = [
    stage(
        1, file="stage_01.sas",
        title="EAD: lo dispuesto y lo que aún puede disponerse",
        tags=["sas", "data-step", "ead", "ccf"],
        action="Escribe stage_01.sas: filtra los incumplidos y calcula ead_cents = "
               "dispuesto_cents + int(no_dispuesto_cents * ccf_bp / 10000). "
               "Deja prestamo, segmento y ead_cents.",
        predict="¿Cuánto EAD tiene P1, que debe 12M y puede disponer 4M con CCF 50%?",
        hints=["El CCF convierte el no dispuesto en exposición: 5000 pb son la mitad.",
               "int() trunca; no uses round() para el EAD.",
               "if incumplido = 1; no es una asignación: es un filtro de filas."],
        check=check_1,
    ),
    stage(
        2, file="stage_02.sas",
        title="MRP: pagos parciales con RETAIN y LAST",
        tags=["sas", "retain", "by-group", "mrp"],
        action="Ordena cashflows_mrp por prestamo y periodo. Acumula mrp_cents en "
               "mrp_total_cents con RETAIN; reinicia en FIRST.prestamo y emite solo "
               "en LAST.prestamo. Una fila por préstamo.",
        predict="P1 paga 100k, 150k y 50k. ¿Qué total sale y por qué no se emite tres veces?",
        hints=["RETAIN conserva el valor entre iteraciones; sin él, cada fila empieza de cero.",
               "FIRST.prestamo y LAST.prestamo existen solo si declaras BY prestamo.",
               "La suma automática `total + importe;` ya implica RETAIN."],
        check=check_2,
    ),
    stage(
        3, file="stage_03.sas",
        title="Gastos añadidos: capitalizar sin duplicar",
        tags=["sas", "if-then-else", "gastos", "ead"],
        action="Calcula ead_final_cents. Si ya_en_dispuesto = 0, suma el gasto "
               "añadido; si ya estaba dentro del dispuesto, no lo sumes. Conserva "
               "prestamo y ead_final_cents.",
        predict="P3 tiene 27.5M de EAD y 300k de gasto ya incluido. ¿Cuál es su EAD final?",
        hints=["El gasto añadido no es un ingreso ni una recuperación: es más exposición.",
               "ya_en_dispuesto es la bandera que evita contar dos veces el mismo gasto.",
               "IF/THEN/ELSE en SAS termina con punto y coma; el ELSE mira la misma fila."],
        check=check_3,
    ),
    stage(
        4, file="stage_04.sas",
        title="Gastos repercutidos: solo lo cobrado recupera",
        tags=["sas", "if", "gastos", "recovery"],
        action="Asigna recuperado_cents: si cobrado = 1, el gasto repercutido; si "
               "no, cero. Conserva una fila por flujo, con prestamo y recuperado_cents.",
        predict="P1 repercute 100k cobrados y 50k impagados. ¿Cuánto entra en la LGD?",
        hints=["Repercutir no es cobrar: el derecho a cobrar no mueve caja.",
               "La recuperación es caja cobrada, no factura emitida.",
               "No sumes las filas de P1 aquí: la etapa 2 ya enseñó a acumular."],
        check=check_4,
    ),
    stage(
        5, file="stage_05.sas",
        title="MERGE uno a uno: el MRP no multiplica el EAD",
        tags=["sas", "merge", "by", "mrp"],
        action="Ordena ead_base y mrp_base por prestamo y haz un MERGE por esa clave. "
               "Deja prestamo, ead_cents y mrp_total_cents. El EAD no se toca y no "
               "pueden aparecer filas duplicadas.",
        predict="Si el MERGE no lleva BY prestamo, ¿qué le pasa a un préstamo con dos MRP?",
        hints=["MERGE sin BY pega por posición; con BY pega por clave.",
               "El MRP se une al EAD, no se suma al EAD: son dos columnas distintas.",
               "Comprueba el número de filas: un MERGE mal hecho lo delata."],
        check=check_5,
    ),
    stage(
        6, file="stage_06.sas",
        title="La LGD: recuperación neta sobre EAD",
        tags=["sas", "lgd", "arithmetic", "caps"],
        action="Calcula recuperacion_neta_cents = MRP + recuperación final + "
               "repercutido cobrado - coste directo. Luego lgd_bp = 10000 - "
               "int(recuperacion_neta_cents * 10000 / ead_cents), con topes 0 y 10000.",
        predict="P1 tiene EAD 14.2M y recupera 8.2M netos. ¿Qué LGD en pb sale?",
        hints=["El coste directo resta de la recuperación; no se suma al EAD.",
               "Multiplica por 10000 antes de dividir para no perder los pb.",
               "P5 recupera de más y P6 no recupera: los topes existen para esos dos."],
        check=check_6,
    ),
    stage(
        7, file="stage_07.sas",
        title="Descontar cada flujo a su fecha",
        tags=["sas", "discounting", "cashflow", "lgd"],
        action="Calcula vp_cents = int(importe_cents * factor_bp / 10000) para cada "
               "flujo, conservando prestamo, periodo y vp_cents. No sumes el nominal.",
        predict="Un flujo de 200k con factor 9000 pb y otro de 100k con 9500: ¿suman 300k?",
        hints=["El factor ya viene del área de tesorería: no lo recalcules con tipos.",
               "Cada periodo tiene su factor; descontar el total una sola vez es el error.",
               "El valor presente se suma después, cuando la etapa lo pida."],
        check=check_7,
    ),
    stage(
        8, file="stage_08.sas",
        title="Garantía: haircut y coste de ejecución",
        tags=["sas", "collateral", "haircut", "lgd"],
        action="Calcula recuperacion_cents = int(valor_garantia_cents * "
               "(10000 - haircut_bp) / 10000) - coste_ejecucion_cents. Después "
               "lgd_bp = 10000 - int(recuperacion_cents * 10000 / ead_cents), con topes.",
        predict="Una garantía de 10M con haircut 20% y coste 200k: ¿cuánto recupera?",
        hints=["El haircut se aplica al valor de la garantía, no al EAD.",
               "Ejecutar la garantía cuesta: ese coste reduce la recuperación.",
               "El coste no puede llevar la LGD fuera de 0..10000."],
        check=check_8,
    ),
    stage(
        9, file="stage_09.sas",
        title="Contagio del garante: la misma garantía vale menos",
        tags=["sas", "contagion", "guarantee", "if"],
        action="Aplica primero el haircut. Si garante_incumplido = 1, aplica también "
               "contagio_bp a la recuperación; si no, déjala en el valor con haircut. "
               "Deja prestamo y recuperacion_cents.",
        predict="P1 tiene garantía de 10M, haircut 20% y contagio 30%. ¿Recupera 8M u 5.6M?",
        hints=["El contagio no es un gasto: es una caída del valor esperado de la garantía.",
               "Aplica los dos porcentajes en secuencia; no los sumes.",
               "Solo el garante incumplido activa el segundo ajuste."],
        check=check_9,
    ),
    stage(
        10, file="stage_10.sas",
        title="Cura contra castigo: no toda salida es pérdida",
        tags=["sas", "cure", "write-off", "lgd"],
        action="Si estado = 'CURA', lgd_bp = 0. En cualquier otro estado, calcula "
               "lgd_bp = 10000 - int(recuperacion_cents * 10000 / ead_cents). "
               "Conserva prestamo y lgd_bp.",
        predict="P1 está en CURA y solo ha recuperado 9M de 10M. ¿Su LGD es 1000 pb o 0?",
        hints=["CURA devuelve el préstamo a cumplimiento: la pérdida esperada se extingue.",
               "CASTIGO y VENTA sí se miden contra la recuperación cash.",
               "IF/THEN/ELSE compara texto con comillas simples: 'CURA'."],
        check=check_10,
    ),
    stage(
        11, file="stage_11.sas",
        title="LGD de cartera: ponderar por EAD",
        tags=["sas", "proc-means", "weighted", "portfolio"],
        action="Suma ead_cents y perdida_cents por segmento con PROC MEANS y calcula "
               "lgd_bp = int(perdida_total_cents * 10000 / ead_total_cents). "
               "Deja segmento y lgd_bp.",
        predict="Hipoteca tiene dos préstamos con LGD distintas. ¿Por qué el promedio "
                "simple no es la LGD del segmento?",
        hints=["La LGD de cartera es pérdida total sobre EAD total, no media de ratios.",
               "PROC MEANS puede sumar varias variables y sacar una fila por CLASE.",
               "Revisa que el OUTPUT nombre las columnas que usará el DATA step."],
        check=check_11,
    ),
]
