# package_lambdas.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir

Write-Host "Packaging Lambda functions..."
Write-Host "Script directory: $ScriptDir"
Write-Host "Root directory: $RootDir"

# Package game_id_discovery function (code only, requests/boto3 from layer)
Write-Host "Packaging game_id_discovery (code only)..."
$discoveryDir = "$RootDir/lambda_functions/game_id_discovery"
$discoveryZip = "$RootDir/lambda_functions/lambda_game_id_discovery.zip"
if (Test-Path $discoveryZip) {
    Remove-Item $discoveryZip -Force -Confirm:$false
}
Compress-Archive -Path "$discoveryDir/game_id_discovery.py" -DestinationPath $discoveryZip -Force
Write-Host "Created: $discoveryZip"

# Package extract function (only needs requests, boto3 from layer)
Write-Host "Packaging extract_bgg_data..."
$extractDir = "$RootDir/lambda_functions/extract_bgg_data"
$extractZip = "$RootDir/lambda_functions/extract_bgg_data.zip"
if (Test-Path $extractZip) {
    Remove-Item $extractZip -Force -Confirm:$false
}
Compress-Archive -Path "$extractDir/extract_bgg_data.py" -DestinationPath $extractZip -Force
Write-Host "Created: $extractZip"

# Package clean function (code only, pandas/pyarrow come from AWS layer)
Write-Host "Packaging clean_bgg_data (code only)..."
$cleanDir = "$RootDir/lambda_functions/clean_bgg_data"
$cleanZip = "$RootDir/lambda_functions/clean_bgg_data.zip"
$tempCleanDir = "$cleanDir/temp_package"

if (Test-Path $tempCleanDir) {
    Remove-Item -Path $tempCleanDir -Recurse -Force -Confirm:$false
}
New-Item -ItemType Directory -Path $tempCleanDir -Force | Out-Null
Copy-Item "$cleanDir/clean_bgg_data.py" $tempCleanDir

# Create zip
if (Test-Path $cleanZip) { Remove-Item $cleanZip -Force -Confirm:$false }
$retryCount = 0
$maxRetries = 3
while ($retryCount -lt $maxRetries) {
    try {
        Compress-Archive -Path "$tempCleanDir\clean_bgg_data.py" -DestinationPath $cleanZip -Force
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

# Package transform function (code only, pandas/pyarrow come from AWS layer)
Write-Host "Packaging transform_bgg_data (code only)..."
$transformDir = "$RootDir/lambda_functions/transform_bgg_data"
$transformZip = "$RootDir/lambda_functions/transform_bgg_data.zip"
$tempTransformDir = "$transformDir/temp_package"

if (Test-Path $tempTransformDir) {
    Remove-Item -Path $tempTransformDir -Recurse -Force -Confirm:$false
}
New-Item -ItemType Directory -Path $tempTransformDir -Force | Out-Null
Copy-Item "$transformDir/transform_bgg_data.py" $tempTransformDir

# Create zip
if (Test-Path $transformZip) { Remove-Item $transformZip -Force -Confirm:$false }
$retryCount = 0
$maxRetries = 3
while ($retryCount -lt $maxRetries) {
    try {
        Compress-Archive -Path "$tempTransformDir\transform_bgg_data.py" -DestinationPath $transformZip -Force
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

# Package data_quality function (code only, boto3 comes from runtime)
Write-Host "Packaging data_quality (code only)..."
$dqDir = "$RootDir/lambda_functions/data_quality"
$dqZip = "$RootDir/lambda_functions/data_quality.zip"
$tempDqDir = "$dqDir/temp_package"

if (Test-Path $tempDqDir) {
    Remove-Item -Path $tempDqDir -Recurse -Force -Confirm:$false
}
New-Item -ItemType Directory -Path $tempDqDir -Force | Out-Null
Copy-Item "$dqDir/data_quality.py" $tempDqDir

# Create zip
if (Test-Path $dqZip) { Remove-Item $dqZip -Force -Confirm:$false }
$retryCount = 0
$maxRetries = 3
while ($retryCount -lt $maxRetries) {
    try {
        Compress-Archive -Path "$tempDqDir\data_quality.py" -DestinationPath $dqZip -Force
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
Remove-Item -Path $tempDqDir -Recurse -Force -Confirm:$false
Write-Host "Created: $dqZip"

# Package apply_mappings function (code only, boto3 comes from runtime)
Write-Host "Packaging apply_mappings (code only)..."
$applyMappingsDir = "$RootDir/lambda_functions/apply_mappings"
$applyMappingsZip = "$RootDir/lambda_functions/apply_mappings.zip"
$tempApplyMappingsDir = "$applyMappingsDir/temp_package"

if (Test-Path $tempApplyMappingsDir) {
    Remove-Item -Path $tempApplyMappingsDir -Recurse -Force -Confirm:$false
}
New-Item -ItemType Directory -Path $tempApplyMappingsDir -Force | Out-Null
Copy-Item "$applyMappingsDir/apply_mappings.py" $tempApplyMappingsDir

# Create zip
if (Test-Path $applyMappingsZip) { Remove-Item $applyMappingsZip -Force -Confirm:$false }
$retryCount = 0
$maxRetries = 3
while ($retryCount -lt $maxRetries) {
    try {
        Compress-Archive -Path "$tempApplyMappingsDir\apply_mappings.py" -DestinationPath $applyMappingsZip -Force
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
Remove-Item -Path $tempApplyMappingsDir -Recurse -Force -Confirm:$false
Write-Host "Created: $applyMappingsZip"
Write-Host "Files:"
Get-ChildItem -Path "$RootDir/lambda_functions" -Filter "*.zip" | Format-Table Name, @{Label="Size";Expression={
    if ($_.Length -lt 1MB) {
        "{0:F2} KB" -f ($_.Length / 1KB)
    } else {
        "{0:F2} MB" -f ($_.Length / 1MB)
    }
}} -AutoSize
