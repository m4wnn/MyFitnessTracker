# Contexto replicable — Evaluación de fitness ciclista y protocolo de entrenamiento Zona 2

**Atleta:** `<alias_o_identificador_local>`
**Fecha de corte del análisis:** `<yyyy-mm-dd>`
**Ventana de datos analizada:** `<yyyy-mm-dd> → <yyyy-mm-dd>`
**Objetivo del programa:** `<objetivo_fisiologico_y_de_entrenamiento>`
**Propósito de este documento:** preservar baseline, metodología, supuestos, reglas de decisión y continuidad del análisis sin exponer datos personales en el repositorio público.

Este archivo es una plantilla pública. El archivo real `CONTEXT.md` puede contener datos personales, históricos detallados y decisiones operativas privadas, por lo que se ignora en Git.

---

## Índice

1. [Metadatos, fuentes y grados de confianza](#1-metadatos-fuentes-y-grados-de-confianza)
2. [Perfil del atleta](#2-perfil-del-atleta)
3. [Estado de fitness actual](#3-estado-de-fitness-actual)
4. [Diagnóstico y evidencia](#4-diagnóstico-y-evidencia)
5. [Configuración vigente de dispositivos](#5-configuración-vigente-de-dispositivos)
6. [Marco conceptual: fisiología del umbral aeróbico](#6-marco-conceptual-fisiología-del-umbral-aeróbico)
7. [Metodología de estimación: triangulación](#7-metodología-de-estimación-triangulación)
8. [Protocolos de test y criterios de calificación](#8-protocolos-de-test-y-criterios-de-calificación)
9. [Catálogo de entrenamientos](#9-catálogo-de-entrenamientos)
10. [Calendario Fase 0 y progresión anual](#10-calendario-fase-0-y-progresión-anual)
11. [Métricas semanales — implementación GarminDB](#11-métricas-semanales--implementación-garmindb)
12. [Métricas de largo plazo](#12-métricas-de-largo-plazo)
13. [Reglas de decisión operativas](#13-reglas-de-decisión-operativas)
14. [Bitácora de supuestos no validados](#14-bitácora-de-supuestos-no-validados)
15. [Bibliografía](#15-bibliografía)
16. [Changelog](#16-changelog)

---

## 1. Metadatos, fuentes y grados de confianza

### 1.1 Fuentes de datos utilizadas

| Fuente | Contenido | Periodo | Uso en el análisis |
|---|---|---|---|
| `<fit_principal>` | `<descripcion>` | `<periodo>` | `<uso>` |
| `<csv_actividades>` | `<descripcion>` | `<periodo>` | `<uso>` |
| `<csv_bienestar>` | `<descripcion>` | `<periodo>` | `<uso>` |
| `<json_estimaciones>` | `<descripcion>` | `<periodo>` | `<uso>` |

### 1.2 Clasificación por grado de confianza

| Valor | Magnitud | Grado | Origen |
|---|---|---|---|
| FC en reposo | `<valor>` | `MEDIDO` / `CALCULADO` / `INFERIDO` | `<origen>` |
| FC máxima | `<valor>` | `<grado>` | `<origen>` |
| Peso | `<valor>` | `<grado>` | `<origen>` |
| LT1 | `<valor>` | `<grado>` | `<origen>` |
| FTP | `<valor>` | `<grado>` | `<origen>` |

### 1.3 Valores explícitamente descartados

| Valor | Fuente | Razón del descarte |
|---|---|---|
| `<valor_1>` | `<fuente>` | `<motivo>` |
| `<valor_2>` | `<fuente>` | `<motivo>` |

---

## 2. Perfil del atleta

| Campo | Valor |
|---|---|
| Edad | `<edad>` |
| Talla | `<talla>` |
| Peso | `<peso>` |
| FC reposo | `<fc_reposo>` |
| FC máxima | `<fc_max>` |
| Ubicación | `<ubicacion_general>` |
| Modalidad | `<modalidad_principal>` |

### 2.1 Equipamiento y entorno

- `<dispositivo_1>`
- `<sensor_1>`
- `<plataforma_1>`
- `<condiciones_ambientales_relevantes>`
- `<ventana_horaria_habitual>`

### 2.2 Contexto de altitud

Describir aquí si la altitud afecta la comparación externa o la interpretación de frecuencia cardiaca y potencia.

---

## 3. Estado de fitness actual

### 3.1 Indicadores primarios

| Indicador | Valor | Rango de incertidumbre | Método |
|---|---|---|---|
| FTP | `<valor>` | `<rango>` | `<metodo>` |
| LT1 potencia | `<valor>` | `<rango>` | `<metodo>` |
| LT1 FC | `<valor>` | `<rango>` | `<metodo>` |
| VO2max | `<valor>` | `<rango>` | `<metodo>` |
| Factor de eficiencia | `<valor>` | `<rango>` | `<metodo>` |

### 3.2 Interpretación del perfil

Registrar aquí la lectura operativa actual del perfil fisiológico del atleta.

### 3.3 Advertencias metodológicas

Documentar fórmulas o zonas poblacionales que no apliquen bien al atleta y deban evitarse.

---

## 4. Diagnóstico y evidencia

### 4.1 Hallazgo central

Resumir aquí la hipótesis principal que gobierna el bloque actual de entrenamiento.

### 4.2 Serie de factor de eficiencia

| Periodo | n | EF | NP media | FC media |
|---|---|---|---|---|
| `<periodo>` | `<n>` | `<ef>` | `<np>` | `<fc>` |

### 4.3 Parones de entrenamiento identificados

| Inicio | Fin | Días sin entrenar | Contexto |
|---|---|---|---|
| `<inicio>` | `<fin>` | `<dias>` | `<contexto>` |

### 4.4 Auditoría de valores configurados

Documentar aquí discrepancias relevantes entre configuración del dispositivo y realidad fisiológica observada.

### 4.5 Validación de campo

| Archivo o sesión | Duración útil | Potencia | FC | Desacople | Conclusión |
|---|---|---|---|---|---|
| `<sesion>` | `<duracion>` | `<potencia>` | `<fc>` | `<pwhr>` | `<lectura>` |

### 4.6 Limitantes secundarias

Registrar aquí factores como cadencia, torque, temperatura, hidratación o disponibilidad de tiempo.

### 4.7 Sueño y recuperación

| Métrica | Valor |
|---|---|
| Sueño mediano | `<valor>` |
| % noches < 7 h | `<valor>` |
| HRV media | `<valor>` |
| Observación clave | `<texto>` |

### 4.8 Verificación del horario de entrenamiento

Documentar si el horario habitual muestra o no penalización visible en la recuperación siguiente.

---

## 5. Configuración vigente de dispositivos

### 5.1 Valores de perfil

| Campo | Valor a configurar | Valor previo |
|---|---|---|
| Peso | `<valor>` | `<valor_previo>` |
| FC máxima | `<valor>` | `<valor_previo>` |
| FTP ciclismo | `<valor>` | `<valor_previo>` |
| Detección automática de FTP | `<estado>` | `<estado_previo>` |

### 5.2 Zonas de frecuencia cardiaca

| Zona | Límite inferior | Rango | Base |
|---|---|---|---|
| Z1 | `<valor>` | `<rango>` | `<base>` |
| Z2 | `<valor>` | `<rango>` | `<base>` |
| Z3 | `<valor>` | `<rango>` | `<base>` |
| Z4 | `<valor>` | `<rango>` | `<base>` |
| Z5 | `<valor>` | `<rango>` | `<base>` |

### 5.3 Zonas de potencia

| Zona | Límite inferior | Rango | Base |
|---|---|---|---|
| Z1 | `<valor>` | `<rango>` | `<base>` |
| Z2 | `<valor>` | `<rango>` | `<base>` |
| Z3 | `<valor>` | `<rango>` | `<base>` |
| Z4 | `<valor>` | `<rango>` | `<base>` |
| Z5 | `<valor>` | `<rango>` | `<base>` |

### 5.4 Alertas

| Alerta | Umbral | Acción |
|---|---|---|
| `<alerta>` | `<umbral>` | `<accion>` |

### 5.5 Zwift u otra plataforma

Describir aquí cómo se reflejan las zonas y alertas en la plataforma de entrenamiento.

---

## 6. Marco conceptual: fisiología del umbral aeróbico

### 6.1 Definición de los umbrales

Definir LT1, LT2 y cualquier otro umbral usado por el protocolo.

### 6.2 Mecanismos de adaptación en Zona 2

Resumir aquí por qué el bloque actual busca este tipo de adaptación.

### 6.3 Control de intensidad

Describir por qué la estabilidad de potencia/FC importa y qué invalida una sesión.

### 6.4 Estado de la evidencia

Registrar reservas metodológicas, lagunas y desacuerdos razonables.

---

## 7. Metodología de estimación: triangulación

### 7.1 Principio

Explicar aquí por qué se combinan varias señales y cómo se resuelven discrepancias.

### 7.2 Método A — Deflexión de frecuencia cardiaca

Describir entradas, condiciones de validez y criterio de lectura.

### 7.3 Método B — Umbral ventilatorio por frecuencia respiratoria

Describir entradas, condiciones de validez y criterio de lectura.

### 7.4 Método C — Desacople potencia:pulso

Describir entradas, condiciones de validez y criterio de lectura.

### 7.5 Regla de precedencia

Definir qué método manda cuando dos métodos discrepan.

### 7.6 Métodos descartados

Documentar aquí heurísticas o métricas que se probaron y se rechazaron.

### 7.7 Trazabilidad de FC máxima

Documentar de dónde sale la FC máxima operativa y qué evidencia la sostiene.

### 7.8 Trazabilidad de FTP

Documentar de dónde sale el FTP operativo y qué debilidades tiene esa estimación.

---

## 8. Protocolos de test y criterios de calificación

### 8.1 Condiciones de control obligatorias

Listar sueño mínimo, temperatura, hidratación, nutrición, descanso previo y consistencia del setup.

### 8.2 Test A — Deriva cardiaca

Definir protocolo, duración, intensidad objetivo y criterio de aprobación.

### 8.3 Test B — Rampa LT1

Definir escalones, duración, variables observadas y criterio de localización del umbral.

### 8.4 Test C — Validación de FTP

Definir si aplica, cuándo aplica y con qué reservas.

---

## 9. Catálogo de entrenamientos

### 9.1 Plantilla A — Z2 Base

Describir objetivo, duración, potencia objetivo y señales de salida.

### 9.2 Plantilla B — Z2 Ondulada

Describir objetivo, duración, potencia objetivo y señales de salida.

### 9.3 Plantilla C — Z2 Cadencia

Describir objetivo, duración, potencia objetivo y señales de salida.

### 9.4 Plantilla D — Z2 Activaciones

Describir objetivo, duración, potencia objetivo y señales de salida.

### 9.5 Plantilla E — Z2 Larga

Describir variantes y criterio para elegir cada una.

### 9.6 Plantilla F — Intensidad

Definir prerequisitos y cuándo introducirla.

### 9.7 Sesión complementaria

Definir si existen dobles sesiones o bloques opcionales.

### 9.8 Entrenamientos de test

Listar sesiones reservadas para evaluación.

---

## 10. Calendario Fase 0 y progresión anual

### 10.1 Fase actual

Documentar objetivo, duración, carga semanal y criterio de avance.

### 10.2 Progresión anual

Describir las fases macro y qué gatilla cada transición.

### 10.3 Techo de volumen

Justificar el máximo de horas o sesiones razonable para este atleta.

### 10.4 Condición para añadir volumen

Definir la señal operativa mínima para subir carga.

---

## 11. Métricas semanales — implementación GarminDB

### 11.1 Advertencia crítica sobre el esquema

Documentar limitaciones del esquema SQLite que afectan las métricas.

### 11.2 Esquema canónico intermedio

Definir tablas/CSV intermedios canónicos usados por el pipeline.

### 11.3 Métricas semanales

Listar aquí las métricas obligatorias y su interpretación.

### 11.4 Consultas SQL

Mantener aquí o referenciar las consultas canónicas.

### 11.5 Cálculos que requieren parseo de FIT

Enumerar métricas que no deben salir de SQLite.

---

## 12. Métricas de largo plazo

### 12.1 Tabla de seguimiento

| Fecha | Peso | LT1 W | LT1 FC | FTP | EF | Sueño | Observación |
|---|---|---|---|---|---|---|---|
| `<fecha>` | `<peso>` | `<lt1_w>` | `<lt1_fc>` | `<ftp>` | `<ef>` | `<sueno>` | `<nota>` |

### 12.2 Métrica rectora

Explicar qué métrica gobierna las decisiones del bloque actual y por qué.

### 12.3 Nota sobre el peso

Explicar cómo se interpreta el peso dentro del sistema y cuándo no usarlo para sacar conclusiones.

### 12.4 Proyección

Registrar una proyección prudente y las condiciones para invalidarla.

---

## 13. Reglas de decisión operativas

### 13.1 Durante la sesión

Definir reglas sobre potencia, FC, respiración, RPE y cuándo abortar o corregir.

### 13.2 Antes de la sesión — semáforo de recuperación

Definir qué combinación de sueño, HRV, RHR, fatiga y contexto bloquea o modifica la sesión.

### 13.3 Recalibración de zonas

Definir cuándo y con qué evidencia se actualizan LT1, FTP o alertas.

### 13.4 Confusores a descartar

Listar calor, deshidratación, enfermedad, problemas de sensores u otros factores.

### 13.5 Transición entre fases

Definir criterio de paso entre fases del plan.

---

## 14. Bitácora de supuestos no validados

| Supuesto | Estado | Riesgo | Próxima validación |
|---|---|---|---|
| `<supuesto>` | `<estado>` | `<riesgo>` | `<accion>` |

### 14.1 Advertencias sobre estimaciones indirectas

Registrar aquí cualquier valor útil pero todavía débil.

---

## 15. Bibliografía

### 15.1 Fundamento fisiológico

Listar referencias base del protocolo.

### 15.2 Evidencia crítica

Listar referencias que contradicen, matizan o limitan la interpretación.

### 15.3 Herramientas

Listar software, librerías o documentación usada.

---

## 16. Changelog

| Fecha | Cambio | Motivo | Impacto |
|---|---|---|---|
| `<yyyy-mm-dd>` | `<cambio>` | `<motivo>` | `<impacto>` |

### 16.1 Plantilla de entrada para el changelog

```md
- Fecha:
- Cambio:
- Evidencia:
- Impacto operativo:
- Archivos afectados:
```
