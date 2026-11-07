# EDA inicial y decisión sobre los datos

Fecha de revisión: 6 de noviembre de 2026. Se inspeccionaron los archivos originales del repositorio real. No se entrenaron modelos. Los hashes SHA-256 se conservaron en quality_summary.json y se verificaron antes y después del análisis.

## Calidad estructural

| Comprobación | Personal Finance (Excel) | My Expenses (CSV) |
| --- | --- | --- |
| Registros / columnas | 806 / 7 | 277 / 11 |
| Fechas | 2018-01-01 a 2019-09-30 | 2021-11-21 a 2022-03-02 |
| Campos esenciales vacíos | Ninguno | Ninguno en fecha, monto, tipo y categoría |
| Otros faltantes | Ninguno | Subcategory y Note.1: 277 cada una; Note: 4 |
| Fechas inválidas | 0 | 0 |
| Montos inválidos, cero o negativos | 0 | 0 |
| Duplicados exactos | 0 | 0 |
| Coincidencias de clave amplia para revisar | 0 | 23 filas |
| Periodos mensuales tocados | 21 | 5: noviembre y marzo parciales |
| Semanas enteras dentro de límites de fechas | 91 | 14 |
| Moneda | No declarada en el archivo | 276 INR y 1 USD |

Una coincidencia de fecha, importe, tipo y cuenta no demuestra duplicación. Las 23 filas del CSV podrían ser compras distintas; no se borraron. No se imputaron valores, no se eliminaron atípicos y no se alteraron las fechas originales para este EDA.

## Hallazgos financieros y semánticos

### Excel

- 688 débitos y 118 créditos.
- 143 movimientos tienen categoría Credit Card Payment. Son candidatos a transferencias/pagos entre cuentas, no consumo adicional. Se excluyen de los gráficos de gasto de este EDA.
- Hay 72 créditos y 71 débitos de esa categoría. Un emparejamiento muy estricto por día e importe deja 97 patas sin pareja. Esto NO significa 97 registros faltantes: las fechas pueden diferir entre cuentas y las partidas pueden agruparse. Requiere conciliación con tolerancia temporal y revisión de cuentas antes de concluir sobre completitud.
- Todos los créditos fuera de pagos de tarjeta pertenecen a Paycheck en este archivo. No se observaron créditos en categorías de consumo.
- La columna Month concuerda con Date en todas las filas.
- USD es una hipótesis del importador de demostración, no una propiedad verificada dentro del Excel. Confirmar procedencia/moneda antes de interpretar cantidades o convertirlas.

### CSV

- 231 gastos y 46 ingresos según las etiquetas originales.
- Para los gráficos comparables se usa la columna INR: contiene un equivalente documentado para la operación de 15 USD (1120,72 INR). No se suman directamente Amount en USD y Amount en INR.
- 61 notas coinciden con expresiones como From, To, Took from o lend. Son candidatos a revisión de transferencias, préstamos, apoyos o devoluciones; una palabra no permite determinar con certeza su naturaleza.
- Subcategory y Note.1 pueden excluirse de una tabla analítica derivada. Note se mantiene como opcional; sus faltantes no justifican eliminar las transacciones.

## Cobertura y dispersión

No hay meses ni semanas interiores totalmente vacíos en estos archivos, pero no se puede demostrar que contengan todas las cuentas, gastos en efectivo o transacciones omitidas. Un día sin movimientos no equivale a un día sin consumo.

En el Excel, Mortgage & Rent aparece en 21 de 91 semanas interiores; Groceries, en 66; Restaurants, en 52. Son gastos con frecuencias distintas. Las categorías de mayor importe no son necesariamente las más adecuadas para una predicción semanal. Los ceros registrados y los gastos mensuales recurrentes requieren un tratamiento explícito.

El criterio IQR identifica importes grandes por categoría con al menos ocho registros. Son señales exploratorias, no errores ni fraude. No deben eliminarse automáticamente.

## Dictamen para APERTURE

1. Usar el Excel como candidato principal para un experimento exploratorio de gasto semanal, tras confirmar su moneda y conciliar pagos de tarjeta.
2. Usar el CSV como segundo caso de importación y análisis de calidad. Catorce semanas interiores son insuficientes para una comparación sólida de MLP con muchos rezagos y categorías.
3. Mantener los perfiles separados. Convertir monedas no vuelve equivalentes poblaciones, épocas o hábitos diferentes.
4. No presentar estas muestras como representativas de Colombia o de los estudiantes de la universidad.
5. Definir semanas lunes-domingo. Excluir del experimento las semanas de borde parciales y revisar las de cobertura dudosa.
6. Determinar categorías, escalado, imputación eventual y variables usando únicamente el entrenamiento de cada partición temporal.
7. Comparar primero última semana y promedio móvil con una regresión regularizada. Un MLP pequeño quedaría sujeto a suficiencia de datos; no se afirma que vaya a mejorar.
8. Monte Carlo debe declarar la estabilidad supuesta y preservar dependencia entre categorías. La calibración se evaluará solo en semanas reales posteriores.
9. Los sintéticos son exclusivamente para desarrollo y pruebas. No se usan como evidencia de precisión real.

## Reproducibilidad

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m scripts.eda_datasets --data-dir data/demo --output-dir reports/eda
```

Se generan un informe HTML interactivo, resumen JSON y tablas CSV de faltantes, cobertura mensual/semanal, categorías y gasto por categoría/semana. Las tablas analíticas del informe son resultados exploratorios; no son registros bancarios conciliados.

Notebook de apoyo: notebooks/01_EDA_datasets.ipynb. Los originales permanecen en su ubicación actual. No se hicieron commits ni push.
