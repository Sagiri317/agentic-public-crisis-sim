"""Synthetic public-function crisis stress test, not a real-world risk estimator."""
from .config import compile_config
from .simulation import simulate

__all__ = ["compile_config", "simulate"]
