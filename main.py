"""
AURa — top-level entry point.
Delegates to aura.main so that both `python main.py` and `python -m aura` work.
"""

import sys
import os

# Ensure the package root is on the path when running directly as a script.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aura.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
