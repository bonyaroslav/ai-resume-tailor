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
    # Reuse uploaded knowledge and Gemini cached content when possible.
    # Keep this ON for normal use.
    # Example: leave ON for daily runs to avoid uploading the same knowledge again.
    UseRoleWideKnowledgeCache = $true
    # Force a fresh run cache for the current run instead of reusing an existing one.
    # Turn ON when resuming or regenerating after changing knowledge files for the same run.
    # Example: you edited role_engineer knowledge and now run `resume` for an old run.
    InvalidateRoleWideKnowledgeCache = $false
    # Re-upload all knowledge files even if unchanged copies already exist in the local cache registry.
    # Turn ON only for a full cache reset or when uploaded file reuse looks wrong.
    # Example: you switched from role_engineer to role_manager and want a completely clean re-upload.
    ForceKnowledgeReupload = $true
    # Fail fast if Gemini says the cache was not actually used.
    # Keep this ON unless you are debugging cache behavior.
    # Example: leave ON to catch cases where cached content exists but requests still send full tokens.
    RequireCachedTokenConfirmation = $true
    # What to do after triage:
    # "prompt" = ask you, "follow_ai" = follow model verdict, "always_continue" = never stop at triage.
    # Example: use "always_continue" when you want the pipeline to keep going without pauses.
    TriageDecisionMode = "always_continue"
    # How long the Gemini run cache stays valid, in seconds.
    # Increase for repeated work in a short window; decrease if you want caches to expire sooner.
    # Example: 3600 = reuse for 1 hour.
    KnowledgeCacheTtlSeconds = 3600
    # Local JSON file that remembers uploaded knowledge files and run cache metadata.
    # Keep the default unless you intentionally want a separate cache registry.
    # Example: use a different path only if you want isolated caches for experiments.
    KnowledgeCacheRegistryPath = ".\runs\_cache\role_wide_knowledge_cache_registry.json"
}
