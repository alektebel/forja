/* Etapa 8 — Descontar cada flujo por su propio factor, no el total. */
data work.flujos_vp;
  set flujos;
  vp_cents = int(importe_cents * factor_bp / 10000);
  keep prestamo periodo vp_cents;
run;
