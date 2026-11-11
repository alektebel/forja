/* Etapa 12 — LGD ponderada por EAD.
   Suma EAD y pérdida por segmento y divide: no promedies lgd_bp.
   TODO: completa PROC MEANS y calcula lgd_bp. */
proc means data=cartera noprint;
  class segmento;
  var ead_cents perdida_cents;
  output out=work.cartera_resumen
    sum=ead_total_cents perdida_total_cents;
run;

data work.cartera_lgd;
  set work.cartera_resumen;
  lgd_bp = 0;
  keep segmento lgd_bp;
run;
