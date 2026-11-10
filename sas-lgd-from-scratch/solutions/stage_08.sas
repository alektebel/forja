/* Etapa 8 — Garantía: haircut y coste de ejecución antes de recuperar. */
data work.garantia;
  set garantias;
  recuperacion_cents = int(valor_garantia_cents * (10000 - haircut_bp) / 10000)
    - coste_ejecucion_cents;
  lgd_bp = 10000 - int(recuperacion_cents * 10000 / ead_cents);
  if lgd_bp < 0 then lgd_bp = 0;
  if lgd_bp > 10000 then lgd_bp = 10000;
  keep prestamo recuperacion_cents lgd_bp;
run;
