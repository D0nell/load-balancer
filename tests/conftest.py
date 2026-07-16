import sys
import os

# Keep generated test output as an artifact without letting pytest collect it.
collect_ignore = ["test_results.txt"]

sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "load_balancer")
)