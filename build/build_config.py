"""
BuildConfig: centralized configuration for chunking and build parameters.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BuildConfig:
    chunk_size: int = 1200
    chunk_overlap: int = 250
    min_speech_length: int = 100
    batch_size: int = 1000


def load_config(path: Optional[str] = None) -> BuildConfig:
    """Load BuildConfig from a YAML file if provided, otherwise return defaults."""
    if path is None:
        return BuildConfig()

    try:
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        chunking = data.get('chunking', {})
        return BuildConfig(
            chunk_size=chunking.get('chunk_size', 1200),
            chunk_overlap=chunking.get('chunk_overlap', 250),
            min_speech_length=chunking.get('min_speech_length', 100),
            batch_size=chunking.get('batch_size', 1000),
        )
    except FileNotFoundError:
        return BuildConfig()
