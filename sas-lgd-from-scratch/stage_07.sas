/* Etapa 7 — LGD por préstamo.
   recuperacion_neta = MRP + recuperación final + repercutido cobrado - coste.
   LGD en pb = 10000 - int(recuperacion_neta * 10000 / ead).
   TODO: calcula y aplica los topes 0..10000. */
data work.lgd;
  set lgd_base;
  lgd_bp = 0;
  keep prestamo lgd_bp;
run;
