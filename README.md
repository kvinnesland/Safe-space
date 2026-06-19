# Safe-space

Anonymiserer personopplysninger (PII) i dokumenter før de sendes til Claude eller andre KI-verktøy. All behandling skjer lokalt i Docker — ingen data forlater maskinen din.

## Forutsetninger

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installert og kjørende
- Git

## Kom i gang

```bash
git clone https://github.com/kvinnesland/Safe-space.git
cd Safe-space
docker compose build
```

Første bygg tar ~5 minutter (laster ned norske og engelske NLP-modeller). Etterfølgende bygg er raske.

## Bruk

**PowerShell (Windows):**
```powershell
.\safe.ps1 C:\Users\brukernavn\Downloads\rapport.xlsx
```

**Git Bash / Mac / Linux:**
```bash
./safe /c/Users/brukernavn/Downloads/rapport.xlsx
```

Anonymisert fil skrives til `Safe-space/safe-output/` med tidsstempel i filnavnet:

```
safe-output/rapport_anonymized_2026-06-20_103045.xlsx
```

Originalen røres ikke.

## Støttede filtyper

| Format | Filtype |
|--------|---------|
| Word | `.docx` |
| Excel | `.xlsx` |
| PowerPoint | `.pptx` |
| PDF | `.pdf` |
| CSV | `.csv` |
| Ren tekst | `.txt` |

## Hva som anonymiseres

| Plasseholder | Innhold |
|---|---|
| `[NAME]` | Navn på personer |
| `[FØDSELSNUMMER]` | Fødselsnummer og D-nummer |
| `[EMAIL]` | E-postadresser |
| `[PHONE]` | Telefon- og mobilnumre |
| `[ACCOUNT_NUMBER]` | Norske kontonumre (XXXX.YY.ZZZZZ) |
| `[ORGNUMMER]` | Organisasjonsnumre |
| `[ADRESSE]` | Gateadresser |
| `[POSTNUMMER]` | Postnumre |
| `[POSTSTED]` | Poststed/by |
| `[ADDRESS]` | Postnummer + by (kombinert) |
| `[DATE_OF_BIRTH]` | Fødselsdatoer |
| `[DATO]` | Norske datoer (f.eks. «14. mars 2024») |
| `[HEALTH_INFO]` | Helseopplysninger |
| `[IP_ADDRESS]` | IP-adresser |
| `[SENSITIVE_DATA]` | Øvrig sensitiv informasjon (URLer m.m.) |

## Oppdatering

```powershell
git pull
docker compose build
```

## Personvern

- Ingen data sendes til eksterne tjenester
- Originalfiler leses kun og skrives aldri tilbake
- Anonymiserte filer og en enkel audit-logg lagres i `safe-output/`
