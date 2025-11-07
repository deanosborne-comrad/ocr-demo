# Download and extract PaddleOCR models for Windows
param(
    [string]$OutputPath = ".\models\paddleocr"
)

# Create directory structure
$dirs = @(
    "$OutputPath\whl\det\en\en_PP-OCRv3_det_infer",
    "$OutputPath\whl\rec\en\en_PP-OCRv3_rec_infer",
    "$OutputPath\whl\cls\ch_ppocr_mobile_v2.0_cls_infer"
)

foreach ($dir in $dirs) {
    New-Item -Path $dir -ItemType Directory -Force
    Write-Host "Created directory: $dir"
}

# Model URLs and extraction paths
$models = @(
    @{
        url = "https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_det_infer.tar"
        file = "en_PP-OCRv3_det_infer.tar"
        dest = "$OutputPath\whl\det\en\en_PP-OCRv3_det_infer"
    },
    @{
        url = "https://paddleocr.bj.bcebos.com/PP-OCRv3/english/en_PP-OCRv3_rec_infer.tar"
        file = "en_PP-OCRv3_rec_infer.tar"
        dest = "$OutputPath\whl\rec\en\en_PP-OCRv3_rec_infer"
    },
    @{
        url = "https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar"
        file = "ch_ppocr_mobile_v2.0_cls_infer.tar"
        dest = "$OutputPath\whl\cls\ch_ppocr_mobile_v2.0_cls_infer"
    }
)

# Download models
foreach ($model in $models) {
    Write-Host "Downloading $($model.file)..."
    try {
        Invoke-WebRequest -Uri $model.url -OutFile $model.file -ErrorAction Stop
        $fileSize = (Get-Item $model.file).Length
        Write-Host "Downloaded $($model.file) ($fileSize bytes)"
    }
    catch {
        Write-Error "Failed to download $($model.file): $_"
        continue
    }
}

# Try Windows tar first
foreach ($model in $models) {
    if (Test-Path $model.file) {
        Write-Host "Extracting $($model.file) with Windows tar..."
        try {
            tar -xf $model.file -C $model.dest
            Write-Host "Successfully extracted $($model.file)"
        }
        catch {
            Write-Warning "Windows tar failed for $($model.file), trying alternative..."
            
            # Try PowerShell expansion
            try {
                Add-Type -AssemblyName System.IO.Compression.FileSystem
                [System.IO.Compression.ZipFile]::ExtractToDirectory($model.file, $model.dest)
                Write-Host "Successfully extracted $($model.file) with .NET"
            }
            catch {
                Write-Error "All extraction methods failed for $($model.file)"
            }
        }
    }
}

# Cleanup tar files
foreach ($model in $models) {
    if (Test-Path $model.file) {
        Remove-Item $model.file
        Write-Host "Cleaned up $($model.file)"
    }
}

Write-Host "Model download and extraction complete!"
Write-Host "Models stored in: $OutputPath"
