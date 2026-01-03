#!/bin/bash
# Simple test runner for Strike converter

set -e

echo "Running Strike to Koinly converter tests..."
echo ""

# Check if pytest is available
if ! python3 -m pytest --version > /dev/null 2>&1; then
    echo "Warning: pytest not found. Install with: pip install -r requirements.txt"
    echo "Running tests with unittest instead..."
    python3 -m unittest test_strike_converter.py -v
else
    python3 -m pytest test_strike_converter.py -v
fi

echo ""
echo "All tests passed! ✓"
