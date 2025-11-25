"""
Headless test runner for QA Agent.

This script reads queries from a CSV file and runs them through the agent,
storing each execution as a separate session in Langfuse for tracking and analysis.
"""

import asyncio
import csv
import sys
import uuid
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Add parent directory to path to import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import observability
from agents import Agent, Runner, SQLiteSession, function_tool
from prompts import get_prompt
from server import get_feature_from_jira, get_bug_from_jira, get_project_context, MODEL_NAME


# Load environment variables
load_dotenv()
observability.init_observability()


class TestResult:
    """Stores the result of a single test query execution."""
    
    def __init__(
        self,
        query: str,
        session_id: str,
        response: str,
        success: bool,
        error: str = None,
        execution_time: float = 0.0
    ):
        self.query = query
        self.session_id = session_id
        self.response = response
        self.success = success
        self.error = error
        self.execution_time = execution_time
    
    def __repr__(self):
        status = "✓" if self.success else "✗"
        return f"[{status}] Session {self.session_id}: {self.query[:50]}..."


def load_queries_from_csv(csv_path: Path) -> List[str]:
    """
    Load queries from a CSV file.
    
    Args:
        csv_path: Path to the CSV file containing queries
        
    Returns:
        List of query strings
    """
    queries = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                query = row.get('queries', '').strip()
                if query:
                    queries.append(query)
        
        print(f"[test-runner] Loaded {len(queries)} queries from {csv_path}")
        return queries
    
    except FileNotFoundError:
        print(f"[test-runner] ERROR: CSV file not found: {csv_path}")
        return []
    except Exception as e:
        print(f"[test-runner] ERROR loading CSV: {e}")
        return []


async def run_single_query(query: str, agent: Agent, session_id: str = None) -> TestResult:
    """
    Run a single query through the agent.
    
    Args:
        query: The user query to process
        agent: The configured agent instance
        session_id: Optional session ID (will generate one if not provided)
        
    Returns:
        TestResult object with execution details
    """
    if session_id is None:
        session_id = f"test-{uuid.uuid4().hex[:8]}"
    
    print(f"\n[test-runner] Starting session {session_id}")
    print(f"[test-runner] Query: {query}")
    
    start_time = asyncio.get_event_loop().time()
    session = SQLiteSession(session_id=session_id)
    
    try:
        # Use Langfuse session context for tracing
        with observability.langfuse_session_context(
            session_id, 
            user_id="test-runner",
            span_name="headless-test"
        ) as lf_span:
            response = await Runner.run(agent, query, session=session)
            text = response.final_output or ""
            
            # Set trace-level input/output for Langfuse Sessions UI
            try:
                if lf_span is not None:
                    lf_span.update_trace(
                        input={"message": query},
                        output={"assistantMessage": text},
                    )
            except Exception as e:
                print(f"[test-runner] Warning: Failed to update trace: {e}")
        
        execution_time = asyncio.get_event_loop().time() - start_time
        
        print(f"[test-runner] Response: {text[:200]}{'...' if len(text) > 200 else ''}")
        print(f"[test-runner] Execution time: {execution_time:.2f}s")
        
        return TestResult(
            query=query,
            session_id=session_id,
            response=text,
            success=True,
            execution_time=execution_time
        )
    
    except Exception as e:
        execution_time = asyncio.get_event_loop().time() - start_time
        error_msg = str(e)
        
        print(f"[test-runner] ERROR: {error_msg}")
        
        return TestResult(
            query=query,
            session_id=session_id,
            response="",
            success=False,
            error=error_msg,
            execution_time=execution_time
        )
    
    finally:
        try:
            session.close()
        except Exception:
            pass


async def run_all_queries(queries: List[str], agent: Agent) -> List[TestResult]:
    """
    Run all queries through the agent sequentially.
    
    Args:
        queries: List of query strings to execute
        agent: The configured agent instance
        
    Returns:
        List of TestResult objects
    """
    results = []
    
    print(f"\n{'='*80}")
    print(f"Starting test run with {len(queries)} queries")
    print(f"Agent: {agent.name}")
    print(f"Model: {MODEL_NAME}")
    print(f"{'='*80}")
    
    for i, query in enumerate(queries, 1):
        print(f"\n--- Test {i}/{len(queries)} ---")
        
        # Generate a unique session ID for each query
        session_id = f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{i:03d}"
        
        result = await run_single_query(query, agent, session_id)
        results.append(result)
        
        # Small delay between queries to avoid rate limiting
        if i < len(queries):
            await asyncio.sleep(1)
    
    return results


def print_summary(results: List[TestResult]):
    """
    Print a summary of test results.
    
    Args:
        results: List of TestResult objects
    """
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}\n")
    
    total = len(results)
    successful = sum(1 for r in results if r.success)
    failed = total - successful
    total_time = sum(r.execution_time for r in results)
    avg_time = total_time / total if total > 0 else 0
    
    print(f"Total queries:    {total}")
    print(f"Successful:       {successful} ({successful/total*100:.1f}%)")
    print(f"Failed:           {failed} ({failed/total*100:.1f}%)")
    print(f"Total time:       {total_time:.2f}s")
    print(f"Average time:     {avg_time:.2f}s per query")
    
    print(f"\n{'='*80}")
    print("INDIVIDUAL RESULTS")
    print(f"{'='*80}\n")
    
    for i, result in enumerate(results, 1):
        status = "✓ PASS" if result.success else "✗ FAIL"
        print(f"{i}. {status} [{result.execution_time:.2f}s] Session: {result.session_id}")
        print(f"   Query: {result.query}")
        if result.success:
            print(f"   Response: {result.response[:150]}{'...' if len(result.response) > 150 else ''}")
        else:
            print(f"   Error: {result.error}")
        print()
    
    print(f"{'='*80}")
    print("All sessions are available in Langfuse for detailed analysis.")
    print(f"{'='*80}\n")


async def main():
    """Main entry point for the test runner."""
    
    # Paths
    script_dir = Path(__file__).parent
    csv_path = script_dir / "user_queries.csv"
    
    # Load queries
    queries = load_queries_from_csv(csv_path)
    
    if not queries:
        print("[test-runner] No queries to process. Exiting.")
        return
    
    # Create agent with the same configuration as the server
    agent = Agent(
        name="QA Assistant Agent",
        instructions=get_prompt("QA Agent main instructions"),
        model=MODEL_NAME,
        tools=[get_feature_from_jira, get_bug_from_jira, get_project_context],
    )
    
    # Run all queries
    results = await run_all_queries(queries, agent)
    
    # Print summary
    print_summary(results)
    
    # Exit with appropriate status code
    if all(r.success for r in results):
        print("[test-runner] All tests passed! ✓")
        sys.exit(0)
    else:
        print("[test-runner] Some tests failed. ✗")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[test-runner] Interrupted by user. Exiting.")
        sys.exit(130)
    except Exception as e:
        print(f"[test-runner] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

