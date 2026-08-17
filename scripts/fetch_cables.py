"""
Fetches Taiwan submarine cable data for 主題2 (Uplink) from smc.peering.tw.

The underlying source repo (seadog007/tw-submarine-cable) is private, but the
built static site (smc.peering.tw, deployed from the smc.peering.tw repo's
gh-pages branch) is public and code-splits each cable into its own small JS
module under assets/, plus a shared data/incidents.json. This script:

1. Lists assets/*.js on gh-pages via the GitHub API (not hardcoded filenames,
   since Vite's content hashes change on every rebuild).
2. Downloads each cable chunk and runs it through Node.js (via
   _extract_js_module.mjs) to import it as a real ES module and read its
   default export — far more robust than regexing minified JS.
3. Downloads data/incidents.json directly.

Requires Node.js on PATH. Run:
    python scripts/fetch_cables.py
"""
import json
import subprocess
import sys
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "uplink"
TMP_DIR = OUT_DIR / "_tmp_chunks"
EXTRACTOR = Path(__file__).resolve().parent / "_extract_js_module.mjs"

REPO = "seadog007/smc.peering.tw"
TREE_URL = f"https://api.github.com/repos/{REPO}/git/trees/gh-pages?recursive=1"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/gh-pages"

# Non-cable JS bundles that happen to live in the same assets/ folder.
NON_CABLE_PREFIXES = ("index-", "maplibre-gl-")


def list_cable_chunks() -> list[str]:
    resp = requests.get(TREE_URL, timeout=15)
    resp.raise_for_status()
    tree = resp.json()["tree"]

    paths = []
    for item in tree:
        path = item["path"]
        if not path.startswith("assets/") or not path.endswith(".js"):
            continue
        filename = path.rsplit("/", 1)[-1]
        if filename.startswith(NON_CABLE_PREFIXES):
            continue
        paths.append(path)
    return paths


def extract_cable(js_path: str) -> dict:
    resp = requests.get(f"{RAW_BASE}/{js_path}", timeout=15)
    resp.raise_for_status()

    tmp_file = TMP_DIR / (Path(js_path).stem + ".mjs")
    tmp_file.write_text(resp.text, encoding="utf-8")

    result = subprocess.run(
        ["node", str(EXTRACTOR), str(tmp_file)],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f"node failed for {js_path}: {result.stderr}")

    return json.loads(result.stdout)


def fetch_incidents() -> list[dict]:
    resp = requests.get(f"{RAW_BASE}/data/incidents.json", timeout=15)
    resp.raise_for_status()
    return resp.json()


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    chunk_paths = list_cable_chunks()
    print(f"found {len(chunk_paths)} cable chunks")

    cables = []
    failed = []
    for path in chunk_paths:
        try:
            cables.append(extract_cable(path))
        except Exception as e:
            failed.append((path, str(e)))
            print(f"  failed: {path}: {e}")

    cables.sort(key=lambda c: c["id"])
    (OUT_DIR / "cables.json").write_text(json.dumps(cables, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(cables)} cables -> {OUT_DIR / 'cables.json'}")
    if failed:
        print(f"{len(failed)} chunks failed to parse (see above)")

    incidents = fetch_incidents()
    (OUT_DIR / "incidents.json").write_text(json.dumps(incidents, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(incidents)} incidents -> {OUT_DIR / 'incidents.json'}")

    for f in TMP_DIR.glob("*.mjs"):
        f.unlink()
    TMP_DIR.rmdir()


if __name__ == "__main__":
    main()
