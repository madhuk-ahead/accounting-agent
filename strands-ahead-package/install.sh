#!/bin/bash
# Simple installation script for Strands-AHEAD

echo "Installing Strands-AHEAD package..."
pip install strands_ahead-*.whl
echo "✓ Installation complete!"
echo ""
echo "Test the installation:"
echo "  python -c 'from strands import Agent; print(\"Strands-AHEAD installed successfully\")'"

