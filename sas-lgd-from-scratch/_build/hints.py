"""Pistas de autor para sas-lgd-from-scratch.

No son las pistas que ve el alumno: esas viven en `course.py`. Esta tabla
existe para que quien revise el curso sepa qué mecanismo enseña cada etapa y
qué línea del SAS es la que no se puede regalar. Si una pista se convierte en
código, la etapa deja de ser un ejercicio.

Cada entrada apunta al archivo de solución y nombra las construcciones SAS que
el check mide.
"""

HINTS = {
    "stage_01.sas": {
        "cociente": "(ead_cents - recuperacion_cents) / ead_cents: la LGD es lo que no vuelve.",
        "pb": "multiplica por 10000 antes de dividir; int() trunca.",
        "extremos": "S2 da 0 pb y S3 da 10000 pb; no hacen falta topes todavía.",
    },
    "stage_02.sas": {
        "filtro": "if incumplido = 1; descarta P5 antes de calcular nada.",
        "ccf": "int(no_dispuesto_cents * ccf_bp / 10000): el CCF se aplica al no dispuesto.",
        "suma": "EAD = dispuesto + no dispuesto convertido; no descuentes recuperaciones aquí.",
    },
    "stage_03.sas": {
        "sort": "PROC SORT por prestamo y periodo; BY necesita orden.",
        "retain": "RETAIN conserva mrp_total_cents entre filas.",
        "first": "if first.prestamo then total = 0; solo reinicia al abrir el grupo.",
        "last": "if last.prestamo then output; emite una fila por préstamo, no por pago.",
        "suma": "mrp_total_cents + mrp_cents; es la suma automática de SAS y ya retiene.",
    },
    "stage_04.sas": {
        "bandera": "ya_en_dispuesto = 1 significa que el gasto ya está dentro del EAD.",
        "if": "IF/THEN/ELSE capitaliza solo el gasto que no estaba dispuesto.",
        "no_duplicar": "sumar siempre convertiría P3 en 27.8M: el check lo delata.",
    },
    "stage_05.sas": {
        "cobro": "cobrado = 1 es la única condición que convierte el gasto en recuperación.",
        "factura": "gasto_repercutido_cents es el derecho; recuperado_cents es la caja.",
        "cero": "lo no cobrado se queda en cero, no resta de la recuperación.",
    },
    "stage_06.sas": {
        "sort": "ambos datasets deben llegar ordenados por prestamo.",
        "merge": "MERGE con BY prestamo pega por clave; sin BY pega por posición.",
        "filas": "cuatro préstamos, cuatro filas: un MERGE mal hecho duplica P1.",
        "columnas": "ead_cents y mrp_total_cents conviven; el MRP no se suma al EAD.",
    },
    "stage_07.sas": {
        "recuperacion": "MRP + recuperación final + repercutido cobrado - coste directo.",
        "ratio": "multiplica por 10000 antes de dividir para conservar puntos básicos.",
        "topes": "P5 exige el tope inferior 0 y P6 el superior 10000.",
    },
    "stage_08.sas": {
        "factor": "cada flujo usa su factor_bp; no hay un factor único de cartera.",
        "vp": "int(importe_cents * factor_bp / 10000) trunca el valor presente.",
        "tiempo": "sumar nominales daría 2.8M; el descuento produce 2.265M.",
    },
    "stage_09.sas": {
        "recorte": "el recorte se aplica al valor de la garantía, no al EAD.",
        "coste": "coste_ejecucion_cents se resta de la recuperación.",
        "lgd": "LGD = 10000 - recuperación/EAD en pb, con topes 0 y 10000.",
    },
    "stage_10.sas": {
        "secuencia": "primero recorte; después, solo si el garante cayó, contagio.",
        "contagio": "aplicar contagio siempre castigaría a P2, cuyo garante sigue sano.",
        "producto": "los dos porcentajes se multiplican en secuencia, no se suman.",
    },
    "stage_11.sas": {
        "cura": "estado = 'CURA' devuelve el préstamo a cumplimiento: LGD 0.",
        "castigo": "CASTIGO y VENTA sí se miden contra la recuperación en efectivo.",
        "texto": "las comillas simples son parte de la comparación SAS.",
    },
    "stage_12.sas": {
        "proc_means": "PROC MEANS con CLASS segmento y OUTPUT SUM crea una fila por segmento.",
        "ponderacion": "LGD = pérdida total / EAD total del segmento, no media de LGD.",
        "error": "el promedio simple de Hipoteca da 2114 pb; la respuesta correcta es 2949.",
    },
}
