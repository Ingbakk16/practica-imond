# Plan de cierre — BigQuery + Looker Studio

Decisión del propietario, 04/11/2026: **Looker Studio reemplaza Power BI**.
El plan distingue implementación, aceptación web y operación observada.
Una tarea solo se marca completa cuando tiene evidencia de su resultado.

## 1. Fijar la entrega y retirar la dependencia Microsoft

- [x] Definir Looker como dashboard final en README y guías.
- [x] Retirar el job Power BI del workflow cloud y su prueba específica de CI.
- [x] Conservar los PBIX y scripts como archivo histórico.
- [x] Eliminar MFA, Entra y refresh Power BI de los requisitos de cierre.

Resultado: el pipeline final depende de Google Cloud y Looker, con DuckDB como
referencia histórica reproducible.

## 2. Asegurar la entrega de datos

- [x] Mantener la publicación transaccional ya existente de cuatro fuentes y metadatos.
- [x] Implementar verificación de la copia publicada, no solo del build dbt.
- [x] Exigir metadatos completos, una publicación coherente y antigüedad máxima
  de dos horas al verificar una publicación nueva.
- [x] Conciliar en las tablas publicadas ventas, pedidos, compradores, productos,
  unidades, sesiones, usuarios identificados, anónimas y componentes de NPS.
- [x] Comprobar que todos los lotes están completos y tienen validación concordante.
- [x] Exigir en schedule el lote correspondiente al día anterior en Argentina.
- [x] Generar evidencia JSON y logs en `bigquery-diagnostics`.
- [x] Diagnosticar el [run fallido #21](https://github.com/Ingbakk16/practica-imond/actions/runs/41849903528).
- [x] Publicar la versión revisada y comprobar un workflow cloud exitoso:
  PR #10 integrado en main (`e14f7e0`); run #22, intento 1, con publicación y
  aceptación exitosas para el lote 03/11/2026.

Prueba manual desde una sesión autorizada, después de un build y conciliaciones
exitosas:

```powershell
$env:GCP_PROJECT_ID = 'marketing-513302'
$env:BQ_LOCATION = 'US'
python cloud/publish_looker.py
python cloud/verify_looker.py --expected-date 2026-11-03 --out looker-acceptance.json
```

La fecha del ejemplo corresponde al schedule del 04/11/2026. En otra fecha usar
el día de negocio esperado. El workflow la calcula automáticamente.
No reejecutar `publish_looker.py` tras un build fallido ni usar artifacts viejos.

La causa del run #21 es un error interno 500 `backendError` en BigQuery.
Se implementó `cloud/build_dbt.py`: hasta tres builds completos, esperas de
15 y 30 segundos y reintento exclusivo de errores transitorios. Los errores
SQL, de permisos y tests de calidad fallidos detienen el proceso.
Pruebas offline: 64 tests cloud aprobados.

## 3. Completar y validar las cinco páginas

- [x] Informe existente con Resumen, Ventas, Clientes, Satisfacción y Adquisición.
- [x] Fuentes separadas para evitar multiplicar importes entre hechos.
- [x] Tabla visible con lote, fecha de datos y publicación UTC.
- [x] Agregar al informe la fuente de [ranking_mensual.sql](lookerstudio/ranking_mensual.sql):
  proyecto `marketing-513302`, parámetros de fecha habilitados, dimensiones mes y
  producto, métricas importe y posición (sin sumar posiciones). Ordenar mes
  ascendente y posición ascendente. Excluir controles de producto/canal/provincia.
- [x] En Ventas: controles canal/provincia/tienda agrupados con los gráficos de
  pedidos; controles equivalentes separados para productos. Producto filtra solo
  líneas. Rotular cada grupo para que el alcance sea visible.
- [x] En Clientes: canal agrupado solo con compradores, sin filtrar sesiones.
- [x] Aplicar corte histórico 01/01/2024–30/09/2025 y registrar los KPIs de
  [la guía](lookerstudio/README.md#5-validar-y-entregar-el-enlace).
- [x] Probar enero 2024: 460 pedidos, ARS 15.965.464,50, 431 compradores,
  424 usuarios activos y NPS 37,6. Ranking: Sport B 1, Classic A 2.
- [x] Restablecer filtros y guardar; comprobar que la fecha final de negocio no
  queda fijada al 04/11 si la demo seguirá incorporando días.
- [x] Verificar que la tabla técnica de publicación no queda limitada por
  el selector de fechas de negocio.

El ranking está incorporado al informe web y sus posiciones de enero de 2024
se comprobaron visualmente. Evidencia y pruebas de filtros en ESTADO_PROYECTO.md.

## 4. Acceso, recuperación y continuidad

- [x] Verificar acceso Público — Lector, autorizado por el propietario.
- [x] Probar el enlace en incógnito: el propietario confirmó que abre y muestra
  los gráficos sin solicitar acceso. No debe requerir permisos
  BigQuery si se mantienen las credenciales del propietario.
- [x] Confirmar frescura de las seis fuentes (una hora) y usar Actualizar datos:
  lote 03/11/2026, publicación 04/11/2026 19:39:37 UTC, 11.998 pedidos.
- [x] Recuperar el run fallido y repetir el lote 03/11/2026, semilla 42, 100 pedidos.
  Run #22, intentos 1 y 2 exitosos. Tras Actualizar datos se mantienen 11.998
  pedidos y las mismas filas e importes; solo cambia la publicación UTC.
- [ ] Registrar siete ejecuciones programadas, fecha procesada, resultado,
  publicación y consumo. Los runs anteriores a la corrección son antecedentes.
- [x] Verificar presupuesto, cuotas y vigencia en la cuenta cloud: prueba hasta
  29/12/2026, USD 300 de crédito; sin presupuesto; cuota 200 TiB/día y por usuario
  ilimitada. Detalle y límites en ESTADO_PROYECTO.md.
- [x] Registrar decisión de consumo: el propietario indicó **conservar los límites
  actuales** el 04/11/2026. No se crea presupuesto ni se cambian cuotas.

Para recuperar faltantes, usar rangos manuales de hasta siete días. No borrar
tablas ni editar marcadores de lotes. Las pruebas de inyección de fallos
continúan diferidas por la decisión previa del propietario.

## Criterio de terminado

La entrega funcional queda cerrada cuando el código revisado pasa las pruebas,
un run cloud publica y verifica el lote esperado, las cinco páginas pasan los
controles y el enlace funciona para un lector externo. El cierre operativo
agrega evidencia de continuidad y consumo durante siete ejecuciones diarias.

Estado actual y límites de esta revisión: [ESTADO_PROYECTO.md](ESTADO_PROYECTO.md).
