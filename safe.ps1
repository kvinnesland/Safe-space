#Requires -Version 5.1
<#
.SYNOPSIS
    Anonymiser PII i en fil for den sendes til Claude.
.EXAMPLE
    .\safe.ps1 C:\Users\meg\Downloads\rapport.xlsx
#>
param(
    [Parameter(Mandatory, Position = 0)]
    [string]$FilePath,
    [string]$OutputDir = (Join-Path $PSScriptRoot "safe-output")
)

$InputAbs = (Resolve-Path $FilePath -ErrorAction Stop).Path
New-Item -ItemType Directory -Force $OutputDir        | Out-Null
New-Item -ItemType Directory -Force "$OutputDir\logs" | Out-Null

python -m safe_cli.main "$InputAbs" --output-dir "$OutputDir"
