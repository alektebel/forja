/* Etapa 4 — Gasto añadido: se capitaliza solo si no estaba ya en el dispuesto. */
data work.ead_gastos;
  set ead_con_gastos;
  if ya_en_dispuesto = 0 then
    ead_final_cents = ead_cents + gasto_anadido_cents;
  else
    ead_final_cents = ead_cents;
  keep prestamo ead_final_cents;
run;
