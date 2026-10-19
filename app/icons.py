"""Map files to Adwaita icon names (bundled in static/icons)."""
import mimetypes
import os

FOLDER = "folder"
GENERIC = "application-x-generic"

_BY_EXTENSION = {
    "text-x-generic": "txt md markdown log nfo rst text",
    "text-html": "html htm xhtml",
    "text-x-script": "sh bash zsh fish py rb pl php js mjs ts tsx jsx go rs c h cc cpp hpp "
                     "java kt swift lua sql json yaml yml toml ini conf cfg xml css scss "
                     "env ps1 bat cmd",
    "x-office-document": "pdf doc docx odt rtf epub",
    "x-office-spreadsheet": "xls xlsx ods csv tsv",
    "x-office-presentation": "ppt pptx odp key",
    "x-office-drawing": "odg drawio",
    "package-x-generic": "zip tar gz tgz bz2 xz zst 7z rar deb rpm apk iso img dmg jar",
    "application-x-executable": "exe msi appimage bin run elf",
    "font-x-generic": "ttf otf woff woff2",
    "application-certificate": "pem crt cer key p12 pfx csr gpg asc",
}
_EXTENSION_ICONS = {
    ext: icon for icon, exts in _BY_EXTENSION.items() for ext in exts.split()
}
_MIME_PREFIX_ICONS = {
    "image/": "image-x-generic",
    "audio/": "audio-x-generic",
    "video/": "video-x-generic",
    "text/": "text-x-generic",
    "font/": "font-x-generic",
}


def icon_name(name, is_dir=False):
    if is_dir:
        return FOLDER
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    if ext in _EXTENSION_ICONS:
        return _EXTENSION_ICONS[ext]
    mime, _ = mimetypes.guess_type(name)
    for prefix, icon in _MIME_PREFIX_ICONS.items():
        if mime and mime.startswith(prefix):
            return icon
    return "text-x-generic" if not ext else GENERIC
