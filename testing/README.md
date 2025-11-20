# QA Agent Testing Suite

This directory contains the testing infrastructure for running the QA Agent in headless mode.

## Overview

The test runner allows you to:
- Run the QA Agent without the web UI
- Process multiple queries from a CSV file
- Track each execution as a separate session in Langfuse
- Generate detailed test reports

## Files

- `user_queries.csv` - CSV file containing test queries
- `run_tests.py` - Main test runner script

## Usage

### Running Tests

From the project root directory:

```bash
# Using Python
python testing/run_tests.py

# Or using uv
uv run testing/run_tests.py
```

### CSV Format

The `user_queries.csv` file should have a single column named `queries`:

```csv
queries
"Can you help me create test cases for feature QA-101?"
"How should I retest BUG-77 after the fix?"
```

### Output

The test runner provides:

1. **Real-time console output** showing:
   - Each query being processed
   - Agent responses (truncated)
   - Execution time per query
   - Success/failure status

2. **Summary report** including:
   - Total queries processed
   - Success rate
   - Average execution time
   - Detailed results for each query

3. **Langfuse traces**: Each query is stored as a separate session in Langfuse with:
   - Unique session ID (format: `test-YYYYMMDD-HHMMSS-NNN`)
   - Complete trace of agent execution
   - Tool calls and responses
   - Input/output for easy review

## Example Output

```
================================================================================
Starting test run with 5 queries
Agent: QA Assistant Agent
Model: gpt-5-mini
================================================================================

--- Test 1/5 ---
[test-runner] Starting session test-20241119-143022-001
[test-runner] Query: Can you help me create test cases for feature QA-101?
[tool-call] get_feature_from_jira(feature_id=QA-101)
[test-runner] Response: Here are the test cases for the MFA login feature...
[test-runner] Execution time: 3.45s

...

================================================================================
TEST SUMMARY
================================================================================

Total queries:    5
Successful:       5 (100.0%)
Failed:           0 (0.0%)
Total time:       15.32s
Average time:     3.06s per query
```

## Adding More Test Queries

Simply edit `user_queries.csv` and add more queries:

```csv
queries
"Your new test query here"
"Another test query"
```

## Viewing Results in Langfuse

1. Open your Langfuse dashboard
2. Navigate to the Sessions view
3. Look for sessions with IDs starting with `test-`
4. Each session contains the full trace of agent execution

## Exit Codes

- `0` - All tests passed successfully
- `1` - One or more tests failed
- `130` - Interrupted by user (Ctrl+C)

## Environment Variables

The test runner uses the same environment variables as the main application:

- `MODEL_NAME` - AI model to use (default: gpt-5-mini)
- `LANGFUSE_PUBLIC_KEY` - Langfuse public key
- `LANGFUSE_SECRET_KEY` - Langfuse secret key
- `LANGFUSE_BASE_URL` - Langfuse instance URL
- `USE_LANGFUSE_PROMPTS` - Whether to fetch prompts from Langfuse

Make sure your `.env` file is properly configured before running tests.

