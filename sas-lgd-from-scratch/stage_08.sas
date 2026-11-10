/* Etapa 8 — Garantía.
   recuperacion = int(valor * (10000 - haircut) / 10000) - coste_ejecucion.
   LGD = 10000 - int(recuperacion * 10000 / ead), con topes.
   TODO: calcula recuperación y LGD. */
data work.garantia;
  set garantias;
  recuperacion_cents = 0;
  lgd_bp = 10000;
  keep prestamo recuperacion_cents lgd_bp;
run;
