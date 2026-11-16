"""Vercel ASGI entry point; paths remain /api/auth, /api/states, etc."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app
