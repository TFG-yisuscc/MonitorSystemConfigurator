# Configurator

[Versión en español](README.md)

Console utility for generating configuration files for [MonitorSystemCplusplus](https://github.com/TFG-yisuscc/MonitorSystemCplusplus).

## Requirements

Python 3.8 or later. No external packages required.

## Usage

```
python main.py
```

The tool walks through each configuration field interactively. For fields that support multiple values (batch size, context size, temperature, model, test type) you can provide:

- **Single value** — one fixed value
- **Range** — `start end step`, generates every value in the interval inclusive
- **List** — comma-separated values

All combinations of the provided values are generated (cartesian product).

## Output formats

At the end you choose between two formats:

**1 — JSONL** — all configurations in a single file, one JSON object per line.

```
configs/
└── configs.jsonl
```

**2 — Individual JSON files** — one `.json` file per configuration plus a `paths.txt` listing absolute paths to every file.

```
configs/
├── config_001.json
├── config_002.json
├── ...
└── paths.txt
```

## Configuration fields

| Field | Type | Values / constraints |
|---|---|---|
| `inference_engine` | enum | `LLAMA`, `OLLAMA` |
| `test_type` | enum | `TYPE_0`, `TYPE_1`, `TYPE_2`, `TYPE_0 + TYPE_1` (combined shortcut) |
| `batch_size` | int | any positive integer |
| `context_size` | int | any positive integer |
| `seed` | int | any integer (single value) |
| `num_prompts` | int | 1–541 (single value) |
| `temperature` | float | any non-negative float |
| `model_path_or_name` | string | model name or path to GGUF file |
| `hardware_period` | float | sampling interval in seconds (single value) |
| `anotations` | string | optional free-text description |
| `ollama_url` | string | only asked when engine is `OLLAMA` |
