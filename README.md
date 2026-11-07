# aperture-finanzas-personales

Aplicación web para registrar ingresos y gastos, ver cómo cambian mes a mes y
saber **en cuántos meses se logra una meta de ahorro y qué recortar para
lograrla antes**. Proyecto de la Competencia de Proyectos 2026-2 del
semillero Aperture (línea de inteligencia artificial y sistemas inteligentes).

Todo el proyecto usa herramientas gratuitas: Python, Streamlit, SQLite,
pandas, NumPy, Plotly y pytest.

## Cómo correrla

Requisitos: Python 3.11, 3.12 o 3.13 y git.

```bash
git clone https://github.com/<usuario>/aperture-finanzas-personales.git
cd aperture-finanzas-personales

python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# macOS / Linux:         source .venv/bin/activate

pip install -r requirements.txt
pytest -q                 # deben pasar todas las pruebas
streamlit run app.py      # abre http://localhost:8501
```

Para tener datos desde el primer momento, descarguen los datasets de Kaggle
en `data/demo/` (instrucciones en [data/demo/README.md](data/demo/README.md))
y usen el botón "Cargar datos de demostración" o:

```bash
python -m scripts.cargar_demo
```

Para ensayar la demo con una fecha fija: `FINTWIN_HOY=2026-11-23 streamlit run app.py`
(en PowerShell: `$env:FINTWIN_HOY="2026-11-23"; streamlit run app.py`).

## Qué hace

| Pantalla | Para qué |
| --- | --- |
| Inicio | Resumen del último mes completo y avance de las metas |
| Registrar | Anotar ingresos, gastos, transferencias entre cuentas propias y préstamos |
| Historial | Buscar, corregir y borrar movimientos |
| Reporte mensual | El mes frente al anterior y frente a lo habitual (mediana de 3 meses), con alertas |
| Metas de ahorro | Meses estimados para llegar, rango con meses buenos y malos, y plan de recortes si hay fecha límite |

## Arquitectura

```
app.py                  punto de entrada: navegación y barra lateral
interfaz/               todo lo que se ve (Streamlit + Plotly)
  paginas/              una pantalla por archivo
  estado.py             conexión a la base y usuario activo
  ui.py, graficos.py    piezas visuales reutilizables
core/                   la lógica, sin Streamlit
  dominio.py            tipos: Movimiento, Meta, Categoria...
  categorias.py         catálogo y cuáles son recortables
  repositorio.py        única puerta a SQLite (con migraciones)
  reportes.py           resumen mensual y comparaciones
  metas.py              meses estimados y rango simulado
  recomendaciones.py    plan de recortes
  formato.py            dinero y fechas en español
  importadores/         datasets de Kaggle -> movimientos
scripts/cargar_demo.py  carga los datasets desde la terminal
tests/                  pruebas de core (pytest)
data/demo/              datasets públicos de Kaggle (se suben)
data/raw/               extractos reales (git los ignora)
```

Tres reglas que mantienen el código ordenado:

1. **`core/` nunca importa Streamlit.** Así la lógica se prueba sola y, si
   después hacen una API o una app móvil, se reutiliza completa.
2. **Solo `repositorio.py` escribe SQL.** Las pantallas piden y guardan datos
   a través de él. Para cambiar el esquema, agreguen una migración al final
   de `_MIGRACIONES`; nunca editen una que ya se aplicó.
3. **El dinero se guarda en centavos enteros.** Nunca floats: así los totales
   siempre cuadran.

## Decisiones del modelo

- **Ahorro típico = mediana** del ahorro (ingresos − gastos) de los últimos
  12 meses completos. El mes en curso no cuenta porque va a medias.
- **Meses estimados = techo(faltante ÷ ahorro típico).**
- **Rango:** se simulan 4.000 futuros tomando al azar meses del propio
  historial (bootstrap) y se reportan los percentiles 10 y 90.
- **Con menos de 3 meses** de registros la app pide un ahorro aproximado y
  marca la estimación como orientativa.
- **Recortes:** el faltante mensual se reparte con el mismo porcentaje entre
  las categorías recortables que la persona elija, con un tope del 30 % por
  categoría. Vivienda, mercado, transporte, salud, educación y deudas nunca
  se tocan. Igual porcentaje = el recorte más grande es el menor posible.
- **Transferencias y préstamos** no cuentan como ingreso ni gasto.

## Cómo trabajamos

- Una rama por tarea (`registro`, `reporte-graficos`...). Nunca se trabaja
  directo en `main`.
- Pull request a `main`; la otra integrante lo revisa antes de unirlo.
  GitHub Actions corre las pruebas en cada pull request.
- Cada función nueva de `core/` llega con su prueba en `tests/`.

## Privacidad

Los datos se guardan en `data/fintwin.db`, solo en el computador de cada una
(git ignora las bases de datos). La demo publicada en Streamlit Community
Cloud debe usar solo los datasets de demostración, nunca extractos reales.# aperture-finanzas-personales

Asistente de finanzas personales: proyección y simulación (Monte Carlo) del gasto a partir de extractos bancarios anonimizados. Proyecto Aperture 2026-02.


---
## Actualización local: implementación y diseño de la interfaz

Se conservó el contenido anterior de este README. La aplicación se implementa en este mismo repositorio con cinco pantallas Streamlit, lógica separada en `core/` y SQL centralizado en `core/repositorio.py`.

### Windows: entorno del proyecto

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

En VS Code: `Ctrl+Shift+P` → `Python: Select Interpreter` → `.venv\Scripts\python.exe`. No es obligatorio activar el entorno ni modificar la política de PowerShell.

Los datasets se detectan también dentro de subcarpetas de `data/demo/`, incluida `archive (8)`. La carga crea perfiles de demostración y desplaza sus fechas; el historial conserva la fecha original. No son movimientos reales de 2026. Antes de publicar los originales, comprobar licencia y posibles datos identificables.

### Monedas

Registro y metas en COP, USD, EUR e INR. El núcleo conserva unidades menores enteras y conversiones Decimal. Frankfurter es una consulta opcional de referencia, no una tasa bancaria garantizada. Si falta la tasa, el equivalente no se inventa. Las pruebas usan tasas ficticias y no requieren Internet. Las metas extranjeras se valoran al guardarse, sin revalorización automática.

### Límites actuales

Los perfiles no son cuentas autenticadas. No se debe publicar esta base local con datos privados en un servidor compartido. No existe conexión bancaria ni contabilidad de saldos por cuenta. El bootstrap de metas es una simulación no calibrada; no hay MLP, regresión predictiva, agente ni RAG implementados. Varias metas se evalúan individualmente, sin asignación conjunta de capacidad. Un mes con registros no garantiza cobertura completa.

Sistema visual y alcance: `docs/diseno_interfaz.md`. No se han realizado commits ni push durante este trabajo.


### Análisis exploratorio de datos

EDA reproducible: `python -m scripts.eda_datasets`. Hallazgos y limitaciones en `docs/eda_inicial.md`; notebook en `notebooks/01_EDA_datasets.ipynb`; informe interactivo y tablas en `reports/eda/`. No se entrenaron modelos ni se modificaron los originales.


### Limpieza y conversión histórica verificable

Tres notebooks de EDA por dataset/comparación; instrucciones en `docs/eda_limpieza_multimoneda.md`. `scripts/preparar_datasets.py` conserva todas las filas y crea una base staging separada en `data/processed/`. Solo convierte monedas verificadas. El Excel queda sin convertir hasta confirmar su moneda; no se supone USD. Las respuestas históricas se guardan para repetición offline. No se carga automáticamente en la base operativa.


**Estado actualizado:** 71 pruebas aprobadas; tres notebooks ejecutados. El importador de Personal Finance bloquea la carga sin moneda y fuente verificadas, incluso en la demo. Los fixtures de prueba con USD son ficticios y no verifican la moneda del Excel real.
