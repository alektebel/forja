/* Etapa 8 — Valor presente de cada flujo.
   vp_cents = int(importe_cents * factor_bp / 10000).
   TODO: descuenta cada fila con su propio factor. */
data work.flujos_vp;
  set flujos;
  vp_cents = importe_cents;
  keep prestamo periodo vp_cents;
run;
