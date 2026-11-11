/* Etapa 1 — La LGD más simple.
   LGD en pb = (EAD - recuperación) / EAD * 10000.
   TODO: calcula lgd_bp. Todavía no hay gastos, MRP ni garantías. */
data work.lgd_simple;
  set lgd_simple;
  lgd_bp = 0;
  keep prestamo lgd_bp;
run;
