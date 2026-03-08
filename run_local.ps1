param(
    [string]$ConfigPath = ".\runner.config.ps1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-FromRoot {
    param(
        [Parameter(Mandatory = $true)][string]$BasePath,
        [Parameter(Mandatory = $true)][string]$InputPath
    )
    if ([System.IO.Path]::IsPathRooted($InputPath)) {
        return $InputPath
    }
    return [System.IO.Path]::GetFullPath((Join-Path $BasePath $InputPath))
}

if (-not (Test-Path -LiteralPath $ConfigPath)) {
    throw "Config file not found: $ConfigPath"
}

. $ConfigPath
if (-not $RunnerConfig) {
    throw "Config file must define `$RunnerConfig."
}

$projectRoot = Resolve-FromRoot -BasePath (Get-Location).Path -InputPath $RunnerConfig.ProjectRoot
$pythonExe = Resolve-FromRoot -BasePath $projectRoot -InputPath $RunnerConfig.PythonExe
$requirementsFile = Resolve-FromRoot -BasePath $projectRoot -InputPath $RunnerConfig.RequirementsFile
$apiKeyFile = Resolve-FromRoot -BasePath $projectRoot -InputPath $RunnerConfig.ApiKeyFile
$jdPath = Resolve-FromRoot -BasePath $projectRoot -InputPath $RunnerConfig.JobDescriptionPath
$companyName = [string]$RunnerConfig.CompanyName
$modelName = [string]$RunnerConfig.ModelName
$templatePath = [string]$RunnerConfig.TemplatePath
$debugMode = [bool]$RunnerConfig.Debug
$runHealthCheck = [bool]$RunnerConfig.RunHealthCheck

if (-not (Test-Path -LiteralPath $projectRoot)) {
    throw "ProjectRoot not found: $projectRoot"
}
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python executable not found: $pythonExe"
}
if (-not (Test-Path -LiteralPath $requirementsFile)) {
    throw "requirements.txt not found: $requirementsFile"
}
if (-not (Test-Path -LiteralPath $apiKeyFile)) {
    throw "API key file not found: $apiKeyFile"
}
if (-not (Test-Path -LiteralPath $jdPath)) {
    throw "Job description file not found: $jdPath"
}
if ([string]::IsNullOrWhiteSpace($companyName)) {
    throw "CompanyName must not be empty in runner.config.ps1"
}
if ([string]::IsNullOrWhiteSpace($modelName)) {
    throw "ModelName must not be empty in runner.config.ps1"
}

$apiKey = (Get-Content -LiteralPath $apiKeyFile -Raw).Trim()
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "API key file is empty: $apiKeyFile"
}

Write-Host "[1/5] cd $projectRoot"
Set-Location -LiteralPath $projectRoot

Write-Host "[2/5] Installing requirements from $requirementsFile"
& $pythonExe -m pip install -r $requirementsFile

Write-Host "[3/5] Exporting GEMINI_API_KEY from $apiKeyFile"
$env:GEMINI_API_KEY = $apiKey

if ($runHealthCheck) {
    Write-Host "[4/5] Running Gemini health check with model $modelName"
    & $pythonExe -c "from google import genai; c=genai.Client(); r=c.models.generate_content(model='$modelName', contents='Reply with OK'); print(r.text)"
}
else {
    Write-Host "[4/5] Health check skipped (RunHealthCheck=false)"
}

Write-Host "[5/5] Running AI Resume Tailor"
$runArgs = @("main.py", "run", "--jd-path", $jdPath, "--company", $companyName, "--model", $modelName)
if (-not [string]::IsNullOrWhiteSpace($templatePath)) {
    $resolvedTemplate = Resolve-FromRoot -BasePath $projectRoot -InputPath $templatePath
    $runArgs += @("--template-path", $resolvedTemplate)
}
if ($debugMode) {
    $runArgs += "--debug"
}
& $pythonExe @runArgs
