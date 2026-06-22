#Requires -Version 5.1
<#
.SYNOPSIS
    Førstegangoppsett for Safe CLI — installerer avhengigheter og NLP-modeller.
.EXAMPLE
    .\setup.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Write-Host "=== Safe CLI — forstegangoppsett ===" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python ikke funnet. Installer Python 3.11+ og prøv igjen."
    exit 1
}

Write-Host "`n1. Installerer avhengigheter ..."
pip install -r requirements.txt

Write-Host "`n2. Laster ned norsk NLP-modell (nb_core_news_lg) ..."
python -m spacy download nb_core_news_lg

Write-Host "`n3. Laster ned engelsk NLP-modell (en_core_web_lg) ..."
python -m spacy download en_core_web_lg

Write-Host "`n4. Installerer safe CLI ..."
pip install --no-deps .

Write-Host "`n5. Oppretter output-mapper ..."
New-Item -ItemType Directory -Force "safe-output"      | Out-Null
New-Item -ItemType Directory -Force "safe-output\logs" | Out-Null

Write-Host "`nKlart! Kjor: .\safe.ps1 <fil>" -ForegroundColor Green
