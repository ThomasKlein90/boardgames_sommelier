# build_lambda_layer.ps1

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$LayerDir = "$ScriptDir/lambda_layers/python"

Write-Host "Building Lambda layer..."
Write-Host "Script directory: $ScriptDir"
Write-Host "Root directory: $RootDir"

# Create directory structure for dependencies
if (Test-Path $LayerDir) {
    Remove-Item -Path $LayerDir -Recurse -Force -Confirm:$false
}
New-Item -ItemType Directory -Path $LayerDir -Force | Out-Null

# Install dependencies
Write-Host "Installing dependencies..."
python -m pip install `
    requests `
    urllib3 `
    certifi `
    charset-normalizer `
    idna `
    boto3 `
    -t $LayerDir | Out-Null

Write-Host "Removing unnecessary files to reduce size..."
# Remove unnecessary files to reduce size
$patterns = @(
    "*.dist-info",
    "*.egg-info",
    "tests",
    "test",
    "__pycache__",
    "*.pyc",
    "*.pyo"
)

foreach ($pattern in $patterns) {
    if ($pattern -like "*.*") {
        Get-ChildItem -Path $LayerDir -Filter $pattern -Recurse -Force | Remove-Item -Force -ErrorAction SilentlyContinue -Confirm:$false
    } else {
        Get-ChildItem -Path $LayerDir -Filter $pattern -Directory -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue -Confirm:$false
    }
}

# Create zip file
Write-Host "Creating zip file..."
$zipPath = "$ScriptDir/dependencies.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force -Confirm:$false
}

# Use Compress-Archive to create the zip - must include the python/ directory at root
Push-Location $ScriptDir
Compress-Archive -Path "lambda_layers/python" -DestinationPath $zipPath -Force
Pop-Location

Write-Host "Lambda layer created at: $zipPath"
$size = (Get-Item $zipPath).Length / 1MB
Write-Host "Size: $('{0:F2}' -f $size) MB"
