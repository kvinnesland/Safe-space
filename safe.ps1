#Requires -Version 5.1
<#
.SYNOPSIS
    Anonymize PII in a file before passing it to Claude.
.EXAMPLE
    .\safe.ps1 C:\Users\me\Downloads\rapport.xlsx
#>
param(
    [Parameter(Mandatory, Position = 0)]
    [string]$FilePath
)

$ScriptDir  = $PSScriptRoot
$OutputDir  = Join-Path $ScriptDir "safe-output"
$InputAbs   = (Resolve-Path $FilePath -ErrorAction Stop).Path
$InputDir   = Split-Path -Parent $InputAbs
$InputName  = Split-Path -Leaf  $InputAbs

New-Item -ItemType Directory -Force $OutputDir | Out-Null

docker compose -f "$ScriptDir\docker-compose.yml" run --rm `
    -v "${InputDir}:/safe_input:ro" `
    -v "${OutputDir}:/app/safe-output" `
    safe "/safe_input/$InputName" `
    --output-dir /app/safe-output
