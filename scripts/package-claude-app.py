"""Generate or check portable Claude app (claude.ai) Custom Skill ZIP packages."""

from __future__ import annotations

import argparse
import sys

from claude_app_packages import DIST_ROOT, active_skill_names, build_packages, packages_are_current, validate_packages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate packages and fail when generated output is stale.")
    args = parser.parse_args(argv)
    try:
        if args.check:
            errors = validate_packages()
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            details: dict[str, str] = {}
            if not packages_are_current(details=details):
                if details.get("status") == "build_failed":
                    print(f"ERROR: Claude app packaging failed: {details.get('error', 'unknown error')}", file=sys.stderr)
                else:
                    print(f"ERROR: Claude app packages are stale: {DIST_ROOT}", file=sys.stderr)
                return 1
            print(f"Claude app packages are valid and current: {len(active_skill_names())} packages.")
            return 0
        build_packages()
        errors = validate_packages()
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Generated portable Claude app packages: {DIST_ROOT}")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: Claude app packaging failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
