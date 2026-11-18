#!/usr/bin/env python3
"""Publish only explicitly selected, hash-verified native/browser CI outputs."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_release():
    release = json.loads((ROOT / "site/release.json").read_text())
    if release["repository"] != "physicsvigilante/domelica_lab":
        raise ValueError("Unexpected publication repository")
    if not re.fullmatch(r"[0-9a-f]{40}", release["revision"]):
        raise ValueError("Publication requires an immutable source revision")
    if type(release["runId"]) is not int or release["runId"] <= 0:
        raise ValueError("Publication requires a workflow run ID")
    for item in release["viewers"]:
        for key in ("file", "manifest", "report"):
            path = Path(item[key])
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Publication path must remain inside the artifact")
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("Every published HTML file needs its approved SHA-256")
    return release


def check_run(release):
    url = f"https://api.github.com/repos/{release['repository']}/actions/runs/{release['runId']}"
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "domelica-lab-publication",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        run = json.load(response)
    if (run["conclusion"] != "success" or run["status"] != "completed"
            or run["head_sha"] != release["revision"]
            or run["repository"]["full_name"] != release["repository"]
            or run["path"] != ".github/workflows/native-modelica.yml"):
        raise ValueError("Release does not identify a successful native/browser workflow")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            stream.write(f"run_id={release['runId']}\n")
    print(f"PASS selected native/browser run {release['runId']} at {release['revision']}")


def build(release, inputs, output):
    output.mkdir(parents=True, exist_ok=True)
    cards = []
    outputs = {}
    checks = 0
    run_url = f"https://github.com/{release['repository']}/actions/runs/{release['runId']}"
    for item in release["viewers"]:
        source = inputs / item["file"]
        manifest = json.loads((inputs / item["manifest"]).read_text())
        report = json.loads((inputs / item["report"]).read_text())
        digest = sha256(source)
        if (digest != item["sha256"] or digest != manifest.get("previewSHA256")
                or digest != report.get("artifactSha256")
                or manifest.get("revision") != release["revision"]
                or manifest.get("runUrl") != run_url
                or report.get("provenance", {}).get("revision") != release["revision"]
                or report.get("passed") is not True):
            raise ValueError(f"Native, browser, and publication identities differ: {item['file']}")
        if not report.get("steps") or any(step.get("passed") is not True for step in report["steps"]):
            raise ValueError("Browser verification is incomplete")
        if any(report.get(key) for key in ("pageErrors", "consoleErrors", "unexpectedRequests")):
            raise ValueError("Browser evidence contains unexpected errors or requests")
        checks += len(report["steps"])
        for name in (item["file"], item["manifest"], item["report"]):
            destination = output / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(inputs / name, destination)
            outputs[name] = sha256(destination)
        escape = html.escape
        cards.append(
            '<article class="experiment"><div class="card-mark" aria-hidden="true">'
            + ("↔" if item["kind"] == "comparison" else "◉" if item["kind"] == "scenes" else "≈")
            + '</div><p class="tag">' + escape(item["tag"]) + '</p><h2>'
            + escape(item["title"]) + '</h2><p class="description">'
            + escape(item["description"]) + '</p><div class="card-actions"><a class="open" href="'
            + escape(item["file"], quote=True) + '">Open experiment <span aria-hidden="true">↗</span></a>'
            + '<a class="download" download href="' + escape(item["file"], quote=True)
            + '">Download HTML</a></div></article>'
        )
    template = (ROOT / "site/index.template.html").read_text()
    replacements = {"__CARDS__": "\n".join(cards), "__LABEL__": html.escape(release["label"]),
                    "__REVISION__": release["revision"][:12], "__RUN_URL__": run_url,
                    "__CHECKS__": str(checks)}
    for marker, value in replacements.items():
        if template.count(marker) != 1:
            raise ValueError(f"Publication template marker must be unique: {marker}")
        template = template.replace(marker, value)
    (output / "index.html").write_text(template)
    (output / ".nojekyll").write_text("")
    outputs["index.html"] = sha256(output / "index.html")
    publication = {"schema": "domelica.publication.v1", "release": release,
                   "runUrl": run_url, "browserChecks": checks, "filesSHA256": outputs}
    (output / "publication.json").write_text(json.dumps(publication, indent=2) + "\n")
    print(f"PASS site: {len(release['viewers'])} verified viewers, {checks} browser checks, {output}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-run", action="store_true")
    parser.add_argument("--artifacts", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--output", type=Path, default=ROOT / "site-output")
    args = parser.parse_args()
    release = load_release()
    if args.check_run:
        check_run(release)
    else:
        build(release, args.artifacts, args.output)


if __name__ == "__main__":
    main()
