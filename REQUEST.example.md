# Protocolo semanal de descarga y reporte — GarminDB

**Documento complementario de:** `CONTEXT.md`
**Frecuencia de ejecución:** cada domingo, sobre la semana cerrada inmediatamente anterior (domingo→sábado)
**Versión:** `<version>` — `<yyyy-mm-dd>`

Este archivo es una plantilla pública. Define el contrato operativo de la evaluación semanal sin incluir datos privados del atleta.

---

## Índice

1. [Rutas y verificación previa](#1-rutas-y-verificación-previa)
2. [Rutina semanal — comandos](#2-rutina-semanal--comandos)
3. [Extracción 1 — Sesiones](#3-extracción-1--sesiones)
4. [Extracción 2 — Serie diaria de bienestar](#4-extracción-2--serie-diaria-de-bienestar)
5. [Extracción 3 — Archivos FIT completos](#5-extracción-3--archivos-fit-completos)
6. [Extracción 4 — Estimaciones y configuración de Garmin](#6-extracción-4--estimaciones-y-configuración-de-garmin)
7. [Validación de integridad](#7-validación-de-integridad)
8. [Formato del reporte semanal](#8-formato-del-reporte-semanal)
9. [Entregable para análisis externo](#9-entregable-para-análisis-externo)
10. [Calendario de tareas no semanales](#10-calendario-de-tareas-no-semanales)
11. [Fallos comunes](#11-fallos-comunes)

---

## 1. Rutas y verificación previa

### 1.1 Rutas canónicas dentro del proyecto

Todas las rutas de esta sección son relativas a la raíz del repo.

| Contenido | Ruta canónica |
|---|---|
| Bases SQLite | `data/raw/HealthData/DBs/` |
| FIT de actividades | `data/raw/HealthData/FitFiles/Activities/` |
| FIT de monitoreo diario | `data/raw/HealthData/FitFiles/Monitoring/` |
| Configuración privada | `config/private/GarminConnectConfig.json` |
| Resumen de actualización | `stats.txt` |
| Salida semanal oficial | `reports/weekly/official/<week_id>/` |
| Salida semanal preview | `reports/weekly/preview/<week_id>/` |

**Semana canónica:** domingo a sábado, en `America/Guatemala`.
**`week_id` canónico:** fecha del domingo de inicio en formato `YYYY-MM-DD`.

### 1.2 Bases disponibles

| Base | Contenido relevante |
|---|---|
| `garmin.db` | Actividades, FC diaria, sueño, estrés, RHR, peso |
| `garmin_activities.db` | Laps y registros por segundo |
| `garmin_monitoring.db` | Monitoreo continuo |
| `garmin_summary.db` | Agregados diarios, semanales y mensuales |

### 1.3 Verificación de esquema

Ejecutar una sola vez antes del primer ciclo o después de cambios de versión:

```bash
sqlite3 data/raw/HealthData/DBs/garmin.db ".schema" > schema_garmin.sql
sqlite3 data/raw/HealthData/DBs/garmin_activities.db ".schema" > schema_activities.sql
sqlite3 data/raw/HealthData/DBs/garmin_summary.db ".schema" > schema_summary.sql
```

### 1.4 Limitación estructural relevante

Documentar aquí cualquier limitación que obligue a usar FIT como fuente primaria para métricas fisiológicas no disponibles en SQLite.

---

## 2. Rutina semanal — comandos

### 2.1 Script de descarga

Mantener aquí el script canónico o el comando CLI equivalente usado por el proyecto. Debe:

1. Resolver `week_id`, `start_date` y `end_date`.
2. Descargar/importar datos nuevos.
3. Respaldar bases antes de consultar.
4. Persistir todos los artefactos de salida en `reports/weekly/<mode>/<week_id>/`.

Ejemplo:

```bash
python -m myfitnesstracker.cli week prepare --mode official
python -m myfitnesstracker.cli week export --mode official
```

### 2.2 Comandos auxiliares

| Situación | Comando |
|---|---|
| Respaldo de bases | `<comando_respaldo>` |
| Rebuild tras cambio de versión | `<comando_rebuild>` |
| Descarga incremental | `<comando_incremental>` |
| Actualización de herramienta | `<comando_upgrade>` |

### 2.3 Orden de ejecución obligatorio

1. Descarga incremental.
2. Respaldo.
3. Extracciones.
4. Validaciones.
5. Reporte.

---

## 3. Extracción 1 — Sesiones

### 3.1 Alcance

Incluir todas las actividades de la semana. El filtrado por deporte debe ocurrir en el análisis, no en la extracción.

### 3.2 Campos requeridos

| Campo | Nombre canónico | Origen | Obligatorio |
|---|---|---|---|
| ID de actividad | `activity_id` | SQLite/FIT | Sí |
| Fecha | `date` | SQLite/FIT | Sí |
| Hora de inicio | `start_time` | SQLite/FIT | Sí |
| Deporte | `sport` | SQLite/FIT | Sí |
| Nombre | `name` | SQLite/FIT | Sí |
| Duración | `duration_seconds` | SQLite/FIT | Sí |
| Distancia | `distance_km` | SQLite/FIT | No |
| FC media / máx | `avg_hr_bpm`, `max_hr_bpm` | SQLite/FIT | Sí |
| Potencia media / NP | `avg_power_w`, `normalized_power_w` | FIT o SQLite | Sí |
| Carga | `tss`, `training_load`, `training_effect` | SQLite/FIT | No |

### 3.3 Consulta

Mantener aquí la consulta SQL canónica o su equivalente programático.

### 3.4 Nombre del archivo

`csv/sesiones_<week_id>.csv`

---

## 4. Extracción 2 — Serie diaria de bienestar

### 4.1 Alcance

Persistir los 7 días de la ventana, incluyendo días sin entrenamiento y faltantes reales.

### 4.2 Campos requeridos

| Campo | Nombre canónico | Crítico |
|---|---|---|
| Fecha | `date` | Sí |
| FC en reposo | `resting_hr_bpm` | Sí |
| HRV última noche | `hrv_last_night_avg_ms` | Sí |
| HRV media semanal | `hrv_weekly_avg_ms` | No |
| Estado HRV | `hrv_status` | No |
| Horas de sueño | `sleep_hours` | Sí |
| Puntaje de sueño | `sleep_score` | No |
| Body Battery min/max | `body_battery_min`, `body_battery_max` | Parcial |
| Peso | `weight_kg` | Sí |
| Reloj usado de noche | `watch_worn_night` | Sí |

### 4.3 Campo derivado `watch_worn_night`

Definir explícitamente la regla de derivación y usarla para evitar interpretar mínimos diurnos como reposo nocturno.

### 4.4 Consulta

Mantener aquí la consulta SQL canónica o su equivalente programático.

### 4.5 Nombre del archivo

`csv/bienestar_<week_id>.csv`

---

## 5. Extracción 3 — Archivos FIT completos

### 5.1 Regla de alcance

Copiar todos los FIT correspondientes a las actividades de la ventana semanal.

### 5.2 Localización y copia

Documentar aquí la fuente, el patrón de selección y la verificación de conteo contra `sesiones_<week_id>.csv`.

### 5.3 Convención de nombres

Definir un patrón estable, por ejemplo:

`fit/<date>_<slug_de_actividad>_<activity_id>.fit`

### 5.4 Campos a extraer de cada FIT

Enumerar aquí los campos mínimos necesarios para el análisis fisiológico y la conciliación contra SQLite.

### 5.5 Métricas derivadas obligatorias por sesión

Enumerar aquí métricas como NP recalculada, desacople Pw:Hr, duración útil, bloques, cadencia, respiración u otras que no se obtienen bien desde SQLite.

### 5.6 Retención

Definir política de retención para FIT crudos y artefactos derivados.

---

## 6. Extracción 4 — Estimaciones y configuración de Garmin

### 6.1 Frecuencia

Indicar si la auditoría de configuración es semanal, quincenal o solo tras cambios explícitos.

### 6.2 Contenido

Incluir campos como FTP, umbrales, zonas, peso, FC máxima, alertas y cualquier otra configuración usada por el análisis.

### 6.3 Verificación semanal obligatoria

Definir qué cambios deben disparar una advertencia o recalibración de zonas.

### 6.4 Nombre del archivo

`json/garmin_estimates_<week_id>.json`

---

## 7. Validación de integridad

### 7.1 Cobertura temporal

Verificar que la ventana cubra exactamente domingo a sábado.

### 7.2 Conciliación FIT ↔ CSV

Verificar que cada sesión relevante tenga correlato en CSV y FIT.

### 7.3 Anomalías por sesión

Documentar reglas para detectar archivos corruptos, duplicados, pausas largas o series imposibles.

### 7.4 Coherencia de potencia

Definir umbrales y chequeos mínimos sobre potencia, cadencia y frecuencia cardiaca.

---

## 8. Formato del reporte semanal

### 8.1 Archivo

`reporte_<week_id>.md`

### 8.2 Plantilla

```md
# Reporte semanal — <start_date> a <end_date>

## 1. Integridad de datos

## 2. Métricas principales

## 3. Detalle por sesión

## 4. Serie diaria

## 5. Configuración de Garmin

## 6. Observaciones

## 7. Decisiones

## 8. Entradas para changelog
```

### 8.3 Reglas de redacción

Definir aquí el tono, los campos obligatorios y cómo documentar desviaciones respecto al contexto histórico.

---

## 9. Entregable para análisis externo

Definir el paquete mínimo exportable para una revisión externa:

| Tipo | Archivo |
|---|---|
| Resumen semanal | `reporte_<week_id>.md` |
| Sesiones | `csv/sesiones_<week_id>.csv` |
| Bienestar | `csv/bienestar_<week_id>.csv` |
| FIT | `fit/*.fit` |
| Estimaciones | `json/garmin_estimates_<week_id>.json` |
| Manifest | `manifest.json` |

### 9.1 En semanas de test

Documentar aquí archivos extra y validaciones adicionales requeridas.

### 9.2 Límite de tamaño

Definir reglas de compresión, muestreo o exclusión si el paquete supera el tamaño deseado.

---

## 10. Calendario de tareas no semanales

Mantener aquí las tareas mensuales, trimestrales o por evento, por ejemplo:

| Frecuencia | Tarea |
|---|---|
| Mensual | Revisar deriva del contexto |
| Trimestral | Revalidar zonas |
| Por cambio de versión | Revisar esquema SQLite |

---

## 11. Fallos comunes

Mantener aquí los errores recurrentes, cómo detectarlos y cómo resolverlos sin comprometer el histórico oficial.
