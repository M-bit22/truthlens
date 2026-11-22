"""Write requirements.txt using the EXACT library versions your model was trained with.

Run it inside the virtual environment you trained the model in:
    python tools/pin_versions.py
A saved scikit-learn model must be loaded by the same scikit-learn version, so this matters.
"""
import importlib.metadata as md
import sys
from pathlib import Path

pinned = []
for name in ["scikit-learn", "numpy", "scipy", "joblib"]:
    pinned.append(f"{name}=={md.version(name)}")

lines = ["streamlit>=1.40,<2", *pinned, "requests>=2.31,<3", "beautifulsoup4>=4.12,<5"]
Path(__file__).resolve().parents[1].joinpath("requirements.txt").write_text("\n".join(lines) + "\n")
print("Wrote requirements.txt:")
print("\n".join("  " + l for l in lines))
print(f"\nYour Python is {sys.version.split()[0]}. Pick the same minor version (e.g. 3.12) in Streamlit's Advanced settings.")
