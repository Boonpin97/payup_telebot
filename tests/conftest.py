"""Test configuration: ensure project imports resolve and skip Firestore init."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make ``import app`` work without installing the package.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Avoid loading any real .env in tests.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("ENVIRONMENT", "test")
