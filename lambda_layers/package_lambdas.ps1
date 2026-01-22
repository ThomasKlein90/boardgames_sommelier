# package_lambdas.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

Write-Host "Packaging Lambda functions..."
Write-Host "Script directory: $ScriptDir"
Write-Host "Root directory: $RootDir"

# Package extract function (only needs requests, boto3 from layer)
Write-Host "Packaging extract_bgg_data..."
$extractDir = "$RootDir/lambda_functions/extract_bgg_data"
$extractZip = "$RootDir/lambda_functions/extract_bgg_data.zip"
if (Test-Path $extractZip) {
    Remove-Item $extractZip -Force -Confirm:$false
}
Compress-Archive -Path "$extractDir/extract_bgg_data.py" -DestinationPath $extractZip -Force
Write-Host "Created: $extractZip"

# Package clean function with pandas and pyarrow
Write-Host "Packaging clean_bgg_data with dependencies..."
$cleanDir = "$RootDir/lambda_functions/clean_bgg_data"
$cleanZip = "$RootDir/lambda_functions/clean_bgg_data.zip"
$tempCleanDir = "$cleanDir/temp_package"

if (Test-Path $tempCleanDir) {
    Remove-Item -Path $tempCleanDir -Recurse -Force -Confirm:$false
}
New-Item -ItemType Directory -Path $tempCleanDir -Force | Out-Null
Copy-Item "$cleanDir/clean_bgg_data.py" $tempCleanDir

Push-Location $tempCleanDir
Write-Host "  Installing pandas and pyarrow..."
python -m pip install -q pandas pyarrow -t . --no-cache-dir | Out-Null

# Clean up unnecessary files
Write-Host "  Cleaning up unnecessary files..."
Get-ChildItem -Path . -Filter "*.dist-info" -Directory -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue -Confirm:$false
Get-ChildItem -Path . -Filter "*.egg-info" -Directory -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue -Confirm:$false
Get-ChildItem -Path . -Filter "tests" -Directory -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue -Confirm:$false
Get-ChildItem -Path . -Filter "__pycache__" -Directory -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue -Confirm:$false
Get-ChildItem -Path . -Filter "*.pyc" -File -Recurse -Force | Remove-Item -Force -ErrorAction SilentlyContinue -Confirm:$false
Get-ChildItem -Path . -Filter "*.pyo" -File -Recurse -Force | Remove-Item -Force -ErrorAction SilentlyContinue -Confirm:$false

# Give files time to be released
Start-Sleep -Seconds 2
Pop-Location

# Wait and retry zip creation if needed
$retryCount = 0
$maxRetries = 3
while ($retryCount -lt $maxRetries) {
    try {
        if (Test-Path $cleanZip) {
            Remove-Item $cleanZip -Force -Confirm:$false
        }
        Compress-Archive -Path "$tempCleanDir/*" -DestinationPath $cleanZip -Force
        break
    } catch {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Host "  Retry $retryCount/$maxRetries - waiting for file locks to release..."
            Start-Sleep -Seconds 2
        } else {
            throw $_
        }
    }
}

Remove-Item -Path $tempCleanDir -Recurse -Force -Confirm:$false
Write-Host "Created: $cleanZip"

# Package transform function with pandas and pyarrow
Write-Host "Packaging transform_bgg_data with dependencies..."
$transformDir = "$RootDir/lambda_functions/transform_bgg_data"
$transformZip = "$RootDir/lambda_functions/transform_bgg_data.zip"
$tempTransformDir = "$transformDir/temp_package"

if (Test-Path $tempTransformDir) {
    Remove-Item -Path $tempTransformDir -Recurse -Force -Confirm:$false
}
New-Item -ItemType Directory -Path $tempTransformDir -Force | Out-Null
Copy-Item "$transformDir/transform_bgg_data.py" $tempTransformDir

Push-Location $tempTransformDir
Write-Host "  Installing pandas and pyarrow..."
python -m pip install -q pandas pyarrow -t . --no-cache-dir | Out-Null

# Clean up unnecessary files
Write-Host "  Cleaning up unnecessary files..."
Get-ChildItem -Path . -Filter "*.dist-info" -Directory -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue -Confirm:$false
Get-ChildItem -Path . -Filter "*.egg-info" -Directory -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue -Confirm:$false
Get-ChildItem -Path . -Filter "tests" -Directory -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue -Confirm:$false
Get-ChildItem -Path . -Filter "__pycache__" -Directory -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue -Confirm:$false
Get-ChildItem -Path . -Filter "*.pyc" -File -Recurse -Force | Remove-Item -Force -ErrorAction SilentlyContinue -Confirm:$false
Get-ChildItem -Path . -Filter "*.pyo" -File -Recurse -Force | Remove-Item -Force -ErrorAction SilentlyContinue -Confirm:$false

# Give files time to be released
Start-Sleep -Seconds 2
Pop-Location

# Wait and retry zip creation if needed
$retryCount = 0
$maxRetries = 3
while ($retryCount -lt $maxRetries) {
    try {
        if (Test-Path $transformZip) {
            Remove-Item $transformZip -Force -Confirm:$false
        }
        Compress-Archive -Path "$tempTransformDir/*" -DestinationPath $transformZip -Force
        break
    } catch {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Host "  Retry $retryCount/$maxRetries - waiting for file locks to release..."
            Start-Sleep -Seconds 2
        } else {
            throw $_
        }
    }
}

Remove-Item -Path $tempTransformDir -Recurse -Force -Confirm:$false
Write-Host "Created: $transformZip"

Write-Host ""
Write-Host "Lambda functions packaged successfully!"
Write-Host "Files:"
Get-ChildItem -Path "$RootDir/lambda_functions" -Filter "*.zip" | Format-Table Name, @{Label="Size";Expression={
    if ($_.Length -lt 1MB) {
        "{0:F2} KB" -f ($_.Length / 1KB)
    } else {
        "{0:F2} MB" -f ($_.Length / 1MB)
    }
}} -AutoSize
