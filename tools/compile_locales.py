#!/usr/bin/env python3
"""Compile .po files to .mo files and regenerate .pot template."""
import subprocess
import sys
import os

LOCALE_DIR = os.path.join(os.path.dirname(__file__), "..", "mdtoepub", "locale")
DOMAIN = "mdtoepub"


def compile_mo():
    """Compile all .po files to .mo files."""
    count = 0
    for lang in os.listdir(LOCALE_DIR):
        po_path = os.path.join(LOCALE_DIR, lang, "LC_MESSAGES", f"{DOMAIN}.po")
        mo_path = os.path.join(LOCALE_DIR, lang, "LC_MESSAGES", f"{DOMAIN}.mo")
        if os.path.exists(po_path):
            try:
                subprocess.run(
                    ["msgfmt", "-o", mo_path, po_path],
                    check=True,
                    capture_output=True,
                )
                print(f"  {lang}: {po_path} -> {mo_path}")
                count += 1
            except FileNotFoundError:
                print("ERROR: msgfmt not found. Install gettext:")
                print("  sudo apt install gettext")
                sys.exit(1)
            except subprocess.CalledProcessError as e:
                print(f"ERROR compiling {po_path}: {e.stderr.decode()}")
    print(f"Compiled {count} .po files.")


def generate_pot():
    """Extract translatable strings from source code to .pot template."""
    src_dir = os.path.join(os.path.dirname(__file__), "..", "mdtoepub")
    pot_path = os.path.join(LOCALE_DIR, f"{DOMAIN}.pot")

    py_files = []
    for root, dirs, files in os.walk(src_dir):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".venv", "locale")]
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))

    try:
        subprocess.run(
            [
                "xgettext",
                "--language=Python",
                "--keyword=_",
                f"--output={pot_path}",
                "--from-code=UTF-8",
                f"--package-name={DOMAIN}",
                "--no-wrap",
            ]
            + py_files,
            check=True,
            capture_output=True,
        )
        print(f"Generated: {pot_path}")
    except FileNotFoundError:
        print("WARNING: xgettext not found. Install gettext:")
        print("  sudo apt install gettext")
        print("Skipping .pot generation.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd in ("all", "pot"):
        print("Generating .pot template...")
        generate_pot()

    if cmd in ("all", "mo"):
        print("Compiling .po -> .mo...")
        compile_mo()

    if cmd not in ("all", "pot", "mo"):
        print(f"Usage: {sys.argv[0]} [all|pot|mo]")
        sys.exit(1)
