/* Etapa 9 — Contagio del garante.
   Primero aplica el haircut; si garante_incumplido = 1, aplica contagio_bp.
   TODO: reduce la recuperación solo en el caso de contagio. */
data work.contagio;
  set garantias_contagio;
  recuperacion_cents = 0;
  keep prestamo recuperacion_cents;
run;
