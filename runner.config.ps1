$RunnerConfig = @{
    # Update these once, then run .\run_local.ps1
    ProjectRoot = "C:\Projects\ai-resume-tailor"
    PythonExe = ".\.venv\Scripts\python.exe"
    RequirementsFile = "requirements.txt"
    ApiKeyFile = ".\secrets\gemini_api_key.txt"

    ##1 UPDATE before run
    JobDescriptionPath = "C:\Users\bonya\Downloads\JD_ EM RevenueCat SQL.md"
    ##2 UPDATE before run
    CompanyName = "RevenueCat"
    ##3 UPDATE before run
    JobTitle = "EM"
    ##4 UPDATE before run
    OutputCvFileName = "RevenueCat - Engineering Manager - YB.docx"
    ##5 UPDATE before run
    TierName = "freetier"
    ##6 UPDATE before run
    InputProfile = "role_manager"

    # Manual override for the selected tier model.
    # Leave empty to use TierProfiles.<TierName>.ModelName.
    ModelName = ""

    # One-place switch for model + throughput behavior.
    TierProfiles = @{
        freetier = @{
            ModelName = "gemini-2.5-flash"
            GenerationMode = "sequential"
            MinIntervalSeconds = "15"
            Max429Attempts = "5"
            BackoffBaseSeconds = "2"
        }
        model_flash = @{
            ModelName = "gemini-2.5-flash"
            GenerationMode = "concurrent"
            MinIntervalSeconds = "1"
            Max429Attempts = "4"
            BackoffBaseSeconds = "1"
        }   
        model_heavy = @{
            ModelName = "gemini-2.5-pro"
            GenerationMode = "concurrent"
            MinIntervalSeconds = "1"
            Max429Attempts = "5"
            BackoffBaseSeconds = "1"
        }   
    }

    # Optional
    TemplatePath = ""
    Debug = $false
    RunHealthCheck = $true
    UseRoleWideKnowledgeCache = $true
    InvalidateRoleWideKnowledgeCache = $false
    ForceKnowledgeReupload = $false
    RequireCachedTokenConfirmation = $true
    TriageDecisionMode = "always_continue"
    KnowledgeCacheTtlSeconds = 3600
    KnowledgeCacheRegistryPath = ".\runs\_cache\role_wide_knowledge_cache_registry.json"
}
