import sys
from pathlib import Path

# Make `api` importable without setting PYTHONPATH=src (the Worker runtime puts src/ on the path itself).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
