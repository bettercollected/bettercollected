"""The backend never reads the photo library's access key (the webapp's picker does,
from its own environment), so a stack that has not set it must still start. It was a
required field, which stopped a new install at the first service."""

from backend.config.unsplash_settings import UnsplashSettings


def test_the_backend_starts_without_a_photo_library_key(monkeypatch):
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    settings = UnsplashSettings()
    assert settings.ACCESS_KEY == ""
    assert settings.BASE_URL == "https://api.unsplash.com"


def test_a_key_in_the_environment_is_still_read(monkeypatch):
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "from-the-environment")
    assert UnsplashSettings().ACCESS_KEY == "from-the-environment"
