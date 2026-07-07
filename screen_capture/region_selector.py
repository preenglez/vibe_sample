import time
import tkinter as tk

import capture


class RegionSelector:
    """마우스 드래그로 캡쳐할 영역을 지정하는 전체화면 오버레이."""

    MIN_SIZE = 5

    def __init__(self, root: tk.Tk, on_result):
        self.root = root
        self.on_result = on_result
        self.start_x = None
        self.start_y = None
        self.rect_id = None

        bbox = capture.virtual_screen_bbox()

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry(f"{bbox['width']}x{bbox['height']}+{bbox['left']}+{bbox['top']}")
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.25)
        self.win.configure(bg="gray20")
        self.win.config(cursor="crosshair")

        self.canvas = tk.Canvas(self.win, bg="gray20", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.win.bind("<Escape>", self._on_cancel)

        self.win.focus_force()

    def _on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline="red", width=2,
        )

    def _on_drag(self, event):
        if self.rect_id is not None:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def _on_release(self, event):
        if self.start_x is None:
            self._on_cancel()
            return

        x0, y0, x1, y1 = self.start_x, self.start_y, event.x, event.y
        left, top = min(x0, x1), min(y0, y1)
        width, height = abs(x1 - x0), abs(y1 - y0)
        origin_x = self.win.winfo_rootx()
        origin_y = self.win.winfo_rooty()

        self._close()

        if width < self.MIN_SIZE or height < self.MIN_SIZE:
            self.on_result(None)
            return

        self.on_result({
            "left": origin_x + left,
            "top": origin_y + top,
            "width": width,
            "height": height,
        })

    def _on_cancel(self, event=None):
        self._close()
        self.on_result(None)

    def _close(self):
        self.win.destroy()
        self.root.update()
        time.sleep(0.15)
