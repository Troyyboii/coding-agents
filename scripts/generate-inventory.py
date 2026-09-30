"""Generate or check the source-backed active repository inventory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repository_inventory import ROOT, collect_inventory, render_inventory, require_repository_path


def generate_inventory(root: Path = ROOT, *, check: bool = False) -> tuple[bool, Path]:
    """Generate inventory for root, or return whether its checked-in copy is current."""

    output_path = root / "docs" / "inventory.md"
    require_repository_path(output_path.parent, root, label="Inventory output directory")
    require_repository_path(output_path, root, label="Inventory output file")
    expected = render_inventory(collect_inventory(root))
    if check:
        actual = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
        return actual == expected, output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(expected, encoding="utf-8", newline="\n")
    return True, output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the generated inventory is stale.")
    args = parser.parse_args()

    if args.check:
        current, output_path = generate_inventory(check=True)
        if not current:
            print(f"Inventory is stale: {output_path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        print(f"Inventory is current: {output_path.relative_to(ROOT)}")
        return 0

    _, output_path = generate_inventory()
    print(f"Generated {output_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
