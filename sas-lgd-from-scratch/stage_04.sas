/* Etapa 4 — Gastos repercutidos.
   Solo la parte cobrada es recuperación; la repercutida impagada no lo es.
   TODO: asigna recuperado_cents según cobrado. */
data work.repercutido_cobrado;
  set repercutidos;
  recuperado_cents = 0;
  keep prestamo recuperado_cents;
run;
