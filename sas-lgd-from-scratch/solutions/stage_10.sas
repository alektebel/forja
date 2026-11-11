/* Etapa 10 — Contagio: si el garante cayó, la garantía vale menos. */
data work.contagio;
  set garantias_contagio;
  recuperacion_garantia_cents = int(valor_garantia_cents * (10000 - haircut_bp) / 10000);
  if garante_incumplido = 1 then
    recuperacion_cents = int(recuperacion_garantia_cents * (10000 - contagio_bp) / 10000);
  else
    recuperacion_cents = recuperacion_garantia_cents;
  keep prestamo recuperacion_cents;
run;
