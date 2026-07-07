import keyboard


class HotkeyManager:
    """전역 단축키를 등록하고, 눌렸을 때 콜백(callback)에 모드 이름을 전달한다.

    keyboard 라이브러리의 콜백은 별도 리스너 스레드에서 실행되므로,
    Tkinter를 직접 다루지 않고 이름만 전달하도록 한다.
    """

    def __init__(self, hotkeys: dict, callback):
        self.callback = callback
        self._registered = []
        for name, combo in hotkeys.items():
            keyboard.add_hotkey(combo, self._make_handler(name))
            self._registered.append(combo)

    def _make_handler(self, name):
        def handler():
            self.callback(name)
        return handler

    def stop(self):
        for combo in self._registered:
            try:
                keyboard.remove_hotkey(combo)
            except KeyError:
                pass
        self._registered.clear()
