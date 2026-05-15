import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USER_IDS = set(int(x) for x in os.getenv("ALLOWED_USER_IDS", "").split(",") if x.strip())

KORAIL_ID = os.getenv("KORAIL_ID", "")
KORAIL_PW = os.getenv("KORAIL_PW", "")
KORAIL_CARD_NUMBER = os.getenv("KORAIL_CARD_NUMBER", "")
KORAIL_CARD_EXPIRY = os.getenv("KORAIL_CARD_EXPIRY", "")
KORAIL_CARD_BIRTH = os.getenv("KORAIL_CARD_BIRTH", "")

SRT_ID = os.getenv("SRT_ID", "")
SRT_PW = os.getenv("SRT_PW", "")
SRT_CARD_NUMBER = os.getenv("SRT_CARD_NUMBER", "")
SRT_CARD_EXPIRY = os.getenv("SRT_CARD_EXPIRY", "")
SRT_CARD_BIRTH = os.getenv("SRT_CARD_BIRTH", "")

WATCH_INTERVAL = int(os.getenv("WATCH_INTERVAL", "30"))

# 주요 역 목록
KORAIL_STATIONS = [
    "서울", "용산", "영등포", "수원", "천안아산", "오송", "대전", "김천구미",
    "동대구", "경주", "울산", "부산", "광명", "평택", "공주", "익산",
    "정읍", "광주송정", "나주", "목포", "전주", "남원", "순천", "여수EXPO",
    "포항", "마산", "창원", "진주",
]

SRT_STATIONS = [
    "수서", "동탄", "평택지제", "천안아산", "오송", "대전", "김천구미",
    "동대구", "경주", "울산", "부산", "공주", "익산", "정읍", "광주송정",
    "나주", "목포", "포항", "마산", "창원중앙", "진주",
]
