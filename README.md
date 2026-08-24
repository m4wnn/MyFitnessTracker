# MyFitnessTracker

Proyecto para descargar, normalizar, auditar y analizar datos de Garmin Connect con una salida semanal reproducible.

El flujo del proyecto no genera solo un resumen. Cada consulta semanal deja un bundle con CSV canónicos, JSON crudos, FIT de actividades, metadatos del export y un reporte preliminar para revisión rápida.

## Inicio rápido

El proyecto requiere Python `>=3.11` (incluido Python 3.13). Puedes usar Conda o un entorno virtual estándar de Python.

### Opción A: Conda

Activar el entorno y validar conectividad:

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate MyFitnessTracker
cd ~/Documents/GitHub/MyFitnessTracker
python intro.py
```

### Opción B: Python sin Conda

Desde la raíz del clon, crea y activa un entorno virtual, instala el proyecto y ejecuta la prueba de conectividad:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python intro.py
```

En Windows PowerShell, activa el entorno con:

```powershell
.venv\Scripts\Activate.ps1
```

`python -m pip install -e .` instala el proyecto en modo editable y resuelve sus dependencias automáticamente. Las dependencias de ejecución declaradas son:

- `garminconnect==0.3.3`: autenticación y consultas a Garmin Connect.
- `pandas>=2.2`: normalización y exportación de datos tabulares.
- `matplotlib>=3.9`: generación de figuras de análisis.
- `setuptools>=68`: backend de construcción usado al instalar el paquete.

`intro.py` autentica contra Garmin Connect, reutiliza o crea `secrets/garmin_tokens.json` y confirma que el proyecto puede leer configuración y credenciales.

## Configuración local del atleta

Antes de generar evaluaciones semanales, crea tus archivos locales a partir de las plantillas públicas:

```bash
cp REQUEST.example.md REQUEST.md
cp CONTEXT.example.md CONTEXT.md
```

Luego modifica esos dos archivos con los datos reales del atleta:

- `REQUEST.md`: define el protocolo semanal vigente, extracciones requeridas, validaciones y formato del entregable.
- `CONTEXT.md`: guarda el baseline del atleta, métricas históricas, zonas, supuestos, evidencia y reglas de decisión.

`REQUEST.md` y `CONTEXT.md` están ignorados por Git para que puedas editar datos personales o históricos sin subirlos al repositorio. Las referencias públicas y versionadas son `REQUEST.example.md` y `CONTEXT.example.md`.

## Qué resuelve este proyecto

- Define una semana canónica de `domingo` a `sábado`, ambos inclusive, en `America/Guatemala`.
- Separa semanas `official` de semanas `preview` para no mezclar histórico cerrado con borradores.
- Combina datos locales de GarminDB con datos online de Garmin Connect cuando el caché local está incompleto o atrasado.
- Guarda suficiente evidencia cruda para depurar cada semana sin repetir toda la descarga.

## Estructura del proyecto

- `src/myfitnesstracker/cli.py`: API CLI principal.
- `src/myfitnesstracker/week.py`: resolución de semanas y estados.
- `src/myfitnesstracker/week_registry.py`: manifests y carpetas semanales.
- `src/myfitnesstracker/export.py`: exportador semanal completo, mezcla local+online.
- `src/myfitnesstracker/client.py`: autenticación Garmin Connect.
- `src/myfitnesstracker/data_sources.py`: resolución de fuentes locales GarminDB.
- `REQUEST.example.md`: plantilla pública del contrato semanal de extracción, validación y reporte.
- `CONTEXT.example.md`: plantilla pública del contexto histórico y metodológico.
- `REQUEST.md`: copia local ignorada por Git, derivada de `REQUEST.example.md`, con el protocolo real del atleta.
- `CONTEXT.md`: copia local ignorada por Git, derivada de `CONTEXT.example.md`, con el contexto real del atleta.
- `AGENTS.md`: reglas operativas, secretos, activación y contratos de implementación.

## API de la CLI

La interfaz estable del proyecto es:

```bash
python -m myfitnesstracker week <subcomando> [opciones]
```

Ejecutar siempre desde la raíz del repo:

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate MyFitnessTracker
cd ~/Documents/GitHub/MyFitnessTracker
```

### Subcomandos

- `status`: resuelve la semana y muestra qué carpeta le corresponde, sin escribir artefactos.
- `prepare`: crea la carpeta semanal y `manifest.json`, sin exportar todavía los datos.
- `export`: genera el bundle semanal completo.

### Modos de selección

- `--mode official`: usa la última semana cerrada anterior a la fecha de referencia.
- `--mode preview-current`: usa la semana actual aunque siga abierta.
- `--mode explicit --week-start YYYY-MM-DD`: usa una semana explícita cuyo inicio debe ser domingo.

### Argumentos comunes

- `--project-root`: raíz del proyecto. En este repo suele ser `~/Documents/GitHub/MyFitnessTracker`.
- `--date YYYY-MM-DD`: fecha de referencia local. Si no se pasa, usa hoy.
- `--timezone`: zona horaria IANA. Por defecto `America/Guatemala`.
- `--json`: imprime el resultado en JSON.
- `--field`: imprime un solo campo del resultado.

### Argumentos de `week export`

- `--overwrite`: rehace el export aunque la semana ya exista.
- `--skip-online-estimates`: deja el export en modo local, sin suplementación online, sin estimaciones live y sin zonas live.
- `--skip-debug-records`: no genera `debug/activity_records/`.

## API en Python

Además de la CLI, el proyecto expone una API Python simple para automatizar consultas:

```python
from datetime import date
from pathlib import Path

from myfitnesstracker.export import export_week_bundle
from myfitnesstracker.week import resolve_official_week

project_root = Path("~/Documents/GitHub/MyFitnessTracker").expanduser()
resolved_week = resolve_official_week(
    reference_date=date(2026, 8, 14),
    timezone_name="America/Guatemala",
)

result = export_week_bundle(
    project_root=project_root,
    resolved_week=resolved_week,
    overwrite=True,
    include_online_estimates=True,
    include_debug_records=True,
)

print(result.to_dict())
```

### Funciones principales

- `resolve_official_week(...)`: resuelve la última semana cerrada.
- `resolve_preview_current_week(...)`: resuelve la semana actual como preview.
- `resolve_explicit_week(...)`: valida y resuelve una semana explícita.
- `export_week_bundle(...)`: construye el bundle semanal completo.
- `load_project_config(...)`: carga configuración local del proyecto.
- `build_client(...)`: autentica un cliente Garmin Connect reutilizable.

### Resultado de `export_week_bundle`

`WeeklyExportResult.to_dict()` devuelve, entre otros, estos campos:

- `week_id`: fecha del domingo de inicio.
- `storage_bucket`: `official` o `preview`.
- `week_state`: `closed`, `incomplete` o `future`.
- `activities_count`: actividades realmente exportadas.
- `online_activity_count`: actividades encontradas online para esa semana.
- `wellbeing_rows`: filas del CSV de bienestar.
- `wellbeing_online_days`: días con payload online descargado.
- `fit_files_copied`: FIT escritos en la carpeta semanal.
- `online_estimates_status`: `ok`, `partial`, `error` o `skipped`.
- `report_path`: ruta del reporte preliminar.

## Modelo semanal

### Regla de calendario

- La semana del proyecto es `domingo, lunes, martes, miércoles, jueves, viernes, sábado`.
- El `week_id` canónico es la fecha del domingo inicial.
- La semana actual solo puede ser `preview` mientras no cierre.

### Estados

- `closed`: la semana ya terminó y puede archivarse como oficial.
- `incomplete`: la semana está en curso.
- `future`: la semana aún no empezó.

### Ejemplo real con fecha fija

Tomando como referencia el viernes `2026-08-14`:

- `--mode official` resuelve `2026-08-02` a `2026-08-08`.
- `--mode preview-current` resuelve `2026-08-09` a `2026-08-15`.

Esto ocurre porque el viernes `2026-08-14` la semana `2026-08-09` a `2026-08-15` seguía abierta. Por eso esa consulta se guarda en `preview` y no en `official`.

## Cómo se ejecutan las consultas

### 1. Consultar la semana oficial sin escribir archivos

```bash
python -m myfitnesstracker week status --mode official --json
```

### 2. Preparar la semana oficial

```bash
python -m myfitnesstracker week prepare --mode official --json
```

### 3. Exportar la semana oficial completa

```bash
python -m myfitnesstracker week export --mode official --json
```

### 4. Exportar la semana parcial actual

```bash
python -m myfitnesstracker week export --mode preview-current --json
```

### 5. Exportar una semana explícita

```bash
python -m myfitnesstracker week export --mode explicit --week-start 2026-08-02 --json
```

## Tutorial: semana completa

Este flujo sirve para generar una semana cerrada, típica de ejecución dominical.

### Paso 1

Resolver la semana:

```bash
python -m myfitnesstracker week status --mode official --json
```

### Paso 2

Preparar manifest y carpetas:

```bash
python -m myfitnesstracker week prepare --mode official --json
```

### Paso 3

Exportar el bundle:

```bash
python -m myfitnesstracker week export --mode official --overwrite --json
```

### Paso 4

Revisar resultados:

```bash
find reports/weekly/official -maxdepth 3 -type f | sort
```

Resultado esperado:

- La salida queda en `reports/weekly/official/<week_id>/`.
- `manifest.json` queda con `run_status = exported`.
- La carpeta incluye sesiones, bienestar, FIT, JSON de actividades, JSON diarios y reporte preliminar.

## Tutorial: semana parcial o preliminar

Este flujo sirve para consultar la semana actual antes del cierre.

### Paso 1

Resolver la semana actual:

```bash
python -m myfitnesstracker week status --mode preview-current --json
```

### Paso 2

Exportar la preview:

```bash
python -m myfitnesstracker week export --mode preview-current --overwrite --json
```

### Paso 3

Revisar resultados:

```bash
find reports/weekly/preview -maxdepth 3 -type f | sort
```

Resultado esperado:

- La salida queda en `reports/weekly/preview/<week_id>/`.
- `week_state` queda en `incomplete`.
- Los días futuros permanecen vacíos en `bienestar_<week_id>.csv`.
- El campo `is_future_day` marca esos días con `1`.
- La preview no se mezcla con el histórico oficial.

## Qué hace realmente `week export`

Cuando la sincronización online está habilitada, `week export` ejecuta esta pipeline:

1. Resuelve la semana y crea o reutiliza su manifest.
2. Localiza la fuente GarminDB local preferida.
3. Carga sesiones desde SQLite si existen.
4. Consulta Garmin Connect para obtener la lista online de actividades de la ventana.
5. Completa cada actividad con resumen, detalles y archivo original.
6. Descarga bienestar diario online para cada día consultable de la semana.
7. Escribe CSV canónicos y CSV enriquecidos.
8. Guarda JSON crudos diarios y por actividad.
9. Consulta FTP y zonas actuales de Garmin.
10. Genera `reporte_<week_id>.md`.

## Dónde quedan los resultados

### Carpetas base

- `reports/weekly/official/<week_id>/`
- `reports/weekly/preview/<week_id>/`

### Archivos principales

- `manifest.json`: metadata de la semana y estado de ejecución.
- `reporte_<week_id>.md`: resumen legible del export.
- `csv/sesiones_<week_id>.csv`: columnas canónicas pedidas por tu `REQUEST.md` local.
- `csv/sesiones_enriquecidas_<week_id>.csv`: versión completa con métricas extra y trazabilidad local/online.
- `csv/bienestar_<week_id>.csv`: una fila por día.
- `csv/laps_<week_id>.csv`: laps presentes en SQLite local.
- `csv/file_inventory_<week_id>.csv`: inventario de archivos escritos.
- `json/export_context_<week_id>.json`: contexto del export, conteos y errores parciales.
- `json/garmin_estimates_<week_id>.json`: FTP, VO2max, zonas y estado online.
- `json/activities_index_<week_id>.json`: índice semanal de actividades visto online.
- `json/activities/*_summary.json`: resumen crudo por actividad.
- `json/activity_details/*_details.json`: detalle crudo por actividad.
- `json/daily/*_user_summary.json`: payload diario de resumen.
- `json/daily/*_sleep.json`: payload diario de sueño.
- `json/daily/*_hrv.json`: payload diario de HRV.
- `json/daily/*_body_battery.json`: payload diario de Body Battery.
- `json/daily/*_body_composition.json`: payload diario de peso/composición corporal.
- `fit/*.fit`: original de cada actividad de la semana.

### Archivos de depuración

- `debug/activity_records/*.csv`: solo aparecen si la base local `garmin_activities.db` contiene `activity_records` para esas actividades.

## Fuente de datos y fallback

La ruta canónica del proyecto es:

```text
data/raw/HealthData/
```

Si ese árbol todavía no contiene las bases SQLite necesarias, el proyecto hace fallback de solo lectura a:

```text
~/.GarminDb/HealthData/
```

Ese fallback queda auditado en:

- `json/export_context_<week_id>.json`
- `reporte_<week_id>.md`
- el campo CLI `used_legacy_fallback`

## Consultas generadas en este repo

A fecha del viernes `2026-08-14` ya quedaron generadas estas dos semanas:

- Oficial `2026-08-02`: `reports/weekly/official/2026-08-02/`
- Preview `2026-08-09`: `reports/weekly/preview/2026-08-09/`

Cobertura observada:

- `2026-08-02`: 6 actividades, 6 FIT, 7 días de bienestar online.
- `2026-08-09`: 5 actividades, 5 FIT, 6 días de bienestar online y 1 día futuro vacío.

## Qué pasa cuando no es domingo

Si corres la consulta en un día que no es domingo, hay dos comportamientos distintos:

- `--mode official` sigue apuntando a la última semana ya cerrada.
- `--mode preview-current` genera una foto preliminar de la semana en curso.

En el caso real del viernes `2026-08-14`:

- La semana oficial sigue siendo `2026-08-02` a `2026-08-08`.
- La semana `2026-08-09` a `2026-08-15` todavía es preliminar.
- El sábado `2026-08-15` aparece vacío en bienestar y marcado con `is_future_day = 1`.
- Si luego vuelves a exportar esa misma semana después del cierre, conviene hacerlo ya como semana oficial de la siguiente ejecución.

## Troubleshooting

- Si `intro.py` falla, revisar `config/private/GarminConnectConfig.json` y `secrets/.garmin_password`.
- Si una semana exporta menos actividades de las esperadas, revisar `json/activities_index_<week_id>.json`.
- Si el CSV de bienestar tiene huecos, revisar `json/daily/` para ese día.
- Si faltan `debug/activity_records`, no significa que falten FIT; normalmente significa que la base local no tenía esos registros por segundo importados.
- Si quieres un export estrictamente offline, usa `--skip-online-estimates`.
