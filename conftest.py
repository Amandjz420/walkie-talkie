import shutil
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_media_root(settings):
    media_root = Path(settings.BASE_DIR) / "test_media"
    settings.MEDIA_ROOT = media_root
    media_root.mkdir(exist_ok=True)
    yield
    shutil.rmtree(media_root, ignore_errors=True)
