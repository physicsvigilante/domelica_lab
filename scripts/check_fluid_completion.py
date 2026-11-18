#!/usr/bin/env python3
"""Reject incomplete M3 simulations using native logs and the native MAT reader.

OpenModelica 1.27.1's batch scripting context cannot resolve fields of an
assigned SimulationResult record in the guards used here. Use its current-run
simulation completion message and the same bounded native result-reader APIs
as the accepted exporter. A partial MAT file or initialization success alone
cannot satisfy this guard.
"""

import argparse
import math
from pathlib import Path
import re
import sys
import tempfile
import json

from export_native_csv import NativeBatchReader, _query, _read_columns


def check_completion(prefix, stop, minimum_samples):
    mat_path = Path(str(prefix) + "_res.mat").resolve()
    log_path = Path(str(prefix) + ".log").resolve()
    for path in (mat_path, log_path):
        if not path.is_file():
            raise ValueError(f"missing current native output: {path.name}")
    log = log_path.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"^LOG_SUCCESS\s*\|\s*info\s*\|\s*The simulation finished successfully\.\s*$",
                     log, re.MULTILINE):
        raise ValueError(f"{prefix.name}: native log does not confirm simulation completion")
    with tempfile.TemporaryDirectory(prefix="domelica-fluid-completion-") as directory:
        reader = NativeBatchReader(directory)
        count = _query(reader, f"readSimulationResultSize({json.dumps(str(mat_path))})")
        if type(count) is not int or count < minimum_samples:
            raise ValueError(f"{prefix.name}: {count} native samples; need at least {minimum_samples}")
        times = _read_columns(reader, mat_path, ["time"], count)[0]
    if (any(b < a for a, b in zip(times, times[1:]))
            or abs(times[0]) > 1e-9 or abs(times[-1]-stop) > 1e-9):
        raise ValueError(f"{prefix.name}: incomplete native time coverage {times[0]}..{times[-1]} s; "
                         f"expected 0..{stop} s")
    print(f"PASS native completion: {prefix.name}; {count} original samples; stop {times[-1]:.12g} s", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", type=Path)
    parser.add_argument("stop", type=float)
    parser.add_argument("minimum_samples", type=int)
    args = parser.parse_args()
    if not math.isfinite(args.stop) or args.stop <= 0 or args.minimum_samples < 2:
        parser.error("stop must be finite and positive; minimum_samples must be at least two")
    try:
        check_completion(args.prefix, args.stop, args.minimum_samples)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
