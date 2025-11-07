[CmdletBinding()]
param(
    [string]$Model = "allenai/olmOCR-2-7B-1025-FP8",
    [int]$Port = 30024,
    [float]$GpuMemoryUtilization = 0.6,
    [int]$MaxModelLen = 16384,
    [string]$HfToken = $env:HF_TOKEN
)

if (-not $HfToken) {
    Write-Warning "HF_TOKEN is not set. You need a Hugging Face token with access to $Model."
}

$cmd = @(
    "vllm",
    "serve",
    $Model,
    "--served-model-name", "olmocr",
    "--quantization", "fp8",
    "--max-model-len", $MaxModelLen,
    "--gpu-memory-utilization", $GpuMemoryUtilization,
    "--port", $Port
)

Write-Host "Launching local olmOCR server on http://localhost:$Port/v1" -ForegroundColor Cyan
Write-Host "Command: $($cmd -join ' ')" -ForegroundColor Gray

if ($HfToken) {
    $env:HUGGING_FACE_HUB_TOKEN = $HfToken
}

& $cmd
