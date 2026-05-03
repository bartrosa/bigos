from __future__ import annotations

import os
import platform
from typing import Literal

Device = Literal["cuda", "mps", "cpu"]


def detect_device() -> Device:
    """Auto-detect best available device. BIGOS_FORCE_CPU=1 forces CPU (e.g. for CI)."""
    if os.environ.get("BIGOS_FORCE_CPU") == "1":
        return "cpu"
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if (
            hasattr(torch.backends, "mps")
            and torch.backends.mps.is_available()
            and platform.system() == "Darwin"
        ):
            return "mps"
    except ImportError:
        pass
    return "cpu"
