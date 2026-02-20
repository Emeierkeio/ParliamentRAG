"""
Configuration management for the Multi-View RAG system.

This module loads configuration from:
1. config/default.yaml - All weights, thresholds, and settings
2. .env - Secrets only (API keys, passwords)

This system uses OpenAI API for LLM inference.

"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from functools import lru_cache

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Project root directory
# config.py is at: backend/app/config.py
# In Docker: /app/app/config.py → .parent.parent = /app/ (backend root)
# Locally: .parent.parent.parent = project root (ParliamentRAG/)
# config/ is at backend/config/ (Docker) or ParliamentRAG/config/ (local)
PROJECT_ROOT = Path(__file__).parent.parent  # backend/ or /app/
CONFIG_DIR = PROJECT_ROOT / "config"
if not CONFIG_DIR.exists():
    # Fallback for local dev: config/ at project root
    CONFIG_DIR = PROJECT_ROOT.parent / "config"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    ONLY secrets are stored here. All other configuration is in YAML.
    """
    # Neo4j Connection
    neo4j_uri: str = Field(
        default="bolt://localhost:7689",
        description="Neo4j Bolt URI"
    )
    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j username"
    )
    neo4j_password: str = Field(
        description="Neo4j password (REQUIRED)"
    )

    # OpenAI API - ONLY provider for LLM inference
    openai_api_key: str = Field(
        description="OpenAI API key (REQUIRED)"
    )

    
    # This system uses OpenAI for all LLM inference.
    

    # Debug settings
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


class ConfigLoader:
    """Loads and manages YAML configuration."""

    def __init__(self, config_dir: Path = CONFIG_DIR):
        self.config_dir = config_dir
        self._config: Optional[Dict[str, Any]] = None
        self._commissioni_topics: Optional[Dict[str, Any]] = None

    def load_config(self) -> Dict[str, Any]:
        """Load the main configuration file."""
        if self._config is not None:
            return self._config

        config_path = self.config_dir / "default.yaml"
        if not config_path.exists():
            logger.warning(f"Config file not found at {config_path}, using defaults")
            self._config = self._get_default_config()
        else:
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {config_path}")

        return self._config

    def load_commissioni_topics(self) -> Dict[str, Any]:
        """Load commission topic mapping."""
        if self._commissioni_topics is not None:
            return self._commissioni_topics

        topics_path = self.config_dir / "commissioni_topics.yaml"
        if not topics_path.exists():
            logger.warning(f"Commission topics not found at {topics_path}")
            self._commissioni_topics = {"commissioni": {}}
        else:
            with open(topics_path, "r", encoding="utf-8") as f:
                self._commissioni_topics = yaml.safe_load(f)
            logger.info(f"Loaded commission topics from {topics_path}")

        return self._commissioni_topics

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration if YAML not found."""
        return {
            "retrieval": {
                "dense_channel": {
                    "top_k": 200,
                    "similarity_threshold": 0.3
                },
                "graph_channel": {
                    "lexical_keywords_min_match": 1,
                    "semantic_similarity_threshold": 0.4,
                    "max_acts_per_query": 100
                },
                "merger": {
                    "diversity_weight": 0.2,
                    "coverage_weight": 0.3,
                    "authority_weight": 0.3,
                    "relevance_weight": 0.2
                }
            },
            "authority": {
                "weights": {
                    "profession": 0.10,
                    "education": 0.10,
                    "committee": 0.20,
                    "acts": 0.25,
                    "interventions": 0.30,
                    "role": 0.05
                },
                "time_decay": {
                    "acts_half_life_days": 365,
                    "speeches_half_life_days": 180
                },
                "normalization": "percentile",
                "max_component_contribution": 0.8
            },
            "compass": {
                "purpose": "multi-view coverage",
                "anchors": {
                    "left": {
                        "groups": [
                            "Alleanza Verdi e Sinistra",
                            "Partito Democratico - Italia Democratica e Progressista"
                        ],
                        "confidence": 0.8
                    },
                    "center": {
                        "groups": [
                            "Azione - Popolari Europeisti Riformatori - Renew Europe",
                            "Italia Viva - Il Centro - Renew Europe",
                            "Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC e Italia al Centro) - MAIE - Centro Popolare"
                        ],
                        "confidence": 0.6
                    },
                    "right": {
                        "groups": [
                            "Fratelli d'Italia",
                            "Lega - Salvini Premier",
                            "Forza Italia - Berlusconi Presidente - PPE"
                        ],
                        "confidence": 0.8
                    }
                },
                "ambiguous": {
                    "Movimento 5 Stelle": {
                        "default_position": "left",
                        "confidence": 0.5
                    }
                },
                "unclassified": ["Misto"],
                "clustering": {
                    "min_fragments_for_kde": 3,
                    "kde_bandwidth": "scott"
                }
            },
            "generation": {
                "models": {
                    "analyst": "gpt-4o",
                    "writer": "gpt-4o",
                    "integrator": "gpt-4o"
                },
                "parameters": {
                    "max_tokens": 4000,
                    "temperature": 0.3,
                    "top_p": 1.0
                },
                "require_all_parties": True,
                "no_evidence_message": "Nel corpus analizzato non risultano interventi rilevanti su questo tema."
            },
            "coalitions": {
                "maggioranza": [
                    "Fratelli d'Italia",
                    "Lega - Salvini Premier",
                    "Forza Italia - Berlusconi Presidente - PPE",
                    "Noi Moderati (Noi con l'Italia, Coraggio Italia, UDC e Italia al Centro) - MAIE - Centro Popolare"
                ],
                "opposizione": [
                    "Partito Democratico - Italia Democratica e Progressista",
                    "Movimento 5 Stelle",
                    "Alleanza Verdi e Sinistra",
                    "Azione - Popolari Europeisti Riformatori - Renew Europe",
                    "Italia Viva - Il Centro - Renew Europe",
                    "Misto"
                ]
            },
            "citation": {
                "method": "offset",
                "format": "«{quote}» [{speaker}, {party}, {date}, ID:{id}]",
                "verify_on_insert": True
            }
        }

    def save_config(self, data: Dict[str, Any]) -> None:
        """Apply configuration in-memory only (not persisted to disk).

        Changes take effect immediately for the current process but are
        lost on restart, preserving config/default.yaml as the source of truth.
        """
        self._config = data
        logger.info("Applied configuration in-memory (not persisted to disk)")

    @property
    def retrieval(self) -> Dict[str, Any]:
        """Get retrieval configuration."""
        return self.load_config().get("retrieval", {})

    @property
    def authority(self) -> Dict[str, Any]:
        """Get authority configuration."""
        return self.load_config().get("authority", {})

    @property
    def compass(self) -> Dict[str, Any]:
        """Get compass configuration."""
        return self.load_config().get("compass", {})

    @property
    def generation(self) -> Dict[str, Any]:
        """Get generation configuration."""
        return self.load_config().get("generation", {})

    @property
    def coalitions(self) -> Dict[str, List[str]]:
        """Get coalition definitions."""
        return self.load_config().get("coalitions", {})

    @property
    def citation(self) -> Dict[str, Any]:
        """Get citation configuration."""
        return self.load_config().get("citation", {})

    def get_coalition(self, group_name: str) -> str:
        """
        Determine which coalition a group belongs to.

        Uses case-insensitive matching with normalized hyphens to handle
        DB names (UPPERCASE) vs config names (display case).

        Args:
            group_name: Parliamentary group name

        Returns:
            'maggioranza' or 'opposizione'
        """
        if not group_name:
            return "opposizione"

        def normalize(name: str) -> str:
            return name.upper().replace(" - ", "-").replace("- ", "-").replace(" -", "-")

        group_norm = normalize(group_name)
        coalitions = self.coalitions
        for coalition, groups in coalitions.items():
            for g in groups:
                if normalize(g) == group_norm:
                    return coalition
        # Default to opposizione for unknown groups
        return "opposizione"

    def get_all_parties(self) -> List[str]:
        """Get list of all parliamentary groups."""
        coalitions = self.coalitions
        all_parties = []
        for groups in coalitions.values():
            all_parties.extend(groups)
        return all_parties


# Global instances
@lru_cache()
def get_settings() -> Settings:
    """Get application settings (cached)."""
    return Settings()


@lru_cache()
def get_config() -> ConfigLoader:
    """Get configuration loader (cached)."""
    return ConfigLoader()
