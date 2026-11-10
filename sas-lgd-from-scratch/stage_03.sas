/* Etapa 3 — Gastos añadidos.
   Si ya_en_dispuesto = 0, el gasto se capitaliza; si no, ya estaba dentro.
   TODO: calcula ead_final_cents sin duplicar el gasto. */
data work.ead_gastos;
  set ead_con_gastos;
  ead_final_cents = ead_cents;
  keep prestamo ead_final_cents;
run;
