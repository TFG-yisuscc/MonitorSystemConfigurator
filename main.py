#!/usr/bin/env python3
"""
Configurator — Generator of configuration files for MonitorSystemCplusplus
https://github.com/TFG-yisuscc/MonitorSystemCplusplus
"""

import itertools
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Fields whose values were selected via a combo option (interleaved in output)
_interleave_keys: set = set()

# ── ANSI colours ──────────────────────────────────────────────────────────────
_CLR = sys.stdout.isatty()

def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _CLR else t

def bold(t):   return _c("1",  t)
def cyan(t):   return _c("96", t)
def green(t):  return _c("92", t)
def yellow(t): return _c("93", t)
def red(t):    return _c("91", t)
def dim(t):    return _c("2",  t)


# ── Schema ────────────────────────────────────────────────────────────────────
FIELDS = [
    dict(key="inference_engine",   label="Inference Engine",       type="enum",   required=True,
         single_only=True,
         choices=["LLAMA", "OLLAMA"],
         hints={"LLAMA": "llama.cpp local", "OLLAMA": "Ollama server"}),
    dict(key="test_type",          label="Test Type",              type="enum",   required=True,
         choices=["TYPE_0", "TYPE_1", "TYPE_2"],
         hints={"TYPE_0": "only prompt metrics",
                "TYPE_1": "prompt + hardware metrics",
                "TYPE_2": "prompt + hardware metrics + 5 s pause"},
         combos=[("TYPE_0 + TYPE_1", ["TYPE_0", "TYPE_1"])]),
    dict(key="batch_size",         label="Batch Size",             type="int",    required=True,  default=512),
    dict(key="context_size",       label="Context Size (tokens)",  type="int",    required=True,  default=4096),
    dict(key="seed",               label="Seed",                   type="int",    required=True,  single_only=True, default=42),
    dict(key="num_prompts",        label="Number of Prompts",      type="int",    required=True,
         single_only=True, min_val=1, max_val=541, default=10),
    dict(key="temperature",        label="Temperature",            type="float",  required=True,  default=0.0),
    dict(key="model_path_or_name", label="Model Path / Name",      type="string", required=True),
    dict(key="hardware_period",    label="Hardware Period (s)",    type="float",  required=True,  single_only=True, default=0.5),
    dict(key="anotations",         label="Annotations",            type="annotation", required=False, single_only=True),
    dict(key="ollama_url",         label="Ollama URL",             type="string", required=False,
         default="http://localhost:11434"),
]


# ── Low-level I/O helpers ─────────────────────────────────────────────────────
def ask(prompt: str, default: str = "") -> str:
    hint = f" [{dim(default)}]" if default else ""
    try:
        raw = input(f"  {prompt}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return raw if raw else default


def hr(title: str) -> None:
    bar = "─" * 60
    print(f"\n{bold(cyan(bar))}")
    print(f"  {bold(title)}")
    print(bold(cyan(bar)))


def section(title: str) -> None:
    print(f"\n  {bold(yellow('▸'))} {bold(title)}")


def padded(s: str, width: int) -> str:
    """Left-pad s to visual width (strips ANSI for length calculation)."""
    import re
    ansi_escape = re.compile(r"\033\[[0-9;]*m")
    visible = len(ansi_escape.sub("", s))
    return s + " " * max(0, width - visible)


# ── Range helpers ─────────────────────────────────────────────────────────────
def int_range(start: int, end: int, step: int) -> list:
    return list(range(start, end + 1, step))


def float_range(start: float, end: float, step: float) -> list:
    n = round((end - start) / step)
    return [round(start + i * step, 10) for i in range(n + 1)]


# ── Per-type collectors ───────────────────────────────────────────────────────
def collect_enum(field: dict) -> list:
    choices     = field["choices"]
    hints       = field.get("hints", {})
    combos      = field.get("combos", [])   # list of (label, [values])
    single_only = field.get("single_only", False)
    print()
    for i, ch in enumerate(choices, 1):
        hint = f"  {dim('—')} {dim(hints[ch])}" if ch in hints else ""
        print(f"    {cyan(str(i))}) {ch}{hint}")
    # combo options are numbered continuing after plain choices
    combo_start = len(choices) + 1
    for j, (label, _) in enumerate(combos):
        print(f"    {cyan(str(combo_start + j))}) {label}  {dim('— combinado')}")
    if not single_only:
        print(f"    {cyan('a')}) {bold('All')}")

    def _resolve(tokens: list) -> list:
        """Expand token indices to values; register combo use."""
        used_combo = False
        selected = []
        for token in tokens:
            if token.isdigit():
                idx = int(token) - 1
                if idx < len(choices):
                    selected.append(choices[idx])
                elif idx - len(choices) < len(combos):
                    selected.extend(combos[idx - len(choices)][1])
                    used_combo = True
                else:
                    print(red(f"  ✗ Index {token} out of range, ignored."))
            elif token:
                print(red(f"  ✗ Unknown token '{token}', ignored."))
        seen: set = set()
        deduped = [v for v in selected if not (v in seen or seen.add(v))]
        if used_combo:
            _interleave_keys.add(field["key"])
        return deduped

    if single_only:
        valid_range = len(choices) + len(combos)
        while True:
            raw = ask("Select one (number)", "1")
            if raw.isdigit() and 1 <= int(raw) <= valid_range:
                result = _resolve([raw])
                return result if result else [choices[0]]
            print(red(f"  ✗ Enter a number between 1 and {valid_range}."))
    else:
        raw = ask("Select (numbers separated by commas, or a)", "a")
        if raw.lower() == "a":
            if combos:
                _interleave_keys.add(field["key"])
            return list(choices)
        result = _resolve(raw.replace(" ", "").split(","))
        return result if result else list(choices)


def collect_numeric(field: dict, cast) -> list:
    single_only  = field.get("single_only", False)
    min_val      = field.get("min_val", None)
    max_val      = field.get("max_val", None)
    default_val  = field.get("default", None)
    kind         = "integer" if cast is int else "decimal"
    default_str  = str(default_val) if default_val is not None else ""

    constraint = ""
    if min_val is not None and max_val is not None:
        constraint = f" [{min_val}–{max_val}]"
    elif min_val is not None:
        constraint = f" [min {min_val}]"
    elif max_val is not None:
        constraint = f" [max {max_val}]"

    def _validate(v):
        if min_val is not None and v < min_val:
            print(red(f"  ✗ Value must be ≥ {min_val}.")); return False
        if max_val is not None and v > max_val:
            print(red(f"  ✗ Value must be ≤ {max_val}.")); return False
        return True

    def _cast(raw: str):
        if not raw and default_str:
            return cast(default_str)
        return cast(raw)

    if single_only:
        while True:
            raw = ask(f"  Value{constraint}", default_str)
            try:
                v = _cast(raw)
            except ValueError:
                print(red(f"  ✗ Expected a {kind} number.")); continue
            if _validate(v):
                return [v]
        return []  # noqa

    print()
    print(f"    {cyan('s')} — Single value")
    print(f"    {cyan('r')} — Range   (start  end  step)")
    print(f"    {cyan('l')} — List    (comma-separated values)")
    mode = ask("Mode", "s").lower()

    if mode == "r":
        while True:
            raw = ask("  Range (start end step)")
            parts = raw.split()
            if len(parts) != 3:
                print(red("  ✗ Provide exactly three numbers: start end step")); continue
            try:
                start, end, step = cast(parts[0]), cast(parts[1]), cast(parts[2])
            except ValueError:
                print(red(f"  ✗ All three must be {kind} numbers.")); continue
            if step <= 0:
                print(red("  ✗ step must be > 0.")); continue
            if start > end:
                print(red("  ✗ start must be ≤ end.")); continue
            values = int_range(start, end, step) if cast is int else float_range(start, end, step)
            preview = str(values[:6]) + ("…" if len(values) > 6 else "")
            print(green(f"  ✓ {len(values)} value(s): {preview}"))
            return values

    if mode == "l":
        while True:
            raw = ask("  Values (comma-separated)")
            try:
                values = [cast(v.strip()) for v in raw.split(",") if v.strip()]
                if not values:
                    raise ValueError
            except ValueError:
                print(red(f"  ✗ All entries must be {kind} numbers.")); continue
            print(green(f"  ✓ {len(values)} value(s): {values}"))
            return values

    # single
    while True:
        raw = ask(f"  Value{constraint}", default_str)
        try:
            v = _cast(raw)
        except ValueError:
            print(red(f"  ✗ Expected a {kind} number.")); continue
        if _validate(v):
            return [v]


def collect_annotation(field: dict) -> list:
    print(f"  {dim('Reminder fields — do not modify the generated configuration.')}")

    def ask_bool(prompt: str) -> bool:
        while True:
            raw = ask(prompt, "n").lower()
            if raw in ("y", "yes"):
                return True
            if raw in ("n", "no", ""):
                return False
            print(red("  ✗ Enter y or n."))

    fan         = ask_bool("Fan active? (y/n)")
    accelerator = ask_bool("Accelerator active? (y/n)")
    other       = ask("Other annotations", "")
    return [{"fan": fan, "accelerator": accelerator, "other": other}]


def collect_string(field: dict) -> list:
    default     = field.get("default", "")
    required    = field.get("required", True)
    single_only = field.get("single_only", False)

    if not single_only:
        print()
        print(f"    {cyan('s')} — Single value")
        print(f"    {cyan('l')} — List    (comma-separated values)")
        mode = ask("Mode", "s").lower()
    else:
        mode = "s"

    if mode == "l":
        while True:
            raw = ask("  Values (comma-separated)", default)
            values = [v.strip() for v in raw.split(",") if v.strip()]
            if not values and required:
                print(red("  ✗ At least one value is required.")); continue
            return values if values else [default]

    while True:
        raw = ask("  Value", default)
        if not raw and required:
            print(red("  ✗ This field is required.")); continue
        return [raw]


def collect_field(field: dict, idx: int, total: int) -> list:
    section(f"[{idx}/{total}]  {field['label']}  {dim('(' + field['key'] + ')')}")
    if not field.get("required", True):
        print(f"  {dim('Optional — press Enter to keep default')}")
    ftype = field["type"]
    if ftype == "enum":
        return collect_enum(field)
    if ftype == "int":
        return collect_numeric(field, int)
    if ftype == "float":
        return collect_numeric(field, float)
    if ftype == "annotation":
        return collect_annotation(field)
    return collect_string(field)


# ── Output ────────────────────────────────────────────────────────────────────
def make_basename(values: dict) -> str:
    ts     = datetime.now().strftime("%Y%m%d%H%M%S")
    engine = values["inference_engine"][0]
    raw_model = values["model_path_or_name"][0]
    model  = re.sub(r"[^\w\-]", "_", raw_model).strip("_")
    model  = re.sub(r"_+", "_", model)
    types  = "+".join(values["test_type"])
    return f"{ts}_{engine}_{model}_{types}"


def ask_output() -> tuple:
    hr("Output Options")
    print()
    print(f"    {cyan('1')} — Single JSONL file      (one config per line, all in one file)")
    print(f"    {cyan('2')} — Individual JSON files  (one file per config + paths.txt)")
    fmt     = ask("Format", "1")
    out_dir = Path(ask("Output directory", "./configs"))
    if fmt == "2":
        print()
        print(f"    {cyan('r')} — Relative paths  {dim('(default)')}")
        print(f"    {cyan('a')} — Absolute paths")
        paths_mode = ask("paths.txt format", "r").lower()
        absolute = paths_mode == "a"
    else:
        absolute = False
    return fmt, out_dir, absolute


def write_jsonl(configs: list, out_dir: Path, basename: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{basename}.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for cfg in configs:
            f.write(json.dumps(cfg, ensure_ascii=False) + "\n")
    print(green(f"\n  ✓ {len(configs)} configuration(s) → {out_file.resolve()}"))


def write_individual(configs: list, out_dir: Path, basename: str, absolute: bool = False) -> None:
    run_dir = out_dir / basename
    run_dir.mkdir(parents=True, exist_ok=True)
    digits = len(str(len(configs)))
    paths  = []
    for i, cfg in enumerate(configs, 1):
        name = f"config_{str(i).zfill(digits)}.json"
        path = run_dir / name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        paths.append(str(path.resolve() if absolute else path))
    txt_path = run_dir / "paths.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(paths) + "\n")
    print(green(f"\n  ✓ {len(configs)} JSON file(s) → {run_dir.resolve()}/"))
    print(green(f"  ✓ Path list                → {txt_path.resolve()}"))


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    hr("MonitorSystem — Configuration Generator")
    print(f"\n  Generates every combination of the parameter values you define.")
    print(f"  {dim('Numeric fields accept a single value, a range (start end step), or a list.')}")

    values_per_field: dict = {}
    total           = len(FIELDS)
    selected_engine = None

    for idx, field in enumerate(FIELDS, 1):
        k = field["key"]

        if k == "ollama_url" and selected_engine != "OLLAMA":
            section(f"[{idx}/{total}]  {field['label']}  {dim('(ollama_url)')}")
            print(f"  {dim('Skipped — engine is not OLLAMA')}")
            values_per_field[k] = [field.get("default", "")]
            continue

        vals = collect_field(field, idx, total)
        values_per_field[k] = vals

        if k == "inference_engine":
            selected_engine = vals[0]

    # ── Summary ────────────────────────────────────────────────────────────
    hr("Summary")
    total_combos = 1
    for field in FIELDS:
        k = field["key"]
        v = values_per_field[k]
        total_combos *= len(v)
        label = padded(cyan(k), 34)
        if len(v) > 1:
            preview = str(v[:4]) + ("  …" if len(v) > 4 else "")
            print(f"  {label}  {yellow(str(len(v)))} values  {dim(preview)}")
        else:
            print(f"  {label}  {v[0]}")

    print(f"\n  {bold('Total combinations:')} {bold(yellow(str(total_combos)))}")

    if total_combos > 10_000:
        print(yellow(f"\n  ⚠  That's {total_combos:,} files. This may take a while."))
        if ask("Continue? (y/n)", "y").lower() not in ("y", "yes"):
            print("  Aborted.")
            sys.exit(0)

    # ── Build cartesian product ────────────────────────────────────────────
    # Interleaved fields vary fastest (innermost dimension) so their values
    # appear adjacent for every combination of the remaining parameters.
    orig_keys    = [f["key"] for f in FIELDS]
    outer_keys   = [k for k in orig_keys if k not in _interleave_keys]
    inner_keys   = [k for k in orig_keys if k in _interleave_keys]
    product_keys = outer_keys + inner_keys
    combos  = itertools.product(*[values_per_field[k] for k in product_keys])
    configs = [{k: row[product_keys.index(k)] for k in orig_keys} for row in combos]

    # ── Write output ───────────────────────────────────────────────────────
    fmt, out_dir, absolute = ask_output()
    basename = make_basename(values_per_field)
    if fmt == "2":
        write_individual(configs, out_dir, basename, absolute)
    else:
        write_jsonl(configs, out_dir, basename)

    print(f"\n  {bold(green('Done!'))}\n")


if __name__ == "__main__":
    main()
