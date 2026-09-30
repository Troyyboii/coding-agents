"""Generate or check portable Agent Skills, Gemini, and Kimi distributions."""

from __future__ import annotations

import argparse
import sys

from agent_skill_packages import (
    PORTABLE_DIST,
    build_packages,
    discover_skills,
    packages_are_current,
    validate_packages,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate packages and fail when output is stale.")
    args = parser.parse_args(argv)
    try:
        if args.check:
            errors = validate_packages()
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            if not packages_are_current():
                print(
                    f"ERROR: Agent Skills, Gemini, and Kimi packages are stale: {PORTABLE_DIST}",
                    file=sys.stderr,
                )
                return 1
            print(f"Agent Skills, Gemini, and Kimi packages are valid and current: {len(discover_skills())} skills.")
            return 0
        build_packages()
        errors = validate_packages()
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print("Generated portable Agent Skills, Gemini, and Kimi packages.")
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: Agent Skills packaging failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
