# SAS y LGD From Scratch

Doce etapas de SAS para calcular una LGD defendible, de lo simple a lo
complejo: primero la pérdida sobre EAD; después EAD, MRP, gastos añadidos y
repercutidos, unión uno a uno, recuperación neta, descuento de flujos,
garantías, contagio, cura contra castigo y, al final, la LGD ponderada de la
cartera.

**12 etapas.** Edita un `.sas` por etapa. El corrector ejecuta tu SAS.

## Etapa 0 — humo (menos de un minuto)

```bash
python3 codecraft/cli.py smoke sas-lgd-from-scratch
```

Debe decir `smoke OK`. Las plantillas producen tablas válidas pero incorrectas:
el primer fallo es de negocio, no de sintaxis.

## Etapa 1 — el primer cálculo

**Archivo:** `stage_01.sas` — la LGD más simple

Para cada préstamo, calcula
`lgd_bp = int((ead_cents - recuperacion_cents) * 10000 / ead_cents)`.
Deja `prestamo` y `lgd_bp`. Todavía no hay gastos, MRP ni garantías.

```bash
python3 codecraft/cli.py run sas-lgd-from-scratch
```

## El bucle

1. Lee `action`, `predict` y las pistas de la etapa.
2. Edita el `.sas` en tu editor.
3. Ejecuta el curso.
4. Lee la causa del fallo.
5. Predice el número antes de volver a ejecutar.

Cada etapa tiene su propia tabla: puedes hacer la 10 sin haber hecho la 6. El
orden propuesto va de la idea más simple a la cartera completa.

## Convenciones

- Céntimos y puntos básicos; nunca `float`.
- `int()` trunca; el corrector fija el valor exacto.
- MRP significa **monto recuperado parcial** en este curso.
- No edites `world.py`: es el contrato de datos.
