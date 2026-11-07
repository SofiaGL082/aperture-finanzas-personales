# Verificación del bloque EDA e interfaz

## Repositorio verificado

C:/Users/SARA ISABEL/Documents/UNIVERSIDAD/2026-2/TrabajodeOpIA/aperture-finanzas-personales. Esta ruta se obtuvo de la ventana de VS Code, no del nombre del ZIP. La copia de Descargas no es el proyecto de trabajo.

## Resultado técnico

- Python local 3.11.4 y entorno .venv propio.
- 71 pruebas pytest aprobadas, 0 fallidas.
- pip check: sin dependencias rotas.
- Tres notebooks ejecutados con kernel local .venv: 7, 7 y 6 celdas de código; sin salidas de error. Código y resultados quedan guardados.
- Preparación repetida offline a partir de respuestas históricas guardadas.
- 1.083 filas en SQLite staging; integridad SQLite ok.
- 277 conversiones recalculadas independientemente con Decimal; 806 pendientes por moneda desconocida.
- Originales verificados por SHA-256, sin cambios. No se sobrescribió la base operativa.
- No se entrenaron modelos ni se implementaron agentes o RAG.

## Interfaz

Se revisaron en navegador las cinco pantallas de la aplicación real: Inicio, Registrar, Historial, Reporte mensual y Metas. Se probó crear un perfil ficticio COP, rechazar un importe vacío, guardar un ingreso ficticio, verlo en historial y reporte, crear una meta y obtener una estimación orientativa a partir de un aporte declarado. Todos esos registros están en una base de prueba separada del repositorio y se identifican como ficticios.

Se comprobó el diseño de Inicio y Metas a 390 x 844, además del tamaño de escritorio. Se restauró el tamaño del navegador. Las tarjetas y formularios se apilan y el menú usa el comportamiento nativo de Streamlit.

No se probó un dispositivo móvil físico, lector de pantalla ni todos los tamaños de pantalla. Edición y borrado tienen pruebas del núcleo, pero no se verificó cada combinación desde el navegador. La aplicación no cuenta con autenticación ni representa una plataforma pública segura para datos reales.

El importador del Excel bloquea la carga sin moneda verificada y fuente explícita. La demo no presupone USD; el archivo sigue disponible en el EDA y el staging mantiene COP nulo. Las reglas antiguas de clasificación de préstamos del CSV requieren revisión humana; la preparación nueva marca la ambigüedad sin inferir un préstamo.

## Archivos principales

- scripts/eda_datasets.py: estructura, faltantes, duplicados, cobertura, categorías y reporte interactivo.
- core/preparacion.py y scripts/preparar_datasets.py: normalización, tasas históricas y banderas de revisión.
- core/repositorio.py: almacenamiento staging exclusivo y centralización SQL.
- notebooks/01_eda_personal_finance.ipynb, 02_eda_my_expenses.ipynb, 03_comparacion_datasets.ipynb: análisis en español con resultados ejecutados.
- scripts/ejecutar_notebooks.py y requirements-eda.txt: ejecución opcional de notebooks, aislada en .venv.
- tests/test_eda.py y tests/test_preparacion.py: pruebas sin red ni archivos privados.
- interfaz/, app.py y .streamlit/config.toml: presentación Streamlit, componentes nativos y Plotly; sin JavaScript personalizado.
- docs/: decisiones de datos, conversión y experiencia de usuario.

## Ejecución Windows

Desde la carpeta del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
.\.venv\Scripts\python.exe -m scripts.eda_datasets
.\.venv\Scripts\python.exe -m scripts.preparar_datasets --offline
.\.venv\Scripts\python.exe -m scripts.ejecutar_notebooks
```

La ejecución offline de preparación requiere la caché creada en la primera consulta. Los notebooks requieren requirements-eda.txt y el kernel local fintwin-eda configurado por el procedimiento documentado.

## Git y siguiente paso

Los cambios están sin publicar; no se hicieron commits, push ni merges. Se conservaron los cambios previos del README y los datasets. Resolver la moneda del Excel y las revisiones semánticas antes de cargar el staging en la base operativa o entrenar modelos.
