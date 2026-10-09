"""Punto di avvio del keyword extractor dalla root del progetto."""

from pathlib import Path
import runpy
import sys


def main():
    extractor_dir = Path(__file__).resolve().parent / "key_extractor"
    sys.path.insert(0, str(extractor_dir))
    runpy.run_path(str(extractor_dir / "main.py"), run_name="__main__")


if __name__ == "__main__":
    main()
