#!/usr/bin/env python3
"""Export complete M3 native results, including compiler-generated variable names.

The accepted M1/M2 exporter remains unchanged. OpenModelica's native filter
accepts string names such as $STATESET entries, which readSimulationResult's
VariableNames syntax cannot parse. Its CSV path omits parameters and serializes
dynamic values with %.15g. This adapter combines that unresampled native output
with parameters and original times from the existing native result reader.
Raw MAT is the primary full-precision result. No Python MAT parser, simulation,
state correction, parameter evaluation, or resampling is used here.

API: https://openmodelica.org/doc/OpenModelicaUsersGuide/v1.27.1/scripting_api.html#filtersimulationresults
Implementation: https://github.com/OpenModelica/OpenModelica/blob/v1.27.1/OMCompiler/Compiler/runtime/SimulationResults.c
"""

import argparse
import csv
import json
import math
from pathlib import Path
import tempfile

from export_native_csv import NativeBatchReader, _query, _read_columns


def inventory(reader, mat_path, include_parameters):
    flag = "true" if include_parameters else "false"
    names = _query(reader, f"readSimulationResultVars({json.dumps(str(mat_path))}, {flag}, false)")
    if (not isinstance(names, list) or not names
            or not all(isinstance(name, str) and name for name in names)
            or len(names) != len(set(names)) or "time" not in names):
        raise ValueError(f"{mat_path.name}: invalid native variable inventory")
    return ["time", *(name for name in names if name != "time")]


def read_filtered_csv(path, dynamic_names, times):
    """Bind native CSV rows to original native times before combining columns."""
    columns = {name: [] for name in dynamic_names if name != "time"}
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        if next(reader, None) != dynamic_names:
            raise ValueError(f"{path.name}: filtered header differs from the native inventory")
        count = 0
        for index, row in enumerate(reader):
            if index >= len(times) or len(row) != len(dynamic_names):
                raise ValueError(f"{path.name}: filtered row count or width differs from native data")
            values = [float(value) for value in row]
            if not all(math.isfinite(value) for value in values):
                raise ValueError(f"{path.name}: non-finite native filtered value at row {index}")
            # The native CSV writer uses %.15g. Compare that exact representation
            # by row, then retain the original time; never merge equal-looking
            # event times or infer an output grid from rounded CSV timestamps.
            if values[0] != float(format(times[index], ".15g")):
                raise ValueError(f"{path.name}: native filtered time mismatch at row {index}")
            for name, value in zip(dynamic_names[1:], values[1:]):
                columns[name].append(value)
            count += 1
    if count != len(times):
        raise ValueError(f"{path.name}: {count} filtered rows; expected {len(times)} native rows")
    columns["time"] = times
    return columns


def cross_check_native_columns(reader, mat_path, columns, dynamic_names, sample_count):
    """Check representative public signals through both native reader paths."""
    preferred = ("tankALevel", "tankBLevel", "supplyFlow", "returnFlow", "bypassFlow",
                 "pumpPower", "totalMass", "totalInternalEnergy")
    selected = [name for name in preferred if name in columns]
    readable = [name for name in dynamic_names if name != "time" and "$" not in name]
    # Include both ends of the inventory for unchanged stock examples, which
    # do not have the authored interface aliases above.
    for name in [*readable[:4], *readable[-4:]]:
        if name not in selected:
            selected.append(name)
    if not selected:
        raise ValueError(f"{mat_path.name}: no readable public signal for native export cross-check")
    originals = _read_columns(reader, mat_path, selected, sample_count)
    for name, original in zip(selected, originals):
        for index, (filtered, native) in enumerate(zip(columns[name], original)):
            # Two native decimal serializers have different precision. This
            # bound covers their decimal round trips, not physical error.
            if not math.isclose(filtered, native, rel_tol=6e-15, abs_tol=1e-300):
                raise ValueError(f"{mat_path.name}: native readers disagree for {name!r} at row {index}")
    print(f"PASS native reader cross-check: {mat_path.name}; {len(selected)} public signals", flush=True)


def export_fluid_csv(reader, prefix, directory):
    prefix = Path(prefix)
    mat_path = Path(str(prefix) + "_res.mat").resolve()
    csv_path = Path(str(prefix) + "_res.csv").resolve()
    if not mat_path.is_file():
        raise FileNotFoundError(f"Native MAT result is missing: {mat_path}")
    print(f"READ {prefix.name}: complete and non-parameter native inventories", flush=True)
    names = inventory(reader, mat_path, True)
    dynamic_names = inventory(reader, mat_path, False)
    if not set(dynamic_names).issubset(names):
        raise ValueError(f"{mat_path.name}: inconsistent native parameter inventories")
    dynamic_set = set(dynamic_names)
    parameter_names = [name for name in names if name not in dynamic_set]
    if any("$" in name for name in parameter_names):
        raise ValueError(f"{mat_path.name}: generated parameter name requires a supported native reader")
    times = _read_columns(reader, mat_path, ["time"])[0]
    native_count = _query(reader, f"readSimulationResultSize({json.dumps(str(mat_path))})")
    if (len(times) < 2 or native_count != len(times) or times[-1] <= times[0]
            or any(b < a for a, b in zip(times, times[1:]))):
        raise ValueError(f"{mat_path.name}: invalid native sample count or times")

    filtered_path = Path(directory) / "native_dynamic.csv"
    filtered_path.unlink(missing_ok=True)
    # The native filter prepends time itself and its CSV path rejects parameters.
    string_names = "{" + ",".join(json.dumps(name) for name in dynamic_names[1:]) + "}"
    expression = (f"filterSimulationResults({json.dumps(str(mat_path))}, "
                  f"{json.dumps(str(filtered_path))}, {string_names}, numberOfIntervals=0)")
    if _query(reader, expression) is not True or not filtered_path.is_file():
        raise ValueError(f"{mat_path.name}: native unresampled CSV filter failed")
    columns = read_filtered_csv(filtered_path, dynamic_names, times)
    cross_check_native_columns(reader, mat_path, columns, dynamic_names, len(times))
    for start in range(0, len(parameter_names), 64):
        batch = parameter_names[start:start + 64]
        print(f"READ {prefix.name}: parameter columns {start + 1}..{start + len(batch)} "
              f"of {len(parameter_names)}", flush=True)
        for name, values in zip(batch, _read_columns(reader, mat_path, batch, len(times))):
            columns[name] = values
    if set(columns) != set(names):
        raise ValueError(f"{mat_path.name}: incomplete native column coverage")

    temporary = csv_path.with_suffix(".csv.tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(names)
            writer.writerows(zip(*(columns[name] for name in names)))
        temporary.replace(csv_path)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"PASS native fluid MAT to CSV: {csv_path.name}; {len(times)} original samples, "
          f"{len(names)} columns including {len(parameter_names)} parameters; "
          "dynamic CSV values use 15 significant digits; original native times retained", flush=True)
    return csv_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefixes", nargs="+", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="domelica-fluid-reader-") as directory:
        reader = NativeBatchReader(directory)
        print(f"Reading native fluid results with {_query(reader, 'getVersion()')} (batch CLI)", flush=True)
        for prefix in args.prefixes:
            export_fluid_csv(reader, prefix, directory)


if __name__ == "__main__":
    main()
