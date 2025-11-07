[CmdletBinding()]
param(
    [string]$EnvFile = ".\.env"
)

Write-Host "olmOCR does not ship light-weight local models that can be downloaded ahead of time." -ForegroundColor Yellow
Write-Host "Instead, point the pipeline at a running olmOCR endpoint (DeepInfra, Parasail, Cirrascale, or your own vLLM deployment)." -ForegroundColor Yellow
Write-Host ""
Write-Host "To run quantized OCR locally, launch 'scripts/start_local_olmocr.ps1' which uses vLLM with the FP8 checkpoint." -ForegroundColor Yellow

if (-Not (Test-Path $EnvFile)) {
    Write-Warning "No .env file was found at $EnvFile. Create one with OLMOCR_SERVER_URL, OLMOCR_MODEL, and OLMOCR_API_KEY."
    return
}

$envContent = Get-Content $EnvFile | Where-Object { $_ -match '^(OLMOCR_SERVER_URL|OLMOCR_MODEL|OLMOCR_API_KEY)=' }
if ($envContent.Count -eq 0) {
    Write-Warning "The .env file does not define OLMOCR_* variables yet."
} else {
    Write-Host "Current olmOCR configuration extracted from $EnvFile:`n" -ForegroundColor Cyan
    $envContent | ForEach-Object { Write-Host "  $_" }
}

Write-Host "`nSet OLMOCR_SERVER_URL to an OpenAI-compatible endpoint (e.g. https://api.deepinfra.com/v1/openai)," `
    + " OLMOCR_MODEL to allenai/olmOCR-2-7B-1025-FP8 (or your hosted variant), and provide OLMOCR_API_KEY when the provider requires it." -ForegroundColor Green
