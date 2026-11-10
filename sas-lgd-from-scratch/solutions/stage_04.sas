/* Etapa 4 — Gasto repercutido: solo es recuperación si se cobró. */
data work.repercutido_cobrado;
  set repercutidos;
  if cobrado = 1 then recuperado_cents = gasto_repercutido_cents;
  else recuperado_cents = 0;
  keep prestamo recuperado_cents;
run;
