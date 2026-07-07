from datetime import datetime
from pathlib import Path

import mss
from PIL import Image


def virtual_screen_bbox() -> dict:
    """모든 모니터를 합친 가상 화면 영역(절대 좌표)을 반환한다."""
    with mss.mss() as sct:
        return dict(sct.monitors[0])


def grab_bbox(bbox: dict) -> Image.Image:
    """bbox(left, top, width, height)에 해당하는 화면 영역을 캡쳐한다."""
    with mss.mss() as sct:
        shot = sct.grab(bbox)
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def build_filename(prefix: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return f"{prefix}_{ts}.jpg"


def save_capture(bbox: dict, save_dir: str, prefix: str, quality: int = 90) -> Path:
    save_path = Path(save_dir).expanduser()
    save_path.mkdir(parents=True, exist_ok=True)

    img = grab_bbox(bbox)
    filepath = save_path / build_filename(prefix)
    img.save(filepath, "JPEG", quality=quality)
    return filepath
