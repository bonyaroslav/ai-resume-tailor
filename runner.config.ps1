$RunnerConfig = @{
    # Update these once, then run .\run_local.ps1
    ProjectRoot = "C:\Projects\ai-resume-tailor"
    PythonExe = ".\.venv\Scripts\python.exe"
    RequirementsFile = "requirements.txt"
    ApiKeyFile = ".\secrets\gemini_api_key.txt"

    JobDescriptionPath = "C:\Users\bonya\Downloads\JD_ Mindera.txt"
    CompanyName = "Mindera"
    ModelName = "gemini-2.5-flash"

    # Optional
    TemplatePath = ""
    Debug = $false
    RunHealthCheck = $true
}
