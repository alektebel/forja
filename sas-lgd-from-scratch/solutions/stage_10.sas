/* Etapa 10 — Cura contra castigo: la cura no genera pérdida. */
data work.estados_lgd;
  set estados;
  if estado = 'CURA' then
    lgd_bp = 0;
  else
    lgd_bp = 10000 - int(recuperacion_cents * 10000 / ead_cents);
  keep prestamo lgd_bp;
run;
