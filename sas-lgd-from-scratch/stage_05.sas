/* Etapa 5 — MERGE por préstamo.
   Une EAD y MRP por prestamo; el MRP no se suma al EAD ni duplica filas.
   TODO: completa el MERGE y conserva las tres columnas. */
proc sort data=ead_base out=work.ead_sorted; by prestamo; run;
proc sort data=mrp_base out=work.mrp_sorted; by prestamo; run;

data work.merge_ead_mrp;
  merge work.ead_sorted work.mrp_sorted;
  by prestamo;
  mrp_total_cents = 0;
  keep prestamo ead_cents mrp_total_cents;
run;
