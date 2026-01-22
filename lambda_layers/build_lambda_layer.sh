#!/bin/bash
# build_lambda_layer.sh

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Building Lambda layer..."
echo "Script directory: $SCRIPT_DIR"
echo "Root directory: $ROOT_DIR"

# Create directory structure for dependencies
mkdir -p "$SCRIPT_DIR/lambda_layers/python"

# Install dependencies
python -m pip install \
    requests \
    boto3 \
    -t "$SCRIPT_DIR/lambda_layers/python"

echo "Removing test files and documentation..."
# Remove unnecessary files to reduce size
find "$SCRIPT_DIR/lambda_layers/python" -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
find "$SCRIPT_DIR/lambda_layers/python" -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
find "$SCRIPT_DIR/lambda_layers/python" -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true
find "$SCRIPT_DIR/lambda_layers/python" -name "test" -type d -exec rm -rf {} + 2>/dev/null || true
find "$SCRIPT_DIR/lambda_layers/python" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$SCRIPT_DIR/lambda_layers/python" -name "*.pyc" -type f -delete 2>/dev/null || true
find "$SCRIPT_DIR/lambda_layers/python" -name "*.pyo" -type f -delete 2>/dev/null || true

# Create zip file in lambda_layers directory
cd "$SCRIPT_DIR"
7z a -r "$SCRIPT_DIR/dependencies.zip" lambda_layers/python/

echo "Lambda layer created at: $SCRIPT_DIR/dependencies.zip"
ls -lh "$SCRIPT_DIR/dependencies.zip"