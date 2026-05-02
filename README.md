# Configurator

[English version](README.en.md)

Utilidad de consola para generar ficheros de configuración para [MonitorSystemCplusplus](https://github.com/TFG-yisuscc/MonitorSystemCplusplus).

## Requisitos

Python 3.8 o superior. Sin dependencias externas.

## Uso

```
python main.py
```

La herramienta recorre cada campo de configuración de forma interactiva. En los campos que admiten múltiples valores (batch size, context size, temperatura, modelo, tipo de test) se puede indicar:

- **Valor único** — un valor fijo
- **Rango** — `inicio fin paso`, genera todos los valores del intervalo, ambos extremos incluidos
- **Lista** — valores separados por comas

Se generan todas las combinaciones posibles de los valores proporcionados (producto cartesiano).

## Formatos de salida

Al finalizar se elige entre dos formatos:

**1 — JSONL** — todas las configuraciones en un único fichero, una por línea.

```
configs/
└── configs.jsonl
```

**2 — Ficheros JSON individuales** — un `.json` por configuración más un `paths.txt` con las rutas absolutas a cada fichero.

```
configs/
├── config_001.json
├── config_002.json
├── ...
└── paths.txt
```

## Campos de configuración

| Campo | Tipo | Valores / restricciones |
|---|---|---|
| `inference_engine` | enum | `LLAMA`, `OLLAMA` |
| `test_type` | enum | `TYPE_0`, `TYPE_1`, `TYPE_2`, `TYPE_0 + TYPE_1` (combinado) |
| `batch_size` | int | entero positivo |
| `context_size` | int | entero positivo |
| `seed` | int | cualquier entero (valor único) |
| `num_prompts` | int | 1–541 (valor único) |
| `temperature` | float | decimal no negativo |
| `model_path_or_name` | string | nombre del modelo o ruta al fichero GGUF |
| `hardware_period` | float | intervalo de muestreo en segundos (valor único) |
| `anotations` | string | descripción libre opcional |
| `ollama_url` | string | solo se pregunta cuando el motor es `OLLAMA` |
