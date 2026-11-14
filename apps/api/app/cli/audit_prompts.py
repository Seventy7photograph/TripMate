# 文件说明：运维命令行工具：audit_prompts。
import argparse
import json
from pathlib import Path

from app.core.config import PROJECT_ROOT, get_settings
from app.prompts.audit import audit_prompt_catalog
from app.prompts.catalog import PromptCatalog


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit TripMate prompt versions and inventory coverage"
    )
    parser.add_argument("--root", type=Path)
    parser.add_argument("--inventory", type=Path)
    args = parser.parse_args()

    settings = get_settings()
    report = audit_prompt_catalog(
        PromptCatalog(args.root or settings.prompts_root),
        args.inventory
        or PROJECT_ROOT / "apps" / "api" / "prompts" / "INVENTORY.md",
    )
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    raise SystemExit(1 if report.errors else 0)


if __name__ == "__main__":
    main()
