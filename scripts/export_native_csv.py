"""Export complete native MAT results, including parameters, through OpenModelica.

Usage: python3 scripts/export_native_csv.py PREFIX [PREFIX ...]

OpenModelica's direct CSV writer omits parameters. Its native MAT reader's
readSimulationResult API expands parameter values across the original sample
times and resolves signed aliases. This adapter only serializes those values;
it performs no simulation, resampling, parameter evaluation, or physics.

Requires only Python's standard library and omc. Queries use bounded batch CLI
processes, never an interactive server (which OMC refuses to run as root).
API reference: https://openmodelica.org/doc/OpenModelicaUsersGuide/v1.27.1/scripting_api.html#readsimulationresult
Parameter handling: https://github.com/OpenModelica/OpenModelica/blob/v1.27.1/OMCompiler/Compiler/runtime/SimulationResults.c
"""

import argparse
import csv
import json
import math
from pathlib import Path
import subprocess
import tempfile
import time


def _parse_native_value(raw):
    """Parse literal numeric/string/list results; never evaluate source code.

    Modelica arrays use braces. Preserve braces inside quoted names and respect
    backslash escapes while translating only the array delimiters to JSON.
    """
    characters, quoted, escaped = [], False, False
    for character in raw:
        if quoted:
            characters.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        else:
            if character == '"':
                quoted = True
            characters.append({"{": "[", "}": "]"}.get(character, character))
    def reject_constant(value):
        raise ValueError(f"non-finite native numeric constant {value}")
    return json.loads("".join(characters), parse_constant=reject_constant)


class NativeBatchReader:
    """Run each official result-reader query in a short-lived omc process."""

    def __init__(self, directory):
        self.script = Path(directory) / "read_native_result.mos"

    def query(self, expression):
        self.script.write_text(expression + ";\n", encoding="utf-8")
        try:
            result = subprocess.run(["omc", str(self.script)], capture_output=True,
                                    text=True, timeout=30, check=False)
        except subprocess.TimeoutExpired as error:
            raise ValueError(f"Native batch result query exceeded 30 seconds: {expression[:180]}") from error
        if result.returncode:
            raise ValueError(f"Native batch result query failed ({result.returncode}): "
                             f"{expression[:180]}\n{result.stdout[:500]}\n{result.stderr[:1000]}")
        try:
            value = _parse_native_value(result.stdout)
        except (ValueError, TypeError) as error:
            raise ValueError(f"Invalid native batch result for {expression[:180]}: "
                             f"{result.stdout[:500]!r}\n{result.stderr[:1000]}") from error
        if value is None or value is False:
            raise ValueError(f"Native batch query returned failure: {expression[:180]}\n{result.stderr[:1000]}")
        return value


def _query(reader, expression):
    return reader.query(expression)


def _read_columns(reader, mat_path, names, sample_count=None):
    # Names come from OMC's result inventory, in its native Modelica syntax.
    # readSimulationResult takes VariableNames, not string literals.
    expression = f"readSimulationResult({json.dumps(str(mat_path))}, {{{','.join(names)}}}, 0)"
    matrix = _query(reader, expression)
    if not isinstance(matrix, (tuple, list)) or len(matrix) != len(names):
        raise ValueError(f"{mat_path.name}: native result returned the wrong number of columns for {names!r}")
    columns = []
    for name, source_column in zip(names, matrix):
        if not isinstance(source_column, (tuple, list)):
            raise ValueError(f"{mat_path.name}: native {name!r} is not a sampled numeric column")
        if not all(type(value) in (int, float) for value in source_column):
            raise ValueError(f"{mat_path.name}: nonnumeric data in native {name!r}")
        column = [float(value) for value in source_column]
        if sample_count is not None and len(column) != sample_count:
            raise ValueError(f"{mat_path.name}: {name!r} has {len(column)} samples; expected {sample_count}")
        if not all(math.isfinite(value) for value in column):
            raise ValueError(f"{mat_path.name}: non-finite native result in {name!r}")
        columns.append(column)
    return columns


def export_native_csv(reader, prefix: Path) -> Path:
    """Write PREFIX_res.csv atomically from PREFIX_res.mat using native APIs."""
    prefix = Path(prefix)
    mat_path = Path(str(prefix) + "_res.mat").resolve()
    csv_path = Path(str(prefix) + "_res.csv").resolve()
    if not mat_path.is_file():
        raise FileNotFoundError(f"Native MAT result is missing: {mat_path}")
    started = time.monotonic()
    print(f"READ {prefix.name}: native variable inventory", flush=True)
    names = _query(reader, f"readSimulationResultVars({json.dumps(str(mat_path))}, true, false)")
    if (not isinstance(names, (tuple, list)) or not names
            or not all(isinstance(name, str) and name for name in names)
            or len(names) != len(set(names)) or "time" not in names):
        raise ValueError(f"{mat_path.name}: invalid native variable inventory")
    names = ["time", *(name for name in names if name != "time")]
    print(f"READ {prefix.name}: time column ({len(names)} total columns)", flush=True)
    times = _read_columns(reader, mat_path, ["time"])[0]
    if (len(times) < 2 or times[-1] <= times[0]
            or any(b < a for a, b in zip(times, times[1:]))):
        raise ValueError(f"{mat_path.name}: invalid native sample times")
    print(f"READ {prefix.name}: native sample count", flush=True)
    native_count = _query(reader, f"readSimulationResultSize({json.dumps(str(mat_path))})")
    if native_count != len(times):
        raise ValueError(f"{mat_path.name}: time column does not match native sample count")
    columns = [times]
    for start in range(1, len(names), 64):
        print(f"READ {prefix.name}: columns {start + 1}..{min(start + 64, len(names))} "
              f"of {len(names)} ({time.monotonic() - started:.1f}s)", flush=True)
        columns.extend(_read_columns(reader, mat_path, names[start:start + 64], len(times)))
    temporary = csv_path.with_suffix(".csv.tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(names)
            writer.writerows(zip(*columns))
        temporary.replace(csv_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(f"PASS native MAT to CSV: {csv_path.name}; {len(times)} original samples, "
          f"{len(names)} columns including parameters and aliases", flush=True)
    return csv_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefixes", nargs="+", type=Path,
                        help="result prefixes, e.g. m1_thermal_geared_arm (without _res.mat)")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="domelica-native-reader-") as directory:
        reader = NativeBatchReader(directory)
        print(f"Reading native results with {_query(reader, 'getVersion()')} (batch CLI)", flush=True)
        for prefix in args.prefixes:
            export_native_csv(reader, prefix)


if __name__ == "__main__":
    main()
