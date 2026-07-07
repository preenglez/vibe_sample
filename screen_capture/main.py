import argparse
import sys

if sys.platform == "win32":
    # DPI 스케일링 환경(125%, 150% 등)에서 tkinter 좌표와 실제 픽셀 좌표가
    # 어긋나 캡쳐 영역이 잘못 잡히는 것을 방지한다.
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from app import App
from config import Config


def parse_args():
    parser = argparse.ArgumentParser(description="로컬 화면 캡쳐 도구")
    parser.add_argument("--config", type=str, default=None, help="config.json 경로 (기본: 같은 폴더의 config.json)")
    return parser.parse_args()


def main():
    args = parse_args()
    config = Config.load(args.config)
    App(config).run()


if __name__ == "__main__":
    main()
