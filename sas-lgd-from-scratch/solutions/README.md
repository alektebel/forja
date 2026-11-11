# Soluciones

Cada `stage_NN.sas` resuelve la etapa correspondiente con el subconjunto de SAS
que implementa `sasmini.py`. No son la única forma: cualquier `DATA` step o
`PROC` que produzca las mismas columnas y los mismos valores pasa el corrector.

Para comprobar que las doce siguen pasando:

```bash
cd ..
python3 _build/run_mutations.py
```

Salida esperada al ejecutar las soluciones (céntimos y puntos básicos):

```text
etapa 1  lgd_simple:   S1=7000  S2=0  S3=10000
etapa 2  ead:          P1=14.000.000  P2=8.000.000  P3=27.500.000  P4=6.500.000
etapa 3  mrp_total:    P1=300.000     P2=0          P3=1.500.000   P4=300.000
etapa 4  ead_gastos:   P1=14.200.000  P2=8.000.000  P3=27.500.000  P4=6.600.000
etapa 5  repercutido:  P1=100.000+0   P2=0          P3=200.000     P4=0
etapa 6  merge:        P1=(14.2M,300k) P2=(8M,0)    P3=(27.5M,1.5M) P4=(6.6M,300k)
etapa 7  lgd_bp:       P1=4226  P2=7625  P3=2291  P4=3637  P5=0  P6=10000
etapa 8  flujos_vp:    P1=(95k,180k)  P2=490k  P3=(800k,700k)
etapa 9  garantia:     P1=(7.8M,4508) P2=(1.4M,8250) P3=(20M,2728)
etapa 10 contagio:     P1=5.600.000  P2=4.500.000  P3=1.400.000
etapa 11 estados_lgd:  P1=0  P2=7500  P3=2500  P4=0  P5=2000
etapa 12 cartera_lgd:  Hipoteca=2949  Consumo=5821
```

La etapa 5 conserva una fila por flujo; el `100.000+0` de P1 es la suma de sus
dos filas, no una fila con dos valores. La etapa 12 calcula la LGD del segmento
como pérdida total sobre EAD total; el promedio simple de Hipoteca daría 2114 pb
y el corrector lo rechaza.
