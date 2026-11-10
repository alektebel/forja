/* Etapa 6 — LGD: recuperación neta sobre EAD, con los dos topes. */
data work.lgd;
  set lgd_base;
  recuperacion_neta_cents = mrp_cents + recuperacion_final_cents
    + gasto_repercutido_cobrado_cents - coste_directo_cents;
  lgd_bp = 10000 - int(recuperacion_neta_cents * 10000 / ead_cents);
  if lgd_bp < 0 then lgd_bp = 0;
  if lgd_bp > 10000 then lgd_bp = 10000;
  keep prestamo lgd_bp;
run;
