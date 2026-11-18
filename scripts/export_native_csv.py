"""Export complete native MAT results, including parameters, through OpenModelica.

Usage: python3 scripts/export_native_csv.py PREFIX [PREFIX ...]

OpenModelica's direct CSV writer omits parameters. Its native MAT reader's
readSimulationResult API expands parameter values across the original sample
times and resolves signed aliases. This adapter only serializes those values;
it performs no simulation, resampling, parameter evaluation, or physics.

Requires OMPython and omc, provided by our pinned OpenModelica CI image.
API reference: https://openmodelica.org/doc/OpenModelicaUsersGuide/v1.27.1/scripting_api.html#readsimulationresult
Parameter handling: https://github.com/OpenModelica/OpenModelica/blob/v1.27.1/OMCompiler/Compiler/runtime/SimulationResults.c
"""

import argparse
import csv
import json
import math
from pathlib import Path


def _query(session, expression):
    value = session.sendExpression(expression)
    if value is None or value is False:
        raise ValueError(f"Native result query failed: {expression}\n{session.sendExpression('getErrorString()')}")
    return value


def _read_columns(session, mat_path, names, sample_count=None):
    # Names come from OMC's result inventory, in its native Modelica syntax.
    # readSimulationResult takes VariableNames, not string literals.
    expression = f"readSimulationResult({json.dumps(str(mat_path))}, {{{','.join(names)}}}, 0)"
    matrix = _query(session, expression)
    if not isinstance(matrix, (tuple, list)) or len(matrix) != len(names):
        raise ValueError(f"{mat_path.name}: native result returned the wrong number of columns for {names!r}")
    columns = []
    for name, source_column in zip(names, matrix):
        if not isinstance(source_column, (tuple, list)):
            raise ValueError(f"{mat_path.name}: native {name!r} is not a sampled numeric column")
        column = [float(value) for value in source_column]
        if sample_count is not None and len(column) != sample_count:
            raise ValueError(f"{mat_path.name}: {name!r} has {len(column)} samples; expected {sample_count}")
        if not all(math.isfinite(value) for value in column):
            raise ValueError(f"{mat_path.name}: non-finite native result in {name!r}")
        columns.append(column)
    return columns


def export_native_csv(session, prefix: Path) -> Path:
    """Write PREFIX_res.csv atomically from PREFIX_res.mat using native APIs."""
    prefix = Path(prefix)
    mat_path = Path(str(prefix) + "_res.mat").resolve()
    csv_path = Path(str(prefix) + "_res.csv").resolve()
    if not mat_path.is_file():
        raise FileNotFoundError(f"Native MAT result is missing: {mat_path}")
    names = _query(session, f"readSimulationResultVars({json.dumps(str(mat_path))}, true, false)")
    if (not isinstance(names, (tuple, list)) or not names
            or not all(isinstance(name, str) and name for name in names)
            or len(names) != len(set(names)) or "time" not in names):
        raise ValueError(f"{mat_path.name}: invalid native variable inventory")
    names = ["time", *(name for name in names if name != "time")]
    times = _read_columns(session, mat_path, ["time"])[0]
    if (len(times) < 2 or times[-1] <= times[0]
            or any(b < a for a, b in zip(times, times[1:]))):
        raise ValueError(f"{mat_path.name}: invalid native sample times")
    native_count = _query(session, f"readSimulationResultSize({json.dumps(str(mat_path))})")
    if native_count != len(times):
        raise ValueError(f"{mat_path.name}: time column does not match native sample count")
    columns = [times]
    for start in range(1, len(names), 64):
        columns.extend(_read_columns(session, mat_path, names[start:start + 64], len(times)))
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
    _query(session, "closeSimulationResultFile()")
    print(f"PASS native MAT to CSV: {csv_path.name}; {len(times)} original samples, "
          f"{len(names)} columns including parameters and aliases")
    return csv_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefixes", nargs="+", type=Path,
                        help="result prefixes, e.g. m1_thermal_geared_arm (without _res.mat)")
    args = parser.parse_args()
    from OMPython import OMCSessionZMQ

    session = OMCSessionZMQ()
    print(f"Reading native results with {_query(session, 'getVersion()')}")
    try:
        for prefix in args.prefixes:
            export_native_csv(session, prefix)
    finally:
        session.sendExpression("quit()")


if __name__ == "__main__":
    main()
