/* Etapa 10 — Cura contra castigo.
   CURA no genera pérdida; CASTIGO y VENTA se calculan sobre la recuperación.
   TODO: usa IF/THEN/ELSE para asignar lgd_bp. */
data work.estados_lgd;
  set estados;
  lgd_bp = 10000;
  keep prestamo lgd_bp;
run;
