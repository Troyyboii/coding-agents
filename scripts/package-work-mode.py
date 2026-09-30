"""Generate or check portable ChatGPT Work Mode skill packages."""

from __future__ import annotations

import argparse
import sys

from work_mode_packages import DIST_ROOT, build_packages, load_manifest, packages_are_current, validate_packages


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
                    print(f"ERROR: Work Mode packaging failed: {details.get('error', 'unknown error')}", file=sys.stderr)
                else:
                    print(f"ERROR: Work Mode packages are stale: {DIST_ROOT}", file=sys.stderr)
                return 1
            print(f"Work Mode packages are valid and current: {len(load_manifest()['skills'])} packages.")
            return 0
        build_packages()
        errors = validate_packages()
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Generated portable Work Mode packages: {DIST_ROOT}")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: Work Mode packaging failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
