"""
Langfuse Experiment Runner for QA Agent.

This module provides functionality to run experiments against Langfuse datasets
directly via the SDK - no hosting required for local development.

Usage:
    # Run from CLI:
    python experiments.py --dataset "my-dataset" --run-name "test-run-1"
    
    # Or import and use programmatically:
    from experiments import run_experiment_on_dataset
    result = await run_experiment_on_dataset("my-dataset", "my-run")
"""

import os
import asyncio
import argparse
from datetime import datetime
from typing import Any, Optional
from dataclasses import dataclass

from dotenv import load_dotenv

# Load environment before other imports
load_dotenv()

# Allow nested event loops (needed for Langfuse's run_experiment + async agent)
import nest_asyncio
nest_asyncio.apply()

import observability  # Initialize tracing
from agents import Runner

# Import agent and model from server to ensure same configuration
from server import qa_agent, MODEL_NAME


@dataclass
class ExperimentConfig:
    """Configuration for an experiment run."""
    dataset_name: str
    run_name: Optional[str] = None
    description: Optional[str] = None
    max_concurrency: int = 5
    metadata: Optional[dict[str, Any]] = None
    
    def __post_init__(self):
        if not self.run_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.run_name = f"{self.dataset_name}_{timestamp}"


async def process_dataset_item(item: Any) -> str:
    """
    Process a single dataset item through the QA Agent.
    
    Args:
        item: Dataset item with 'input' field containing the user query
        
    Returns:
        The agent's response text
    """
    # Extract input from the dataset item
    user_input = item.input if hasattr(item, 'input') else item.get('input', '')
    
    if not user_input:
        return "Error: No input provided in dataset item"
    
    # Run the agent (using qa_agent imported from server)
    response = await Runner.run(qa_agent, user_input)
    return response.final_output or ""


def create_experiment_task():
    """
    Create a task function compatible with Langfuse's run_experiment.
    
    The task function receives the dataset item and should return the output.
    Langfuse automatically traces the execution.
    Uses qa_agent imported from server.py.
    """
    def task(*, item, **kwargs) -> str:
        """Synchronous wrapper for the async agent call."""
        return asyncio.run(process_dataset_item(item))
    
    return task


async def run_experiment_on_dataset(
    config: ExperimentConfig,
) -> Any:
    """
    Run an experiment on a Langfuse dataset.
    
    This fetches the dataset from Langfuse and runs your QA agent against
    each item. Results are automatically sent back to Langfuse.
    
    Args:
        config: Experiment configuration
        
    Returns:
        ExperimentResult from Langfuse SDK
    """
    from langfuse import get_client
    
    langfuse = get_client()
    
    print(f"[experiment] Fetching dataset: {config.dataset_name}")
    dataset = langfuse.get_dataset(config.dataset_name)
    
    print(f"[experiment] Dataset loaded with {len(dataset.items)} items")
    print(f"[experiment] Starting run: {config.run_name}")
    
    # Create task using qa_agent from server.py
    task = create_experiment_task()
    
    # Run the experiment (with concurrent execution)
    result = dataset.run_experiment(
        name=config.run_name,
        description=config.description or f"Experiment run for {config.dataset_name}",
        task=task,
        max_concurrency=config.max_concurrency,
        metadata={
            "model": MODEL_NAME,
            "agent": "QA Assistant Agent",
            **(config.metadata or {}),
        },
    )
    
    print(f"[experiment] Experiment completed!")
    print(result.format())
    
    # Ensure all data is flushed to Langfuse
    langfuse.flush()
    
    return result


async def run_experiment_on_local_data(
    data: list[dict[str, Any]],
    experiment_name: str,
    run_name: Optional[str] = None,
    description: Optional[str] = None,
    max_concurrency: int = 5,
) -> Any:
    """
    Run an experiment on local data (without a Langfuse dataset).
    
    Useful for quick tests before creating a dataset in Langfuse.
    
    Args:
        data: List of dicts with 'input' (and optionally 'expected_output')
        experiment_name: Name for this experiment
        run_name: Optional run name
        description: Optional description
        max_concurrency: Maximum concurrent executions (default: 5)
        
    Returns:
        ExperimentResult from Langfuse SDK
    """
    from langfuse import get_client
    
    langfuse = get_client()
    
    print(f"[experiment] Running on {len(data)} local items (concurrency: {max_concurrency})")
    
    # Create task using qa_agent from server.py
    task = create_experiment_task()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    result = langfuse.run_experiment(
        name=experiment_name,
        run_name=run_name or f"local_{timestamp}",
        description=description or "Local data experiment",
        data=data,
        task=task,
        max_concurrency=max_concurrency,
        metadata={"model": MODEL_NAME, "source": "local"},
    )
    
    print(f"[experiment] Experiment completed!")
    print(result.format())
    
    langfuse.flush()
    
    return result


def main():
    """CLI entry point for running experiments."""
    parser = argparse.ArgumentParser(
        description="Run Langfuse experiments for QA Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run experiment on a Langfuse dataset
  python experiments.py --dataset "qa-test-dataset"
  
  # Run with custom run name
  python experiments.py --dataset "qa-test-dataset" --run-name "prod-v1.2-test"
  
  # Run with description
  python experiments.py --dataset "qa-test-dataset" --description "Testing new prompts"
        """,
    )
    
    parser.add_argument(
        "--dataset",
        required=True,
        help="Name of the Langfuse dataset to run the experiment on",
    )
    parser.add_argument(
        "--run-name",
        help="Custom name for this experiment run (default: auto-generated)",
    )
    parser.add_argument(
        "--description",
        help="Description for this experiment run",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=5,
        help="Maximum concurrent executions (default: 5)",
    )
    
    args = parser.parse_args()
    
    config = ExperimentConfig(
        dataset_name=args.dataset,
        run_name=args.run_name,
        description=args.description,
        max_concurrency=args.max_concurrency,
    )
    
    print(f"[experiment] Configuration:")
    print(f"  Dataset: {config.dataset_name}")
    print(f"  Run Name: {config.run_name}")
    print(f"  Description: {config.description or '(none)'}")
    print(f"  Model: {MODEL_NAME}")
    print(f"  Max Concurrency: {config.max_concurrency}")
    print()
    
    asyncio.run(run_experiment_on_dataset(config))


if __name__ == "__main__":
    main()

