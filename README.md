# Simulación de cajeros de parqueadero — Centro Comercial Supercentro

Simulación de eventos discretos del sistema de pago de parqueaderos de Supercentro.
Cada punto de salida tiene **3 cajeros independientes** modelados como colas **M/M/1**
(filas independientes, sin cambio de fila ni deserción). El objetivo es determinar si
tres cajeros bastan para la demanda o se requieren más.

## Modelo

| Tipo de usuario | Servicio (media exp, min) | Llegada (media, min) | Proporción |
|-----------------|---------------------------|----------------------|------------|
| Rápido          | 1                         | 3                    | 25 %       |
| Normal          | 3                         | 3                    | 20 %       |
| Lento           | 4                         | 5                    | 30 %       |
| Muy lento       | 6                         | 7                    | 25 %       |

- Llegadas Poisson; tiempo de servicio exponencial según el tipo de usuario.
- El cliente se asigna de forma uniforme a uno de los 3 cajeros.
- 30 réplicas, horizonte de 6000 min cada una (~1300 clientes/réplica).

## Estructura del repositorio

| Archivo | Descripción |
|---------|-------------|
| `simulacion_parqueadero.py` | Simulador SimPy: corre las réplicas, detecta el estado estable (Welch), elimina el transitorio y genera las figuras y `resumen.json`. |
| `gen_docx.py` | Genera el documento Word con las 4 secciones (introducción, metodología, resultados, conclusiones). |
| `resumen.json` | Estadísticas numéricas de la corrida (entrada de los generadores de documentos). |
| `fig1..fig6_*.png` | Figuras Matplotlib del análisis. |
| `simulacion_30_problemaParqueadero.docx` | Documento entregable. |

## Metodología estadística

1. **Estado estable** — técnica de la media (Welch): promedio del tiempo en sistema `W`
   entre réplicas, alineado por cliente y suavizado con media móvil → fin del transitorio
   (warm-up). *(Fig 1)*
2. **Número de réplicas** — media acumulada de `W` con intervalo de confianza 95 % →
   30 réplicas suficientes. *(Fig 2)*
3. **Eliminación del transitorio** — se descartan los primeros clientes y se recalculan
   los promedios; gráfica antes/después. *(Fig 6)*
4. **Verificación y calibración** — las proporciones simuladas reproducen el 25/20/30/25 y
   los tiempos de servicio simulados coinciden con los teóricos 1/3/4/6 min. *(Fig 5)*

## Resultados principales

- Cajero con **menor** tiempo de atención: **Cajero 3** (~3.53 min). *(Fig 3)*
- Cajero con **mayor** tiempo de atención: **Cajero 1** (~3.61 min). *(Fig 3)*
- Promedio de usuarios por tipo en los 3 cajeros (por réplica): Rápido ≈ 317,
  Normal ≈ 256, Lento ≈ 383, Muy lento ≈ 319. *(Fig 4)*
- Espera media por cajero ≈ 1.6 min; utilización baja (ρ ≈ 0.26).
- **Decisión:** con criterio de utilización < 70 % y espera < 5 min, **tres cajeros por
  salida son suficientes**; no se requieren cajeros adicionales.

## Cómo ejecutar

Requisitos: Python 3.12, `numpy`, `simpy`, `matplotlib`, `python-docx`.

```bash
pip install numpy simpy matplotlib python-docx
python simulacion_parqueadero.py   # corre la simulación y genera figuras + resumen.json
python gen_docx.py                 # genera el documento Word
```

## Autor

Grupo de Simulación — Evidencia 4.
