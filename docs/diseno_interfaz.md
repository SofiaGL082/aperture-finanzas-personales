# Diseño y experiencia de usuario

## Base y alcance

Repositorio real verificado mediante la ventana activa de VS Code: Documents/UNIVERSIDAD/2026-2/TrabajodeOpIA/aperture-finanzas-personales. Al iniciar este bloque contenía README, .gitignore y datasets; no existían componentes Streamlit que preservar. Se incorporaron componentes auditados del ejemplo como referencia, sin reemplazar el README ni los datos existentes. No se cambió de framework.

## Sistema visual

- Tema claro: fondo #F6F8FC, superficies blancas, texto #14213D, secundario #526079.
- Acento índigo #4F46E5; verde azulado, azul y ámbar para series de gráficos.
- Tarjetas nativas de métricas, esquinas redondeadas y espaciado consistente.
- Jerarquía: título, contexto, indicadores, gráficos y acciones.
- Menú lateral nativo con cinco páginas; iconos acompañados de texto.
- Importes con código de moneda cuando hay riesgo de ambigüedad.
- Formularios con campos etiquetados, ayuda para tasas y mensajes de validación.
- Gráficos con etiquetas, tooltips y tablas de apoyo; el color no es la única señal.
- CSS adaptable a pantallas estrechas y foco de teclado visible. Sin JavaScript personalizado.

## Definiciones de indicadores

Balance del periodo = ingresos menos gastos registrados, no saldo bancario. Ahorro típico = mediana de hasta doce meses anteriores con registros. Los meses vacíos no se convierten en ahorro cero. Los meses con registros pueden estar incompletos. Las devoluciones aún se importan como otros ingresos, una limitación del modelo contable inicial.

## Multimoneda

Se conservan monto y moneda originales y equivalente en la moneda principal. Tasas con par, fecha, valor decimal, fuente y consulta; sin tasa válida no se guarda el equivalente. Las metas extranjeras fijan su valoración al guardarse. No se revalúan automáticamente. Las cuentas son etiquetas, no un libro contable completo de saldos o transferencias.

## Privacidad

Perfiles locales sin autenticación: no desplegar con información privada en una instancia pública compartida. Los datos públicos originales no deben publicarse sin revisar licencia y contenido. Los originales existentes no se modifican. No hay envíos de datos financieros a LLM. Frankfurter recibe únicamente el par de monedas y la fecha solicitada.

## Verificación

La verificación visual y las pruebas ejecutadas se registrarán en el informe de este bloque. Una inspección en navegador no equivale a una auditoría de accesibilidad con lector de pantalla ni a una prueba en dispositivos físicos.


## Verificación realizada

Cinco pantallas revisadas en navegador de escritorio; creación y registro con perfil ficticio COP, mensajes de validación y meta orientativa. Inicio y Metas revisados también a 390 x 844. No se verificaron lectores de pantalla ni dispositivos físicos. Detalle en reports/VERIFICACION_2026-11-06.md.
