/* Etapa 5 — MERGE uno a uno: el MRP se une al EAD, no lo multiplica. */
proc sort data=ead_base out=work.ead_sorted; by prestamo; run;
proc sort data=mrp_base out=work.mrp_sorted; by prestamo; run;

data work.merge_ead_mrp;
  merge work.ead_sorted work.mrp_sorted;
  by prestamo;
  keep prestamo ead_cents mrp_total_cents;
run;
