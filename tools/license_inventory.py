"""Collect version-matched dependency metadata and shipped notices. No installs/network."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("requirements-lock.txt", "requirements-text-lock.txt",
           "installer/optional-constraints.txt", "requirements-whisper.txt",
           "requirements-kokoro.txt", "requirements-piper.txt", "requirements-ocr.txt")


def collect(output):
    declared = {}
    for source in SOURCES:
        for line in (ROOT/source).read_text(encoding="utf-8").splitlines():
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line.strip())
            if match:
                name, version = match.groups()
                key = re.sub(r"[-_.]+", "-", name).lower()
                item = declared.setdefault(key, {"name":name, "versions":[], "requirements":[]})
                if version not in item["versions"]:
                    item["versions"].append(version)
                item["requirements"].append(source)
    rows = []
    for key, entry in sorted(declared.items()):
        row = dict(entry, notice_files=[])
        rows.append(row)
        try:
            dist = metadata.distribution(entry["name"])
        except metadata.PackageNotFoundError:
            row["status"] = "missing"
            continue
        row.update(installed_version=dist.version,
                   status="matched" if dist.version in entry["versions"] else "version_mismatch")
        info = dist.metadata
        row["license_expression"] = info.get("License-Expression", "")
        row["license_metadata"] = info.get("License", "")
        row["license_classifiers"] = [v for v in info.get_all("Classifier", []) if v.startswith("License ::")]
        row["project_urls"] = info.get_all("Project-URL", [])
        row["homepage"] = info.get("Home-page", "")
        if row["status"] != "matched":
            continue
        for file in dist.files or []:
            if not re.match(r"^(license|licence|copying|notice|authors)([._-]|$)", file.name, re.I):
                continue
            if ".." in file.parts or file.suffix.lower() in (".dll", ".exe", ".py", ".pyc"):
                continue
            source = Path(dist.locate_file(file))
            if not source.is_file() or source.stat().st_size > 2*1024*1024:
                continue
            content = source.read_bytes()
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                continue
            relative = Path("python")/(key+"-"+dist.version)/Path(*file.parts)
            target = output/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            row["notice_files"].append({"path":relative.as_posix(),
                                        "sha256":hashlib.sha256(content).hexdigest()})
        row["notice_status"] = "copied" if row["notice_files"] else "no_notice_in_distribution"
    output.mkdir(parents=True, exist_ok=True)
    (output/"python-packages.json").write_text(json.dumps({
        "scope":"Declared pinned packages only; metadata is not a complete native-binary audit.",
        "sources":list(SOURCES), "packages":rows}, indent=2)+"\n", encoding="utf-8")
    print("Packages:", len(rows), "matched:", sum(r["status"]=="matched" for r in rows),
          "notice files:", sum(len(r["notice_files"]) for r in rows))
    print("No shipped notice text:", ", ".join(r["name"] for r in rows
          if r.get("notice_status")=="no_notice_in_distribution") or "none")
    return 0 if all(r["status"]=="matched" for r in rows) else 1


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT/"docs/licenses")
    raise SystemExit(collect(parser.parse_args().output))
