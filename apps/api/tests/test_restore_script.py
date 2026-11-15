# 文件说明：后端自动化测试：test_restore_script。
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RESTORE_SCRIPT = REPO_ROOT / "scripts" / "restore.ps1"


def test_restore_rejects_dump_that_does_not_match_manifest(
    tmp_path: Path,
) -> None:
    pwsh = shutil.which("pwsh")
    if pwsh is None:
        pytest.skip("PowerShell 7 is required for restore-script regression")
    backup = tmp_path / "tripmate-test.dump"
    backup.write_bytes(b"not-a-real-dump")
    (tmp_path / "tripmate-test.dump.manifest.json").write_text(
        json.dumps(
            {
                "format_version": 1,
                "file": str(backup),
                "size_bytes": backup.stat().st_size,
                "sha256": "0" * 64,
                "counts": {},
                "uploads": None,
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            pwsh,
            "-NoProfile",
            "-File",
            str(RESTORE_SCRIPT),
            "-BackupFile",
            str(backup),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "SHA-256" in f"{result.stdout}\n{result.stderr}"
