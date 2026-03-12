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
$tierName = [string]$RunnerConfig.TierName
$roleName = [string]$RunnerConfig.RoleName
$manualModelName = [string]$RunnerConfig.ModelName
$templatePath = [string]$RunnerConfig.TemplatePath
$debugMode = [bool]$RunnerConfig.Debug
$runHealthCheck = [bool]$RunnerConfig.RunHealthCheck
$tierProfiles = $RunnerConfig.TierProfiles

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
if ([string]::IsNullOrWhiteSpace($tierName)) {
    throw "TierName must not be empty in runner.config.ps1"
}
if ([string]::IsNullOrWhiteSpace($roleName)) {
    throw "RoleName must not be empty in runner.config.ps1"
}
if (-not $tierProfiles) {
    throw "TierProfiles must be defined in runner.config.ps1"
}
$tierProfile = $tierProfiles[$tierName]
if (-not $tierProfile) {
    $knownTiers = ($tierProfiles.Keys | Sort-Object) -join ", "
    throw "Unknown TierName '$tierName'. Available tiers: $knownTiers"
}
$modelName = [string]$tierProfile.ModelName
if (-not [string]::IsNullOrWhiteSpace($manualModelName)) {
    $modelName = $manualModelName
}
if ([string]::IsNullOrWhiteSpace($modelName)) {
    throw "ModelName is empty after tier resolution. Set TierProfiles.<TierName>.ModelName or RunnerConfig.ModelName."
}

$apiKeyRaw = Get-Content -LiteralPath $apiKeyFile -Raw
if ($null -eq $apiKeyRaw) {
    throw "API key file read returned null: $apiKeyFile"
}
$apiKey = ([string]$apiKeyRaw).Trim()
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "API key file is empty: $apiKeyFile"
}

Write-Host "[1/5] cd $projectRoot"
Set-Location -LiteralPath $projectRoot

Write-Host "[2/5] Installing requirements from $requirementsFile"
& $pythonExe -m pip install -r $requirementsFile

Write-Host "[3/5] Exporting GEMINI_API_KEY from $apiKeyFile"
$env:GEMINI_API_KEY = $apiKey
$env:ART_GENERATION_MODE = [string]$tierProfile.GenerationMode
$env:ART_LLM_MIN_INTERVAL_SECONDS = [string]$tierProfile.MinIntervalSeconds
$env:ART_LLM_MAX_429_ATTEMPTS = [string]$tierProfile.Max429Attempts
$env:ART_LLM_BACKOFF_BASE_SECONDS = [string]$tierProfile.BackoffBaseSeconds
$env:ART_AUTO_APPROVE_REVIEW = "1"
$env:ART_AUTO_APPROVE_TRIAGE = "0"

Write-Host "      TierName=$tierName"
Write-Host "      ModelName=$modelName"
Write-Host "      RoleName=$roleName"
Write-Host "      ART_GENERATION_MODE=$env:ART_GENERATION_MODE"
Write-Host "      ART_LLM_MIN_INTERVAL_SECONDS=$env:ART_LLM_MIN_INTERVAL_SECONDS"
Write-Host "      ART_LLM_MAX_429_ATTEMPTS=$env:ART_LLM_MAX_429_ATTEMPTS"
Write-Host "      ART_LLM_BACKOFF_BASE_SECONDS=$env:ART_LLM_BACKOFF_BASE_SECONDS"
Write-Host "      ART_AUTO_APPROVE_REVIEW=$env:ART_AUTO_APPROVE_REVIEW"
Write-Host "      ART_AUTO_APPROVE_TRIAGE=$env:ART_AUTO_APPROVE_TRIAGE"

if ($runHealthCheck) {
    Write-Host "[4/5] Running Gemini health check with model $modelName"
    & $pythonExe -c "from google import genai; c=genai.Client(); r=c.models.generate_content(model='$modelName', contents='Reply with OK'); print(r.text)"
}
else {
    Write-Host "[4/5] Health check skipped (RunHealthCheck=false)"
}

Write-Host "[5/5] Running AI Resume Tailor"
$runArgs = @("main.py", "run", "--jd-path", $jdPath, "--company", $companyName, "--model", $modelName, "--role", $roleName)
if (-not [string]::IsNullOrWhiteSpace($templatePath)) {
    $resolvedTemplate = Resolve-FromRoot -BasePath $projectRoot -InputPath $templatePath
    $runArgs += @("--template-path", $resolvedTemplate)
}
if ($debugMode) {
    $runArgs += "--debug"
}
& $pythonExe @runArgs
