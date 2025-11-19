"""
Prompt management for QA Agent.

This module handles loading prompts from either:
- Local definitions (default)
- Langfuse prompt management (when USE_LANGFUSE_PROMPTS=true)
"""

import os
from typing import Optional
from functools import lru_cache


# Local prompt definitions
LOCAL_PROMPTS = {
    "QA Agent main instructions": """
    You are QA Assistant Agent, a senior-quality specialist. Guide users on testing strategy, 
    answer QA questions, suggest targeted test cases, outline retest focus for defects, and prioritize features by risk and project goals.
    Draw on provided tools for JIRA data when feature or bug IDs are supplied.
"""
}


@lru_cache(maxsize=32)
def get_prompt_from_langfuse(prompt_name: str, label: Optional[str] = None, version: Optional[int] = None) -> str:
    """
    Retrieve a prompt from Langfuse.
    
    Args:
        prompt_name: Name of the prompt in Langfuse
        label: Optional label (e.g., "production", "latest")
        version: Optional specific version number
        
    Returns:
        The prompt text/instructions
        
    Raises:
        Exception: If prompt cannot be retrieved from Langfuse
    """
    try:
        from langfuse import Langfuse
        
        langfuse = Langfuse()
        
        # Get prompt with appropriate parameters
        if version is not None:
            prompt = langfuse.get_prompt(prompt_name, version=version)
        elif label is not None:
            prompt = langfuse.get_prompt(prompt_name, label=label)
        else:
            prompt = langfuse.get_prompt(prompt_name)
        
        # Extract the prompt text/template
        # Langfuse prompts typically have a .prompt or .compile() method
        if hasattr(prompt, 'prompt'):
            return prompt.prompt
        elif hasattr(prompt, 'compile'):
            return prompt.compile()
        else:
            return str(prompt)
            
    except ImportError:
        raise ImportError(
            "Langfuse is not installed. Install it with: pip install langfuse"
        )
    except Exception as e:
        raise Exception(f"Failed to retrieve prompt '{prompt_name}' from Langfuse: {e}")


def get_prompt(prompt_name: str, label: Optional[str] = None, version: Optional[int] = None) -> str:
    """
    Get a prompt from either Langfuse or local storage.
    
    Behavior is controlled by the USE_LANGFUSE_PROMPTS environment variable:
    - If USE_LANGFUSE_PROMPTS=true: Fetch from Langfuse
    - Otherwise: Use local prompt definitions
    
    Args:
        prompt_name: Name of the prompt
        label: Optional Langfuse label (only used when USE_LANGFUSE_PROMPTS=true)
        version: Optional Langfuse version (only used when USE_LANGFUSE_PROMPTS=true)
        
    Returns:
        The prompt text/instructions
    """
    use_langfuse = os.getenv("USE_LANGFUSE_PROMPTS", "false").lower() in ("true", "1", "yes")
    
    if use_langfuse:
        try:
            print(f"[prompts] Retrieving '{prompt_name}' from Langfuse (label={label}, version={version})")
            return get_prompt_from_langfuse(prompt_name, label=label, version=version)
        except Exception as e:
            print(f"[prompts] Failed to retrieve from Langfuse: {e}")
            print(f"[prompts] Falling back to local prompt for '{prompt_name}'")
            # Fall back to local prompt
            return _get_local_prompt(prompt_name)
    else:
        print(f"[prompts] Using local prompt for '{prompt_name}'")
        return _get_local_prompt(prompt_name)


def _get_local_prompt(prompt_name: str) -> str:
    """
    Get a prompt from local definitions.
    
    Args:
        prompt_name: Name of the prompt
        
    Returns:
        The prompt text/instructions
        
    Raises:
        KeyError: If prompt name is not found in local definitions
    """
    if prompt_name not in LOCAL_PROMPTS:
        raise KeyError(
            f"Prompt '{prompt_name}' not found in local definitions. "
            f"Available prompts: {list(LOCAL_PROMPTS.keys())}"
        )
    return LOCAL_PROMPTS[prompt_name].strip()


def clear_langfuse_cache() -> None:
    """Clear the Langfuse prompt cache. Useful for testing or forcing refresh."""
    get_prompt_from_langfuse.cache_clear()

