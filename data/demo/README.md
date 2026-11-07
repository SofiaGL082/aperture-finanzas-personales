# Fuentes de demostración y EDA

Los originales se conservan en archive (8), sin cambios. No se mueven ni se limpian en el mismo archivo.

- Personal Finance, entrepreneurlife/Lauhith: 806 movimientos. La moneda no está declarada en el Excel ni en los metadatos oficiales consultados. Se analiza en su unidad original y queda en staging pendiente de moneda. La carga en la aplicación se bloquea hasta aportar código de moneda y fuente verificable. No se asume USD.
- My Expenses Data, tharunprabu: 277 movimientos, 276 INR y uno USD. El importador conserva la moneda original y el equivalente INR documentado; las conversiones históricas a COP de la preparación se calculan desde cada moneda original.

La licencia MIT del primero y CC0 del segundo se deben verificar junto con su procedencia antes de publicar copias. La disponibilidad pública no elimina el riesgo de datos identificables. No se publicaron archivos durante este trabajo.

La demo puede desplazar las fechas para mostrar reportes recientes; el EDA y la preparación histórica siempre utilizan las fechas originales. Un mes de borde puede estar incompleto. Las reglas de clasificación son heurísticas, requieren revisión y no certifican que una nota From/To sea un préstamo.

Datos derivados y caché de tasas: data/processed, ignorada por Git. No son evidencia de representatividad colombiana ni de precisión predictiva.
