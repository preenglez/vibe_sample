import json
from pathlib import Path

DEFAULT_CONFIG = {
    "save_dir": str(Path.home() / "Pictures" / "ScreenCapture"),
    "hotkeys": {
        "region": "ctrl+shift+a",
        "window": "ctrl+shift+w",
    },
    "jpg_quality": 90,
}


class Config:
    def __init__(self, path: Path):
        self.path = path
        data = json.loads(json.dumps(DEFAULT_CONFIG))

        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            data.update(loaded)
            merged_hotkeys = dict(DEFAULT_CONFIG["hotkeys"])
            merged_hotkeys.update(loaded.get("hotkeys", {}))
            data["hotkeys"] = merged_hotkeys
        else:
            self._write(path, data)

        self.save_dir = data["save_dir"]
        self.hotkeys = data["hotkeys"]
        self.jpg_quality = data["jpg_quality"]

    @staticmethod
    def _write(path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path=None) -> "Config":
        if path is None:
            path = Path(__file__).resolve().parent / "config.json"
        return cls(Path(path))
