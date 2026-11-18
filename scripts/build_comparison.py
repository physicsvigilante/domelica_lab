#!/usr/bin/env python3
"""Compose two unchanged native viewers around one physical-time playback clock."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoded(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c")


def main() -> None:
    native_path = ROOT / "artifacts/native-scenes.json"
    metrics_path = ROOT / "artifacts/m2-metrics.json"
    native = json.loads(native_path.read_text())
    metrics = json.loads(metrics_path.read_text())
    config = json.loads((ROOT / "viewer/comparisons.json").read_text())
    if native.get("schema") != "domelica.native-scene.v1":
        raise ValueError("Unsupported native scene schema")
    if metrics.get("schema") != "domelica.control-comparison-metrics.v1":
        raise ValueError("Missing verified comparison metrics")
    if native["provenance"]["inputsSHA256"].get("artifacts/m2-metrics.json") != digest(metrics_path):
        raise ValueError("Metrics changed after the native scene payload was built; rebuild it")
    if native.get("metrics") != metrics:
        raise ValueError("Native scene payload and comparison metrics differ")
    if metrics.get("verificationScriptSHA256") != native["provenance"]["sourceSHA256"].get("scripts/verify_m2.py"):
        raise ValueError("Metrics verifier source differs from native scene provenance")
    scene_ids = config["sceneIds"]
    if not scene_ids or len(set(scene_ids)) != len(scene_ids):
        raise ValueError("Comparison scene IDs must be unique and nonempty")
    if len(config["defaultPair"]) != 2 or any(i not in scene_ids for i in config["defaultPair"]):
        raise ValueError("Comparison needs two valid default scene IDs")
    scenes_by_id = {s["id"]: s for s in native["scenes"]}
    metrics_by_id = {case["id"]: case for case in metrics["cases"]}
    selected = []
    for scene_id in scene_ids:
        if scene_id not in scenes_by_id or scene_id not in metrics_by_id:
            raise ValueError(f"Missing native scene or metrics: {scene_id}")
        scene = scenes_by_id[scene_id]
        case = metrics_by_id[scene_id]
        if scene["model"] != case["model"]:
            raise ValueError(f"Metrics and scene model differ: {scene_id}")
        csv_name = case["prefix"] + "_res.csv"
        if csv_name not in native["provenance"]["inputsSHA256"]:
            raise ValueError(f"Native result provenance missing: {csv_name}")
        if case.get("nativeCSV_SHA256") != native["provenance"]["inputsSHA256"][csv_name]:
            raise ValueError(f"Metrics and native result identity differ: {csv_name}")
        for key, suffix in (("nativeXML_SHA256", "_visual.xml"), ("nativeMAT_SHA256", "_res.mat")):
            name = case["prefix"] + suffix
            if not case.get(key) or case[key] != native["provenance"]["inputsSHA256"].get(name):
                raise ValueError(f"Metrics and native geometry/result identity differ: {name}")
        if case.get("verification", {}).get("passed") is not True:
            raise ValueError(f"Native numerical verification did not pass: {scene_id}")
        times = scene["times"]
        if (len(times) < 2 or not all(math.isfinite(t) for t in times)
                or any(b < a for a, b in zip(times, times[1:]))):
            raise ValueError(f"Invalid native time grid: {scene_id}")
        if times[-1] <= times[0]:
            raise ValueError(f"Empty native time range: {scene_id}")
        series = {s["name"]: s for s in scene["series"]}
        required = {s["name"] for s in config["signals"]}
        required.update(s["reference"] for s in config["signals"] if s.get("reference"))
        for name in required:
            if name not in series or len(series[name]["values"]) != len(times):
                raise ValueError(f"Missing comparison series {scene_id}/{name}")
        for signal in config["signals"]:
            if series[signal["name"]]["unit"] != signal["unit"]:
                raise ValueError(f"Comparison units differ for {scene_id}/{signal['name']}")
        selected.append(scene)

    runtime_path = ROOT / "artifacts/three-runtime.js"
    template_path = ROOT / "viewer/preview.template.html"
    exporter_path = ROOT / "scripts/native_scene.py"
    provenance = native["provenance"]
    for path in (template_path, exporter_path):
        if provenance["sourceSHA256"].get(str(path.relative_to(ROOT))) != digest(path):
            raise ValueError(f"Native source identity changed: {path.name}; rebuild native payload")
    if provenance["renderer"]["runtimeSHA256"] != digest(runtime_path):
        raise ValueError("Native payload and renderer bundle differ")
    runtime = runtime_path.read_text(encoding="utf-8")
    viewer = template_path.read_text(encoding="utf-8")
    if viewer.count("__NATIVE_MODEL_DATA__") != 1 or viewer.count("__THREE_RUNTIME__") != 1:
        raise ValueError("Native viewer markers are ambiguous")
    # Reuse the viewer implementation verbatim. Only its data reference and
    # presentation are adapted. Each iframe executes its own Three.js copy;
    # no WebGL class or context is shared across JavaScript realms.
    viewer = viewer.replace("__NATIVE_MODEL_DATA__", "parent.__comparisonData.native")
    viewer = viewer.replace("__THREE_RUNTIME__", runtime)
    wrapper_style = """<style id="comparison-embed-style">
html,body{margin:0;background:transparent;overflow-x:hidden}main{padding:0!important;max-width:none}
.masthead,.intro,.scene-tabs,.timeline,.provenance,.signals{display:none!important}
.layout{display:block!important}.layout>.panel{border:0;border-radius:0;box-shadow:none}
.panel-title{padding:10px 14px!important}.panel-title h2{font-size:11px}
.panel-title .subtle{font-size:10px}#scene{height:330px!important}
.scene-meta{top:12px;font-size:9px}.scene-meta strong{font-size:10px}
.objects summary{padding:10px 14px}.object-body{padding:0 14px 13px}
.error{margin:10px;padding:13px}.camera-axis{top:0}
@media(max-width:450px){#scene{height:300px!important}.camera-label{display:none}}
</style>"""
    viewer = viewer.replace("</head>", wrapper_style + "\n</head>", 1)
    # Stop the viewer's normal autoplay immediately, before its first RAF. The
    # parent will exclusively drive seek(index), including Space-key playback.
    viewer = viewer.replace("</body>", "<script>if(window.__domelica?.available)window.__domelica.seek(0);</script>\n</body>", 1)
    source_paths = [ROOT / "viewer/comparison.template.html", ROOT / "viewer/comparisons.json",
                    ROOT / "scripts/build_comparison.py", ROOT / "scripts/check_comparison.cjs"]
    comparison_provenance = {
        "revision": provenance["revision"],
        "runUrl": provenance["runUrl"],
        "nativeSceneSHA256": digest(native_path),
        "metricsSHA256": digest(metrics_path),
        "rendererTemplateSHA256": digest(template_path),
        "nativeExporterSHA256": digest(exporter_path),
        "rendererRuntimeSHA256": digest(runtime_path),
        "comparisonSourceSHA256": {str(p.relative_to(ROOT)): digest(p) for p in source_paths},
    }
    data = {"schema": "domelica.comparison.v1", "config": config,
            "native": {**native, "scenes": selected}, "metrics": metrics,
            "provenance": comparison_provenance}
    template = (ROOT / "viewer/comparison.template.html").read_text(encoding="utf-8")
    if template.count("__COMPARISON_DATA__") != 1 or template.count("__VIEWER_DOCUMENT__") != 1:
        raise ValueError("Comparison template markers are ambiguous")
    output = ROOT / "artifacts/comparison.html"
    output.write_text(template.replace("__COMPARISON_DATA__", encoded(data))
                      .replace("__VIEWER_DOCUMENT__", encoded(viewer)), encoding="utf-8")
    manifest = {**comparison_provenance, "previewSHA256": digest(output),
                "sceneIds": scene_ids, "defaultPair": config["defaultPair"],
                "bytes": output.stat().st_size}
    (ROOT / "artifacts/comparison-provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"PASS offline native comparison: {len(selected)} cases; {output.stat().st_size} bytes; {manifest['previewSHA256']}")


if __name__ == "__main__":
    main()
