"""Ensure the project root is importable for scripts under scripts/*/.

Usage at the top of any nested script (before app imports):

    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
