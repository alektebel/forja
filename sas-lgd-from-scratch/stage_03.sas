/* Etapa 3 — MRP: pagos parciales.
   Ordena por prestamo y periodo, acumula con RETAIN y emite al LAST.
   TODO: completa la acumulación; hoy el total siempre vale cero. */
proc sort data=cashflows_mrp out=work.cf; by prestamo periodo; run;

data work.mrp_total;
  set work.cf;
  by prestamo;
  retain mrp_total_cents 0;
  if first.prestamo then mrp_total_cents = 0;
  /* TODO: suma mrp_cents al total */
  if last.prestamo then output;
  keep prestamo mrp_total_cents;
run;
