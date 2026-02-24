#!/usr/bin/env bash
# Build Lambda layers: Strands-AHEAD (from strands-ahead-package wheel) and OpenAI.
# Produces infra/layers/artifacts/strands-ahead-layer.zip and openai-layer.zip for linux/amd64.
# For Strands-AHEAD: place strands_ahead-*.whl in strands-ahead-package/ then run this script.
# Or set strands_layer_arn in Terraform to use an existing layer and build openai only.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ARTIFACTS_DIR="$PROJECT_ROOT/infra/layers/artifacts"
mkdir -p "$ARTIFACTS_DIR"
WORK="/tmp/agent-template-layers-$$"
mkdir -p "$WORK"
trap "rm -rf '$WORK'" EXIT

echo "Building Lambda layers (Python 3.11, linux/amd64)..."
echo ""

# Strands-AHEAD layer (from local wheel in strands-ahead-package/)
echo "Building strands-ahead layer..."
if ! "$PROJECT_ROOT/infra/layers/strands_ahead/build_layer.sh"; then
  echo "Strands-AHEAD layer build failed (missing wheel?). Set strands_layer_arn in Terraform to use an existing layer, or add strands_ahead-*.whl to strands-ahead-package/ and re-run."
fi

# OpenAI layer
echo "Building openai layer..."
docker run --rm --platform linux/amd64 \
  --entrypoint /bin/bash \
  -v "$WORK:/work" -w /work \
  public.ecr.aws/lambda/python:3.11 \
  -c "pip install openai -t python/ --no-cache-dir && \
      rm -rf python/*.dist-info python/__pycache__ python/*/__pycache__ 2>/dev/null; \
      python3 -c \"import zipfile, os; z = zipfile.ZipFile('openai-layer.zip', 'w', zipfile.ZIP_DEFLATED); [z.write(os.path.join(r,f), os.path.join(r,f)) for r,d,fs in os.walk('python') for f in fs]; z.close()\" && rm -rf python/"
cp "$WORK/openai-layer.zip" "$ARTIFACTS_DIR/"
echo "  -> $ARTIFACTS_DIR/openai-layer.zip"

echo ""
echo "Done. Run: cd infra && terraform init && terraform apply"
