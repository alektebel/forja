/* Etapa 3 — MRP: pagos parciales acumulados por préstamo. */
proc sort data=cashflows_mrp out=work.cf; by prestamo periodo; run;

data work.mrp_total;
  set work.cf;
  by prestamo;
  retain mrp_total_cents 0;
  if first.prestamo then mrp_total_cents = 0;
  mrp_total_cents + mrp_cents;
  if last.prestamo then output;
  keep prestamo mrp_total_cents;
run;
