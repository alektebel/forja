/* Etapa 1 — EAD al default.
   EAD = dispuesto + int(no_dispuesto * ccf_bp / 10000).
   Filtra incumplido = 1 y deja prestamo, segmento y ead_cents.
   TODO: sustituye el cero por la exposición calculada. */
data work.ead;
  set portfolio;
  if incumplido = 1;
  ead_cents = 0;
  keep prestamo segmento ead_cents;
run;
