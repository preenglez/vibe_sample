import queue
import tkinter as tk

import capture
from config import Config
from hotkeys import HotkeyManager
from region_selector import RegionSelector
from window_selector import WindowSelector

try:
    from tray import TrayIcon
except ImportError:
    TrayIcon = None

QUEUE_POLL_MS = 50

SELECTORS = {
    "region": RegionSelector,
    "window": WindowSelector,
}


class App:
    def __init__(self, config: Config):
        self.config = config
        self.job_queue: "queue.Queue[str]" = queue.Queue()
        self.busy = False

        self.root = tk.Tk()
        self.root.withdraw()

        self.hotkeys = HotkeyManager(config.hotkeys, self._on_hotkey)

        self.tray = None
        if TrayIcon is not None:
            try:
                self.tray = TrayIcon(on_quit=self.quit)
                self.tray.start()
            except Exception as exc:
                print(f"[경고] 트레이 아이콘을 시작하지 못했습니다: {exc}")

        self._poll_queue()

    def _on_hotkey(self, name):
        # keyboard 리스너 스레드에서 호출되므로 큐에 넣기만 한다.
        self.job_queue.put(name)

    def _poll_queue(self):
        try:
            while True:
                name = self.job_queue.get_nowait()
                self._start_capture(name)
        except queue.Empty:
            pass
        self.root.after(QUEUE_POLL_MS, self._poll_queue)

    def _start_capture(self, name):
        selector_cls = SELECTORS.get(name)
        if selector_cls is None or self.busy:
            return
        self.busy = True
        selector_cls(self.root, lambda bbox: self._finish(bbox, name))

    def _finish(self, bbox, prefix):
        try:
            if bbox is not None:
                path = capture.save_capture(
                    bbox, self.config.save_dir, prefix, self.config.jpg_quality
                )
                print(f"[저장됨] {path}")
                if self.tray:
                    self.tray.notify(f"저장됨: {path.name}")
        finally:
            self.busy = False

    def quit(self):
        self.hotkeys.stop()
        if self.tray:
            self.tray.stop()
        self.root.after(0, self.root.destroy)

    def run(self):
        print("화면캡쳐 도구가 백그라운드에서 실행 중입니다.")
        print(f"  영역 캡처 단축키 : {self.config.hotkeys.get('region')}")
        print(f"  창 캡처 단축키   : {self.config.hotkeys.get('window')}")
        print(f"  저장 폴더        : {self.config.save_dir}")
        print("종료: 트레이 아이콘의 '종료' 메뉴 또는 Ctrl+C")
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.quit()
