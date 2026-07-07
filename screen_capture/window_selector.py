import time
import tkinter as tk

import win32con
import win32gui

import capture


class WindowSelector:
    """마우스가 위치한 창을 하이라이트하고 클릭하면 해당 창을 캡쳐 대상으로 선택하는 오버레이."""

    POLL_MS = 40

    def __init__(self, root: tk.Tk, on_result):
        self.root = root
        self.on_result = on_result
        self.current_hwnd = None
        self.current_rect = None
        self.highlight_id = None
        self.poll_job = None

        bbox = capture.virtual_screen_bbox()

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry(f"{bbox['width']}x{bbox['height']}+{bbox['left']}+{bbox['top']}")
        self.win.attributes("-topmost", True)
        # 'magenta' 색상만 투명하게 처리되어(Windows 전용), 하이라이트 테두리만 보이고
        # 나머지 화면은 오버레이에 가려지지 않는다.
        self.win.attributes("-transparentcolor", "magenta")
        self.win.configure(bg="magenta")
        self.win.config(cursor="hand2")

        self.canvas = tk.Canvas(self.win, bg="magenta", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.own_hwnd = win32gui.GetAncestor(self.win.winfo_id(), win32con.GA_ROOT)

        self.canvas.bind("<Button-1>", self._on_click)
        self.win.bind("<Escape>", self._on_cancel)
        self.win.focus_force()

        self._poll()

    def _find_window_under_cursor(self):
        pt = win32gui.GetCursorPos()
        hwnd = win32gui.GetTopWindow(None)
        while hwnd:
            if (
                hwnd != self.own_hwnd
                and win32gui.IsWindowVisible(hwnd)
                and not win32gui.IsIconic(hwnd)
                and win32gui.GetWindowText(hwnd)
            ):
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                if left <= pt[0] < right and top <= pt[1] < bottom:
                    return hwnd, (left, top, right, bottom)
            hwnd = win32gui.GetWindow(hwnd, win32con.GW_HWNDNEXT)
        return None, None

    def _poll(self):
        hwnd, rect = self._find_window_under_cursor()
        if rect != self.current_rect:
            self._draw_highlight(rect)
        self.current_hwnd, self.current_rect = hwnd, rect
        self.poll_job = self.root.after(self.POLL_MS, self._poll)

    def _draw_highlight(self, rect):
        if self.highlight_id is not None:
            self.canvas.delete(self.highlight_id)
            self.highlight_id = None
        if rect is None:
            return
        origin_x = self.win.winfo_rootx()
        origin_y = self.win.winfo_rooty()
        left, top, right, bottom = rect
        self.highlight_id = self.canvas.create_rectangle(
            left - origin_x, top - origin_y, right - origin_x, bottom - origin_y,
            outline="red", width=3,
        )

    def _on_click(self, event):
        hwnd, rect = self.current_hwnd, self.current_rect
        self._close()

        if hwnd is None:
            self.on_result(None)
            return

        left, top, right, bottom = rect
        self.on_result({
            "left": left,
            "top": top,
            "width": right - left,
            "height": bottom - top,
        })

    def _on_cancel(self, event=None):
        self._close()
        self.on_result(None)

    def _close(self):
        if self.poll_job is not None:
            self.root.after_cancel(self.poll_job)
            self.poll_job = None
        self.win.destroy()
        self.root.update()
        time.sleep(0.15)
