"""Run reviewed static pytest commands and preserve package evidence."""

import argparse
from datetime import datetime, timezone
from importlib import metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from car_rental.observability import record_test_run

parser = argparse.ArgumentParser()
parser.add_argument("package")
parser.add_argument("phase")
parser.add_argument("paths", nargs="+")
parser.add_argument("--expect", type=int, default=0)
args = parser.parse_args()
out = Path("logs/tdd") / args.package / args.phase
out.mkdir(parents=True, exist_ok=False)
command = [sys.executable, "-m", "pytest", *args.paths, "-q", "--tb=line", "--assert=plain",
           "--show-capture=no", "-p", "no:cacheprovider",
           "--basetemp=.backend-setup/" + args.package.replace("/", "-") + "-" + args.phase,
           "--junitxml=" + (out / "junit.xml").as_posix()]
env = os.environ.copy()
env.update(PYTHONUTF8="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONPATH="src")
env["TDD_EVIDENCE_DIR"] = str(out.resolve())
start = datetime.now(timezone.utc).isoformat()
run = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
output = run.stdout + run.stderr
if any(marker in output for marker in ("synthetic-password-marker", "synthetic-token-marker", "synthetic-contact-marker")):
    raise RuntimeError("Unsafe captured evidence; not persisted")
(out / "runner.txt").write_text(output, encoding="utf-8")
tree = ET.parse(out / "junit.xml")
for suite in tree.getroot().iter("testsuite"):
    suite.set("hostname", "local")
(out / "junit.xml").write_text(ET.tostring(tree.getroot(), encoding="unicode") + "\n", encoding="utf-8")
safe_command = [".venv-backend/Scripts/python.exe", *command[1:]]
record_test_run(out / "runs.jsonl", run_id=args.phase, command=safe_command,
                exit_code=run.returncode, result="PASS" if run.returncode == 0 else "FAIL")
(out / "manifest.json").write_text(json.dumps({
    "started_at": start, "finished_at": datetime.now(timezone.utc).isoformat(),
    "command": safe_command, "exit_code": run.returncode,
    "python": sys.version.split()[0], "pytest": metadata.version("pytest"),
    "test_ids": [c.attrib for c in tree.getroot().iter("testcase")],
}, indent=2) + "\n", encoding="utf-8")
print(output)
if run.returncode != args.expect:
    raise SystemExit("Unexpected pytest exit; analyze before continuing")
