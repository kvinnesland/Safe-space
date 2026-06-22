#!/usr/bin/env bash
# Førstegangoppsett for Safe CLI — installer avhengigheter og NLP-modeller.
# Bruk: bash setup.sh

set -euo pipefail

echo "=== Safe CLI — førstegangoppsett ==="

if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "Feil: Python ikke funnet. Installer Python 3.11+ og prøv igjen." >&2
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)

echo ""
echo "1. Installerer avhengigheter ..."
pip install -r requirements.txt

echo ""
echo "2. Laster ned norsk NLP-modell (nb_core_news_lg) ..."
$PYTHON -m spacy download nb_core_news_lg

echo ""
echo "3. Laster ned engelsk NLP-modell (en_core_web_lg) ..."
$PYTHON -m spacy download en_core_web_lg

echo ""
echo "4. Installerer safe CLI ..."
pip install --no-deps .

echo ""
echo "5. Oppretter output-mapper ..."
mkdir -p safe-output/logs

echo ""
echo "Klart! Kjør: ./safe <fil>"
