/* Etapa 1 — EAD: lo dispuesto más la parte no dispuesta que se convierte. */
data work.ead;
  set portfolio;
  if incumplido = 1;
  ead_cents = dispuesto_cents + int(no_dispuesto_cents * ccf_bp / 10000);
  keep prestamo segmento ead_cents;
run;
