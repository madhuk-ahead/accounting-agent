# Strands-AHEAD Package

This directory contains the Strands-AHEAD Python package - a fork of the Strands SDK with no-op telemetry (no OpenTelemetry required).

## Installation

### Option 1: Install from wheel file (Recommended)

```bash
pip install strands_ahead-*.whl
```

### Option 2: Install from local directory

```bash
pip install /path/to/strands-ahead-package/
```

### Option 3: Install in editable mode (for development)

If you want to modify the package:

```bash
cd /path/to/strands-ahead-workspace/sdk-python
pip install -e .
```

## Usage

After installation, use it exactly like the regular Strands SDK:

```python
from strands import Agent

agent = Agent()
result = agent("Hello, world!")
```

## What's Different?

- **No OpenTelemetry required**: All telemetry calls are no-ops
- **Same API**: Works as a drop-in replacement for `strands-agents`
- **Lighter**: No telemetry dependencies means smaller installation

## Package Contents

- `strands_ahead-*.whl`: The built wheel file (ready to install)

## Version

Current version: Built from Strands SDK with no-op telemetry implementation.

