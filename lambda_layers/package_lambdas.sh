#!/bin/bash
# package_lambdas.sh

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Packaging Lambda functions..."
echo "Script directory: $SCRIPT_DIR"
echo "Root directory: $ROOT_DIR"

# Package extract function (only needs requests, boto3 from layer)
echo "Packaging extract_bgg_data..."
cd "$ROOT_DIR/lambda_functions/extract_bgg_data"
7z a -r "$ROOT_DIR/lambda_functions/extract_bgg_data.zip" extract_bgg_data.py
echo "Created: $ROOT_DIR/lambda_functions/extract_bgg_data.zip"

# Package clean function with pandas and pyarrow
echo "Packaging clean_bgg_data with dependencies..."
cd "$ROOT_DIR/lambda_functions/clean_bgg_data"
mkdir -p temp_package
cp clean_bgg_data.py temp_package/
cd temp_package
pip install -q pandas pyarrow -t . --no-cache-dir
# Clean up unnecessary files
find . -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -type f -delete 2>/dev/null || true
cd ..
7z a -r "$ROOT_DIR/lambda_functions/clean_bgg_data.zip" temp_package/*
rm -rf temp_package
echo "Created: $ROOT_DIR/lambda_functions/clean_bgg_data.zip"

# Package transform function with pandas and pyarrow
echo "Packaging transform_bgg_data with dependencies..."
cd "$ROOT_DIR/lambda_functions/transform_bgg_data"
mkdir -p temp_package
cp transform_bgg_data.py temp_package/
cd temp_package
pip install -q pandas pyarrow -t . --no-cache-dir
# Clean up unnecessary files
find . -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -type f -delete 2>/dev/null || true
cd ..
7z a -r "$ROOT_DIR/lambda_functions/transform_bgg_data.zip" temp_package/*
rm -rf temp_package
echo "Created: $ROOT_DIR/lambda_functions/transform_bgg_data.zip"

echo ""
echo "Lambda functions packaged successfully!"
echo "Files:"
ls -lh "$ROOT_DIR/lambda_functions"/*.zip