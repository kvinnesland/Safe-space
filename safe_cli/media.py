"""
Shared constants for embedded media removal.

Under GDPR, images, video, and audio of persons are personal data.
Biometric data (faces, voices) falls under Article 9.
We cannot safely determine programmatically whether media contains
persons, so we remove ALL embedded media and replace with placeholders.
"""

# Standalone files safe cannot process — these ARE the personal data
STANDALONE_IMAGE_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp",
    ".tiff", ".tif", ".webp", ".heic", ".svg",
}
STANDALONE_VIDEO_EXT = {
    ".mp4", ".avi", ".mov", ".mkv", ".wmv",
    ".flv", ".webm", ".m4v", ".mpeg", ".mpg",
}
STANDALONE_AUDIO_EXT = {
    ".mp3", ".wav", ".aac", ".ogg", ".flac",
    ".m4a", ".wma", ".opus", ".aiff",
}
STANDALONE_MEDIA_EXT = STANDALONE_IMAGE_EXT | STANDALONE_VIDEO_EXT | STANDALONE_AUDIO_EXT

# Placeholders written into documents where media has been removed
PLACEHOLDER_IMAGE = "[BILDE FJERNET — KAN INNEHOLDE PII]"
PLACEHOLDER_VIDEO = "[VIDEO FJERNET — KAN INNEHOLDE PII]"
PLACEHOLDER_AUDIO = "[LYD FJERNET — KAN INNEHOLDE PII]"
PLACEHOLDER_MEDIA = "[MEDIAFIL FJERNET — KAN INNEHOLDE PII]"

STANDALONE_MESSAGE = """\
{sep}
MEDIAFIL — IKKE ANONYMISERT
{sep}
Bilder, lyd og video av personer er personopplysninger under GDPR,
og ansikter / stemmer / biometriske kjennetegn er saerlig beskyttet
etter artikkel 9.

safe anonymiserer ikke mediafiler automatisk fordi vi ikke kan
garantere at alle ansikter, stemmer og videoframes er fjernet.

Del aldri denne filen med verktoey som kjoerer utenfor EU/EOES
uten manuell gjennomgang og eventuell sladding.
{sep}"""

def standalone_warning(suffix: str) -> str:
    sep = "=" * 60
    return STANDALONE_MESSAGE.format(sep=sep)
