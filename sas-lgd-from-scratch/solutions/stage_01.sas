/* Etapa 1 — La LGD más simple: pérdida sobre EAD, sin adornos. */
data work.lgd_simple;
  set lgd_simple;
  lgd_bp = int((ead_cents - recuperacion_cents) * 10000 / ead_cents);
  keep prestamo lgd_bp;
run;
