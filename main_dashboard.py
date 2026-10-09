"""Avvia la dashboard Streamlit dalla root del progetto."""

from pathlib import Path
import subprocess
import sys


def main():
    app_path = Path(__file__).resolve().parent / "app.py"
    return subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]]
    )


if __name__ == "__main__":
    raise SystemExit(main())
