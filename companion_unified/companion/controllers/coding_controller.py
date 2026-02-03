from __future__ import annotations
import os, subprocess
from datetime import datetime
from companion.core.types import ExecutionResult, Intent

class CodingController:
    def __init__(self, artifacts_dir: str):
        self.artifacts_dir = artifacts_dir

    def execute(self, intent: Intent) -> ExecutionResult:
        os.makedirs(os.path.join(self.artifacts_dir, "coding"), exist_ok=True)
        if intent.type != "run_tests":
            return ExecutionResult("skipped", [], "unsupported_intent")

        repo_path = intent.payload.get("repo", ".")
        cmd = (intent.payload.get("suite") or "pytest -q").split()
        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(self.artifacts_dir, "coding", f"tests_{stamp}.out.txt")
        err_path = os.path.join(self.artifacts_dir, "coding", f"tests_{stamp}.err.txt")

        try:
            p = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=1200)
            open(out_path, "w", encoding="utf-8").write(p.stdout)
            open(err_path, "w", encoding="utf-8").write(p.stderr)
            return ExecutionResult("ok" if p.returncode == 0 else "fail", [out_path, err_path], f"rc={p.returncode}")
        except Exception as e:
            open(err_path, "w", encoding="utf-8").write(str(e))
            return ExecutionResult("fail", [err_path], "runner_error")
