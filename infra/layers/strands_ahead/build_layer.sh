#!/bin/bash
# Build Lambda layer for Strands-AHEAD package
# This script builds a Lambda layer zip containing the strands-ahead package
# Architecture: linux/amd64 (x86_64) to match Lambda runtime
# Python version: 3.11 to match Lambda runtime

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LAYERS_DIR="$PROJECT_ROOT/infra/layers"
ARTIFACTS_DIR="$LAYERS_DIR/artifacts"
STRANDS_AHEAD_PACKAGE_DIR="$PROJECT_ROOT/strands-ahead-package"
BUILD_DIR="$LAYERS_DIR/strands_ahead/build"
LAYER_ZIP="$ARTIFACTS_DIR/strands-ahead-layer.zip"

echo "Building Strands-AHEAD Lambda layer..."
echo "======================================"

# Clean previous build
echo "Cleaning previous build..."
rm -rf "$BUILD_DIR"
rm -f "$LAYER_ZIP"
mkdir -p "$BUILD_DIR"
mkdir -p "$ARTIFACTS_DIR"

# Create python directory for layer
PYTHON_DIR="$BUILD_DIR/python"
mkdir -p "$PYTHON_DIR"

# Find the wheel file
WHEEL_FILE=$(find "$STRANDS_AHEAD_PACKAGE_DIR" -name "strands_ahead-*.whl" | head -1)

if [ -z "$WHEEL_FILE" ]; then
    echo "ERROR: No strands_ahead wheel file found in $STRANDS_AHEAD_PACKAGE_DIR"
    exit 1
fi

echo "Found wheel: $WHEEL_FILE"

# Use Docker to install in a Linux x86_64 environment matching Lambda
echo "Installing Strands-AHEAD package using Docker (Python 3.11, linux/amd64)..."

# Create temporary directory for Docker build
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Copy wheel to temp directory
cp "$WHEEL_FILE" "$TEMP_DIR/"

# Create install script
cat > "$TEMP_DIR/install.sh" << 'EOF'
#!/bin/bash
set -e
cd /work
pip install --upgrade pip
pip install strands_ahead-*.whl --target python --no-cache-dir
EOF
chmod +x "$TEMP_DIR/install.sh"

# Run installation in Docker (Python 3.11, linux/amd64)
# Use --entrypoint to override Lambda handler requirement
docker run --rm \
    --platform linux/amd64 \
    --entrypoint /bin/bash \
    -v "$TEMP_DIR:/work" \
    -w /work \
    public.ecr.aws/lambda/python:3.11 \
    install.sh

# Copy python directory from temp to build directory
if [ -d "$TEMP_DIR/python" ]; then
    cp -r "$TEMP_DIR/python"/* "$PYTHON_DIR/"
else
    echo "ERROR: Python directory not created in Docker build"
    exit 1
fi

# Verify strands package is present
if [ ! -d "$PYTHON_DIR/strands" ]; then
    echo "ERROR: strands package not found in layer"
    exit 1
fi

echo "✓ Strands-AHEAD package installed successfully"

# Create zip file
echo "Creating layer zip file..."
cd "$BUILD_DIR"
zip -r "$LAYER_ZIP" python > /dev/null

# Verify zip was created
if [ ! -f "$LAYER_ZIP" ]; then
    echo "ERROR: Layer zip file not created"
    exit 1
fi

SIZE_MB=$(du -m "$LAYER_ZIP" | cut -f1)
echo "✓ Layer zip created: $LAYER_ZIP (${SIZE_MB} MB)"
echo ""
echo "Layer structure:"
unzip -l "$LAYER_ZIP" | head -20
echo ""
echo "Build complete!"
