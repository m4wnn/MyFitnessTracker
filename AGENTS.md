# MyFitnessTracker Agent Guide

## Activacion del entorno

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate MyFitnessTracker
```

Si el entorno no existe, recrearlo con:

```bash
conda create --name MyFitnessTracker --clone base
conda activate MyFitnessTracker
python -m pip install -e .
```

## Contratos de secretos

- `secrets/.garmin_password` contiene unicamente la password de Garmin, en una sola linea.
- Nunca imprimir, commitear, mover ni versionar contenido de `secrets/` o `config/private/`.
- `secrets/garmin_tokens.json` se genera despues del primer login exitoso y debe tratarse como secreto.
- `config/private/GarminConnectConfig.json` debe apuntar a `secrets/.garmin_password` mediante `credentials.password_file`.

## Contratos de runtime

- Ejecutar los comandos desde la raiz del repo.
- `intro.py` es la prueba minima de conectividad: autentica y pide datos basicos del perfil.
- Las descargas crudas viven en `data/raw/HealthData`.
- Los datasets procesados viven en `data/processed`.
- Las figuras y reportes derivados viven en `reports/figures`.
- La semana oficial del proyecto va de **domingo a sabado**, ambos inclusive, en `America/Guatemala`.
- El `week_id` canonico es la fecha del **domingo de inicio** en formato `YYYY-MM-DD`.

## Documentos de contexto

- `REQUEST.md` define la solicitud semanal: que datos descargar, que validaciones correr y que formato debe tener la evaluacion entregada.
- `CONTEXT.md` conserva el contexto completo de la evaluacion previa: baseline del atleta, supuestos vigentes, metodologia, hallazgos y reglas de decision.

## Protocolo de lectura

- Antes de cualquier evaluacion semanal, leer `REQUEST.md` completo para identificar el entregable actual y sus campos obligatorios.
- Despues leer `CONTEXT.md` completo para recuperar el contexto historico y evitar cambiar criterios, umbrales o interpretaciones sin justificarlo.
- Si se genera un nuevo analisis, usar `REQUEST.md` como contrato de salida y `CONTEXT.md` como contrato de continuidad.
- Si existe tension entre una instruccion puntual del pedido actual y el contexto historico, priorizar la instruccion actual y dejar explicita la desviacion en el reporte.

## Contratos de cambios

- Mantener compatibilidad con Python 3.13 del entorno actual.
- Preferir rutas relativas al proyecto; no volver a apuntar a `~/.GarminDb`.
- Cualquier script nuevo que use credenciales debe leerlas desde `config/private/` y `secrets/`, no desde variables hardcodeadas.

## Contratos de implementacion

- Implementar el protocolo de `REQUEST.md` como una pipeline modular en Python; evitar scripts monoliticos con muchas responsabilidades.
- Separar claramente extraccion, parseo FIT, metricas derivadas, validacion, render del reporte y CLI.
- Toda etapa debe poder ejecutarse y depurarse de forma independiente.
- Toda salida intermedia relevante debe persistirse en archivos dentro de `reports/weekly/official/<week_id>/` o `reports/weekly/preview/<week_id>/` para inspeccion posterior.
- Los errores deben fallar con mensajes explicitos que indiquen etapa, archivo, actividad o consulta involucrada.
- Las semanas oficiales cerradas y las semanas incompletas en preview deben persistirse por separado para no mezclar historico oficial con borradores.
- Si la semana actual no ha cerrado todavia, no generar reporte oficial; usar un estado `incomplete` o un preview explicito.

## Documentacion obligatoria de codigo

- Todo codigo implementado en este proyecto debe estar adecuadamente comentado y documentado; esto es obligatorio.
- Todo modulo publico debe tener docstring de modulo.
- Toda clase, dataclass y funcion publica debe tener docstring que describa proposito, entradas, salidas y supuestos relevantes.
- Toda logica no obvia debe incluir comentarios inline concisos, especialmente formulas fisiologicas, heuristicas de validez y reglas de conciliacion FIT ↔ CSV.
- No introducir funciones "magicas" o compactas que dificulten el debug; priorizar nombres explicitos y pasos intermedios observables.
