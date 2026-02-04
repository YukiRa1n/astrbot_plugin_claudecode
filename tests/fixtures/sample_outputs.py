"""
Sample Outputs - Example CLI outputs for testing.
"""

import json

# Successful execution output
SUCCESS_OUTPUT = json.dumps({
    "result": "Task completed successfully. Created file hello.py with a simple hello world program.",
    "is_error": False,
    "total_cost_usd": 0.0042,
    "session_id": "test-session-123",
})

# Error output
ERROR_OUTPUT = json.dumps({
    "result": "Error: Permission denied when accessing /etc/passwd",
    "is_error": True,
    "total_cost_usd": 0.0001,
    "session_id": "test-session-456",
})

# Malformed JSON (for testing fallback)
MALFORMED_OUTPUT = "This is not JSON output\nBut it contains useful information"

# Empty output
EMPTY_OUTPUT = ""

# Stream JSON chunks
STREAM_CHUNKS = [
    json.dumps({"type": "thinking", "content": "Analyzing the task..."}),
    json.dumps({"type": "tool_use", "content": "Reading file main.py"}),
    json.dumps({"type": "tool_use", "content": "Writing file output.txt"}),
    json.dumps({"type": "result", "content": "Task completed successfully"}),
]

# All sample outputs
SAMPLE_OUTPUTS = {
    "success": SUCCESS_OUTPUT,
    "error": ERROR_OUTPUT,
    "malformed": MALFORMED_OUTPUT,
    "empty": EMPTY_OUTPUT,
    "stream_chunks": STREAM_CHUNKS,
}

__all__ = ["SAMPLE_OUTPUTS"]
