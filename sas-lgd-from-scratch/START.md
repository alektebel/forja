# SAS y LGD From Scratch

Once etapas de SAS para calcular una LGD defendible: EAD, MRP, gastos
añadidos y repercutidos, unión uno a uno, recuperación neta, descuento de
flujos, garantías, contagio, cura contra castigo y LGD ponderada por EAD.

**11 etapas.** Edita un `.sas` por etapa. El corrector ejecuta tu SAS.

## Etapa 0 — humo (menos de un minuto)

```bash
python3 codecraft/cli.py smoke sas-lgd-from-scratch
```

Debe decir `smoke OK`. Las plantillas producen tablas válidas pero incorrectas:
el primer fallo es de negocio, no de sintaxis.

## Etapa 1 — el primer cálculo

**Archivo:** `stage_01.sas` — el EAD y el filtro de incumplidos

Filtra los préstamos incumplidos y calcula
`ead_cents = dispuesto_cents + int(no_dispuesto_cents * ccf_bp / 10000)`.
Deja `prestamo`, `segmento` y `ead_cents`.

```bash
python3 codecraft/cli.py run sas-lgd-from-scratch
```

## El bucle

1. Lee `action`, `predict` y las pistas de la etapa.
2. Edita el `.sas` en tu editor.
3. Ejecuta el curso.
4. Lee la causa del fallo.
5. Predice el número antes de volver a ejecutar.

Cada etapa tiene su propia tabla: puedes hacer la 9 sin haber hecho la 5. El
orden propuesto cuenta la historia completa de un expediente.

## Convenciones

- Céntimos y puntos básicos; nunca `float`.
- `int()` trunca; los checks fijan el valor exacto.
- MRP significa **monto recuperado parcial** en este curso.
- No edites `world.py`: es el contrato de datos.
