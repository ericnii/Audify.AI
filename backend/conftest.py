import sys
import os

# Ensure the repository root is on sys.path so tests can import `backend` as a
# top-level package when pytest runs from the repository root.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
