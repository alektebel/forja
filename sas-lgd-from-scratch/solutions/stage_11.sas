/* Etapa 11 — LGD ponderada por EAD, no promedio simple de LGD. */
proc means data=cartera noprint;
  class segmento;
  var ead_cents perdida_cents;
  output out=work.cartera_resumen
    sum=ead_total_cents perdida_total_cents;
run;

data work.cartera_lgd;
  set work.cartera_resumen;
  lgd_bp = int(perdida_total_cents * 10000 / ead_total_cents);
  keep segmento lgd_bp;
run;
