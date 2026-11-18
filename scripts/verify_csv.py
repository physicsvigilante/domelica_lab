#!/usr/bin/env python3
"""Independent numeric checks of native OpenModelica CSV output; no physics recomputation for rendering."""
import csv
import math
from pathlib import Path


def read_csv(path: Path, required: tuple[str, ...]) -> list[dict[str, float]]:
    if not path.is_file():
        raise AssertionError(f"Missing native result: {path}")
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        missing = sorted(set(required) - set(columns))
        if missing:
            raise AssertionError(
                f"{path}: missing {missing}; available columns: {columns[:30]}"
            )
        result = []
        for row in reader:
            values = {name: float(row[name]) for name in required}
            if not all(math.isfinite(value) for value in values.values()):
                raise AssertionError(f"{path}: non-finite {values}")
            result.append(values)
    if len(result) < 50:
        raise AssertionError(f"{path}: too few points ({len(result)})")
    times = [r["time"] for r in result]
    if any(b < a for a, b in zip(times, times[1:])):
        raise AssertionError(f"{path}: time is not monotone")
    return result


def close(actual: float, expected: float, tol: float, context: str) -> None:
    if abs(actual - expected) > tol:
        raise AssertionError(
            f"{context}: expected {expected:.7g}, got {actual:.7g} (tol {tol})"
        )


def main() -> None:
    p = read_csv(
        Path("m0_motorized_pendulum_res.csv"),
        ("time", "angle", "angularVelocity", "motorCurrent"),
    )
    close(p[0]["time"], 0, 1e-8, "pendulum start time")
    close(p[-1]["time"], 4, 1e-5, "pendulum end time")
    if not any(abs(row["motorCurrent"]) > 0.05 for row in p if row["time"] > 0.6):
        raise AssertionError("motor current never responds to voltage step")
    if not any(abs(row["angle"] - p[0]["angle"]) > 1e-3 for row in p[1:]):
        raise AssertionError("pendulum did not move")

    h = read_csv(Path("m0_thermal_step_res.csv"), ("time", "temperature"))
    close(h[0]["temperature"], 293.15, 1e-4, "thermal initial temperature")
    close(h[-1]["time"], 5, 1e-5, "thermal end time")
    # Independent lumped heat balance: C * dT/dt = Q - G * (T-Tamb).
    # A delayed step applies Q=90 W for t >= 0.5 s.
    t = h[-1]["time"]
    expected = 293.15 + (90 / 1.2) * (1 - math.exp(-1.2 * (t - 0.5) / 15))
    close(h[-1]["temperature"], expected, 0.15, "thermal analytic solution")

    b = read_csv(Path("m0_msl_double_pendulum_res.csv"), ("time",))
    close(b[-1]["time"], 1, 1e-5, "MSL baseline end time")
    print(
        "PASS native CSV verification: electromechanical movement/current, "
        "thermal analytic solution, and MSL baseline"
    )


if __name__ == "__main__":
    main()
