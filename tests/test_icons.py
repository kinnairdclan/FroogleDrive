import pytest

from app.icons import icon_name


@pytest.mark.parametrize("name, is_dir, icon", [
    ("photos", True, "folder"),
    ("photos.zip", True, "folder"),          # directories win over extensions
    ("notes.TXT", False, "text-x-generic"),
    ("README", False, "text-x-generic"),     # no extension
    ("index.html", False, "text-html"),
    ("app.py", False, "text-x-script"),
    ("report.pdf", False, "x-office-document"),
    ("budget.xlsx", False, "x-office-spreadsheet"),
    ("deck.pptx", False, "x-office-presentation"),
    ("backup.tar.gz", False, "package-x-generic"),
    ("setup.exe", False, "application-x-executable"),
    ("font.woff2", False, "font-x-generic"),
    ("server.pem", False, "application-certificate"),
    ("photo.jpg", False, "image-x-generic"),     # via MIME type
    ("song.mp3", False, "audio-x-generic"),
    ("movie.mp4", False, "video-x-generic"),
    ("data.mystery", False, "application-x-generic"),  # unknown MIME
    ("blob.json5", False, "application-x-generic"),
])
def test_icon_name(name, is_dir, icon):
    assert icon_name(name, is_dir) == icon
