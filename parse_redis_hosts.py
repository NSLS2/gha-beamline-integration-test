"""
parse_redis_hosts.py — extract Redis hostnames from nslsii.configure_base() calls.

Walks all *.py files under <profile_dir>/startup/, parses each file with the
Python ``ast`` module, and prints every unique string literal passed as the
``redis_url`` keyword argument to a function named ``configure_base``.

Usage::

    python3 parse_redis_hosts.py /path/to/profile-collection

One hostname is printed per line; duplicates are suppressed.  The script exits
with code 0 even when no hostnames are found (the caller should treat empty
output as "no custom host required").
"""

import ast
import glob
import os
import sys


def find_redis_hosts(profile_dir: str) -> list[str]:
    """Return a deduplicated list of redis_url string literals found in startup files."""
    startup_glob = os.path.join(profile_dir, "startup", "*.py")
    hosts: list[str] = []
    seen: set[str] = set()

    for filepath in sorted(glob.glob(startup_glob)):
        try:
            with open(filepath, encoding="utf-8", errors="replace") as fh:
                source = fh.read()
            tree = ast.parse(source, filename=filepath)
        except SyntaxError as exc:
            print(f"# Warning: could not parse {filepath}: {exc}", file=sys.stderr)
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            # Match bare name or attribute: configure_base(...) or nslsii.configure_base(...)
            func_name = func.attr if isinstance(func, ast.Attribute) else (
                func.id if isinstance(func, ast.Name) else None
            )
            if func_name != "configure_base":
                continue
            for kw in node.keywords:
                if kw.arg == "redis_url" and isinstance(kw.value, ast.Constant):
                    host = kw.value.value
                    if isinstance(host, str) and host not in seen:
                        seen.add(host)
                        hosts.append(host)

    return hosts


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <profile_dir>", file=sys.stderr)
        sys.exit(1)

    profile_dir = sys.argv[1]
    hosts = find_redis_hosts(profile_dir)
    for host in hosts:
        print(host)


if __name__ == "__main__":
    main()
