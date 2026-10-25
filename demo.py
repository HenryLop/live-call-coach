"""One-command demo: replay two invented calls through the pipeline with the offline stub model.

    python demo.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from live_call_coach import cli  # noqa: E402

print("=== interview mode: bundled transcript, stub model ===\n")
cli.main(["--mode", "interview"])
print("\n=== meeting mode: read-only reader on the offline simulator, then coach from the saved session ===\n")
session = os.path.join(tempfile.mkdtemp(prefix="coach-demo-"), "session")
cli.main(["--mode", "meeting", "--simulate", session])
