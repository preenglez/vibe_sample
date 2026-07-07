import threading

import pystray
from PIL import Image, ImageDraw


def _make_icon_image():
    img = Image.new("RGB", (64, 64), "black")
    draw = ImageDraw.Draw(img)
    draw.rectangle((8, 8, 56, 56), outline="white", width=4)
    draw.ellipse((22, 22, 42, 42), fill="white")
    return img


class TrayIcon:
    """작업 표시줄 트레이 아이콘. 종료 메뉴만 제공한다."""

    def __init__(self, on_quit):
        self.on_quit = on_quit
        self.icon = pystray.Icon(
            "screen_capture",
            _make_icon_image(),
            "Screen Capture Tool",
            menu=pystray.Menu(pystray.MenuItem("종료", self._quit)),
        )

    def _quit(self, icon, item):
        icon.stop()
        self.on_quit()

    def start(self):
        threading.Thread(target=self.icon.run, daemon=True).start()

    def notify(self, message):
        try:
            self.icon.notify(message)
        except Exception:
            pass

    def stop(self):
        try:
            self.icon.stop()
        except Exception:
            pass
