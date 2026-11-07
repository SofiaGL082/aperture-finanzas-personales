# Limpieza y conversión histórica: resultados y decisiones

## Fuentes y alcance

Se inspeccionó el repositorio abierto en VS Code y se reutilizaron el núcleo, los importadores y el EDA existente. El notebook aportado personal-finance-project.ipynb contiene dos celdas: lectura del Excel en una ruta Kaggle y exportación a CSV. Esa exportación no constituye limpieza ni validación. No se ejecutó el notebook aportado ni se usó su ruta Kaggle como ruta local.

El prompt aportado termina en la sección de categorías, después de la palabra «Gasto». Se implementaron los requisitos visibles y el objetivo explícito de EDA, limpieza, conversión histórica y preparación para SQLite.

## Moneda del Excel: pendiente de verificación

Se consultó el endpoint oficial de metadatos de Kaggle del dataset entrepreneurlife/personal-finance. La respuesta original está en reports/eda/fuentes/kaggle_personal_finance_metadata.json. La descripción no declara USD ni otra moneda. Las 806 celdas Amount tienen formato General y el notebook aportado tampoco declara moneda.

Por tanto, las 806 filas se conservan con original_currency=NULL, amount_cop_minor=NULL y conversion_status=unidentified_currency. USD sigue siendo una hipótesis del importador de demostración; esa hipótesis no se utiliza en esta preparación. Se necesita una fuente verificable del autor para desbloquear la conversión. No debe sustituirse NULL por cero ni sumar un total COP incompleto.

## CSV: conversión aplicada

Se conservaron y convirtieron 277 filas: 276 INR y una USD, utilizando cada moneda original y su fecha original. No se usó la fecha desplazada de demostración. La operación USD se convirtió directamente USD/COP; la columna INR de la fuente se mantiene como equivalente documentado independiente, no como tasa histórica externa.

Se utilizaron respuestas históricas de Frankfurter v2 con información de proveedores. Son tasas de referencia blended, no tasas bancarias efectivas ni una TRM certificada. No incluyen comisiones, inflación ni diferencias de poder adquisitivo. La conversión a COP no convierte a una persona o hábito extranjero en un perfil colombiano.

Política: tasa del mismo día o última observación anterior con antigüedad máxima de siete días; nunca una tasa futura. Respuestas guardadas con URL, fecha de consulta y SHA-256. Lectura con Decimal y redondeo HALF_UP a centavos COP una sola vez. Se aplicaron 86 combinaciones distintas de moneda/fecha/tasa.

Se conservaron 78 filas con una o varias señales de revisión: coincidencia en clave amplia o notas ambiguas, entre otras. Esto no demuestra error y no produce borrado ni reclasificación automática como préstamo. El estado de conversión es independiente del estado de revisión semántica.

## Preparación y esquema

Una fila preparada por cada fila original: 1.083 en total. transaction_uid deriva de hash de fuente y posición original; dataset_id y profile_ref mantienen separados los dos conjuntos. Se conservan fecha original, fecha demo opcional vacía, tipo original, categoría original, categoría normalizada, importe decimal original, unidades menores si la moneda es conocida, moneda, COP, tasa, fecha de tasa, fuente y consulta.

Las cuentas se seudonimizan mediante referencia determinista. Esto NO es anonimización completa; descripciones, fechas e importes siguen siendo sensibles. Los archivos derivados quedan en data/processed/, ignorada por Git.

La base preparacion.sqlite se crea exclusivamente en un directorio nuevo por ejecución. No reemplaza ni recibe una conexión a la base operativa. El SQL se mantiene en core/repositorio.py. La carga en la aplicación no se realiza automáticamente: primero se deben resolver moneda y revisiones pendientes. Las marcas de transferencia son candidatas para conciliación, no una reconstrucción completa de saldos por cuenta.

## Reproducción

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-eda.txt
.\.venv\Scripts\python.exe -m scripts.eda_datasets
.\.venv\Scripts\python.exe -m scripts.preparar_datasets
# Repetir sin consultar Internet cuando ya existe la caché:
.\.venv\Scripts\python.exe -m scripts.preparar_datasets --offline
.\.venv\Scripts\python.exe -m pytest -q
```

El manifiesto más reciente está en reports/eda/preparacion_manifest.json. Cada ejecución produce un directorio independiente, conservando los resultados anteriores. Los notebooks leen ese manifiesto; no consultan la red ni alteran las fuentes.

## Notebooks solicitados

- notebooks/01_eda_personal_finance.ipynb
- notebooks/02_eda_my_expenses.ipynb
- notebooks/03_comparacion_datasets.ipynb

Cada sección incluye objetivo, código, observaciones, interpretación e implicaciones. Los resultados textuales corresponden a los hashes auditados; si cambian los archivos hay que revisar también esas interpretaciones. Los gráficos pueden usar float para visualización; los importes financieros definitivos y conversiones utilizan enteros y Decimal.

## Límites

No se entrenaron modelos ni se inventaron resultados predictivos. No se certifica completitud del historial, naturaleza real/sintética más allá de lo declarado por el autor, representatividad de la población, igualdad de poder adquisitivo ni calibración probabilística. No se hicieron commits, push ni merges.


## Verificación ejecutada

Tres notebooks ejecutados en kernel .venv: 20 celdas de código sin errores. Suite: 71 aprobadas, 0 fallidas. Base staging: 1.083 filas e integridad ok; 277 conversiones recalculadas fila a fila con Decimal. Preparación offline repetida correctamente.

Para registrar el kernel local: `.\.venv\Scripts\python.exe -m ipykernel install --prefix .venv --name fintwin-eda --display-name "Python (.venv FinTwin EDA)"`. Después ejecutar `python -m scripts.ejecutar_notebooks` con el intérprete de .venv.
