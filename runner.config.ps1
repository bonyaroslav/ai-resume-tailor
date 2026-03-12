$RunnerConfig = @{
    # Update these once, then run .\run_local.ps1
    ProjectRoot = "C:\Projects\ai-resume-tailor"
    PythonExe = ".\.venv\Scripts\python.exe"
    RequirementsFile = "requirements.txt"
    ApiKeyFile = ".\secrets\gemini_api_key.txt"

    JobDescriptionPath = "C:\Users\bonya\Downloads\JD_ Mindera.txt"
    CompanyName = "Mindera"
    TierName = "freetier"
    RoleName = "role_senior_dotnet_engineer"

    # Manual override for the selected tier model.
    # Leave empty to use TierProfiles.<TierName>.ModelName.
    ModelName = ""

    # One-place switch for model + throughput behavior.
    TierProfiles = @{
        freetier = @{
            ModelName = "gemini-2.5-flash"
            GenerationMode = "sequential"
            MinIntervalSeconds = "15"
            Max429Attempts = "2"
            BackoffBaseSeconds = "2"
        }
        heavy_model = @{
            ModelName = "gemini-2.5-pro"
            GenerationMode = "concurrent"
            MinIntervalSeconds = "0"
            Max429Attempts = "5"
            BackoffBaseSeconds = "1"
        }
    }

    # Optional
    TemplatePath = ""
    Debug = $false
    RunHealthCheck = $true
}
