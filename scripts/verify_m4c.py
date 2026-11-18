#!/usr/bin/env python3
"""Accept two new MSL compositions using independent physical oracles.

Completion and native CSV validation reuse the accepted M4 reader. Physical
oracles are separate from both the Modelica models and the playback renderer.
"""

import argparse
import json
import math
from pathlib import Path
import sys

from verify_m4 import check_completion, digest

ROOT = Path(__file__).resolve().parent.parent
PREFIXES = ("m4c_cart_pendulum", "m4c_pdf_composition")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--completion-only", nargs=3,
                        metavar=("PREFIX", "STOP", "MIN_SAMPLES"))
    args = parser.parse_args()
    if args.completion_only:
        prefix, stop, count = args.completion_only
        stop, count = float(stop), int(count)
        if prefix not in PREFIXES or not math.isfinite(stop) or stop <= 0 or count < 2:
            parser.error("expected an M4C prefix, positive finite stop, and at least two samples")
        check_completion(prefix, stop, count)
        return

    from verify_m4c_cart import verify_cart
    from verify_m4c_pdf import verify_pdf

    cases = {"cart-pendulum-spring": verify_cart(),
             "released-spring-chain": verify_pdf()}
    sources = {
        "scripts/verify_m4c.py", "scripts/verify_m4c_cart.py", "scripts/verify_m4c_pdf.py",
        "scripts/verify_m4.py", "scripts/native_m4c.mos", "scripts/export_native_csv.py",
        ".github/workflows/composition-modelica.yml", "01_mechanics.pdf",
        "DomelicaLab/Examples/CartPendulumSpring3D.mo",
        "DomelicaLab/Examples/ReleasedSpringChain3D.mo",
        "DomelicaLab/package.mo", "DomelicaLab/package.order",
        "DomelicaLab/Examples/package.mo", "DomelicaLab/Examples/package.order",
    }
    inputs = {f"{prefix}{suffix}" for prefix in PREFIXES
              for suffix in ("_res.mat", "_res.csv", "_visual.xml", ".log")}
    inputs.update(f"artifacts/{prefix}-completion.json" for prefix in PREFIXES)
    inputs.add("m4c-native-toolchain.txt")
    report = {
        "passed": True,
        "cases": cases,
        "method": "Independent nonlinear cart oracle with step convergence, closed-form released-chain modes, and all-native-sample geometry, force and energy balances",
        "sourceSHA256": {name: digest(ROOT / name) for name in sorted(sources)},
        "inputsSHA256": {name: digest(ROOT / name) for name in sorted(inputs)},
        "limitations": [
            "Two nominal illustrative recordings; no broad parameter sweep or experimental validation.",
            "The cart has an ideal horizontal guide, an ideal revolute joint, a massless rigid rod and a point-mass bob.",
            "The wall spring exerts an external force; cart-pendulum horizontal momentum is checked against its impulse, not assumed conserved.",
            "The chain recording starts immediately after support removal. It does not simulate a cutting event or topology change.",
            "Symmetric freely moving chain bodies stay vertical in this nominal run; no vertical guides, collisions, spring mass, damping or coil contact are modeled.",
            "Browser playback verification is separate from native numerical checks and does not establish OMEdit GUI behavior.",
        ],
    }
    output = ROOT / "artifacts/m4c-metrics.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    for name, case in cases.items():
        print(f"PASS {name}: {case['samples']} native samples; errors {json.dumps(case['maxErrors'], sort_keys=True)}")
    print(f"PASS M4C physics report: {output}")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
