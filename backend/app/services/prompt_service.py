import os
import logging
import yaml
from typing import Dict, Any

logger = logging.getLogger(__name__)

class PromptService:
    _cache: Dict[str, Dict[str, Any]] = {}
    PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")

    @classmethod
    def load_prompt_file(cls, filename: str) -> Dict[str, Any]:
        """Loads and caches the prompt YAML file."""
        if filename in cls._cache:
            return cls._cache[filename]
        
        filepath = os.path.join(cls.PROMPTS_DIR, filename)
        if not os.path.exists(filepath):
            logger.error("Prompt file not found: %s", filepath)
            raise FileNotFoundError(f"Prompt file not found at {filepath}")
            
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                cls._cache[filename] = data
                return data
        except Exception as e:
            logger.error("Failed to parse prompt file %s: %s", filepath, e)
            raise

    @classmethod
    def get_prompt(cls, filename: str, key: str, version: str = None) -> str:
        """
        Gets a prompt template from a file for the specified key and version.
        If version is not provided, the active_version from the YAML is used.
        """
        try:
            data = cls.load_prompt_file(filename)
            active_ver = version or data.get("active_version", "v1.0")
            versions = data.get("versions", {})
            version_data = versions.get(active_ver, {})
            
            if key not in version_data:
                logger.error("Key %s not found in version %s of %s", key, active_ver, filename)
                raise KeyError(f"Prompt key '{key}' not found in version '{active_ver}' of '{filename}'")
                
            return version_data[key]
        except Exception as e:
            logger.error("Error fetching prompt %s[%s] (version: %s): %s", filename, key, version, e)
            raise
            
    @classmethod
    def clear_cache(cls):
        """Clears the cached templates to allow loading updated prompt files from disk."""
        cls._cache.clear()
        logger.info("Prompt template cache cleared.")
