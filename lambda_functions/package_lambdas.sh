#!/bin/bash
# package_lambdas.sh

# Package extract function
cd lambda_functions/extract_bgg_data
zip -r ../extract_bgg_data.zip extract_bgg_data.py
cd ../..

# Package clean function
cd lambda_functions/clean_bgg_data
zip -r ../clean_bgg_data.zip clean_bgg_data.py
cd ../..

# Package transform function
cd lambda_functions/transform_bgg_data
zip -r ../transform_bgg_data.zip transform_bgg_data.py
cd ../..

echo "Lambda functions packaged"