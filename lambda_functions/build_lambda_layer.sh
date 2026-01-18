#!/bin/bash
# build_lambda_layer.sh

# Create directory structure
mkdir -p lambda_layers/python

# Install dependencies
pip install \
    requests \
    pandas \
    pyarrow \
    boto3 \
    -t lambda_layers/python

# Create zip file
cd lambda_layers
zip -r ../dependencies.zip python/
cd ..

echo "Lambda layer created: dependencies.zip"