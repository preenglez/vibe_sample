"""로그인 없이 KTX/SRT 열차 조회 (공개 API 직접 호출)"""
from __future__ import annotations
import logging
import requests
from dataclasses import dataclass

log = logging.getLogger(__name__)

# ── Korail 역코드 ──────────────────────────────────────────────────
KORAIL_STATION_CODES: dict[str, str] = {
    "서울": "0001", "용산": "0002", "영등포": "0003", "광명": "0004",
    "수원": "0005", "천안": "0007", "천안아산": "0009", "오송": "0010",
    "대전": "0011", "김천구미": "0013", "동대구": "0015", "신경주": "0016",
    "울산": "0017", "부산": "0020", "공주": "1065", "익산": "0051",
    "정읍": "0052", "광주송정": "0053", "나주": "0054", "목포": "0056",
    "전주": "0048", "순천": "0036", "여수EXPO": "0039",
    "포항": "0028", "마산": "0091", "창원": "0092", "진주": "0093",
}

# ── SRT 역코드 ─────────────────────────────────────────────────────
SRT_STATION_CODES: dict[str, str] = {
    "수서": "0551", "동탄": "0552", "평택지제": "0553",
    "천안아산": "0502", "오송": "0507", "대전": "0508",
    "김천구미": "0509", "동대구": "0004", "경주": "0513",
    "울산": "0514", "부산": "0003", "공주": "0510",
    "익산": "0517", "정읍": "0518", "광주송정": "0519",
    "나주": "0520", "목포": "0521",
    "포항": "0515", "마산": "0511", "창원중앙": "0512", "진주": "0516",
}


@dataclass
class TrainInfo:
    service: str        # "KTX" | "SRT"
    train_no: str
    dep_station: str
    arr_station: str
    dep_time: str       # "HH:MM"
    arr_time: str       # "HH:MM"
    date: str           # "YYYYMMDD"
    duration: str       # "Xh Ym"
    has_general: bool
    has_special: bool
    raw: dict


def _duration(dep: str, arr: str) -> str:
    dh, dm = int(dep[:2]), int(dep[2:4])
    ah, am = int(arr[:2]), int(arr[2:4])
    total = (ah * 60 + am) - (dh * 60 + dm)
    if total < 0:
        total += 1440
    return f"{total // 60}h {total % 60:02d}m"


# ── Korail 공개 조회 ───────────────────────────────────────────────

def search_korail(dep: str, arr: str, date: str, time: str = "000000") -> list[TrainInfo]:
    dep_code = KORAIL_STATION_CODES.get(dep)
    arr_code = KORAIL_STATION_CODES.get(arr)
    if not dep_code or not arr_code:
        raise ValueError(f"역 코드 없음: {dep} → {arr}")

    url = "https://www.letskorail.com/ebizprd/EbizPrdTicketpr21100W_pr21110.do"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.letskorail.com/",
    }
    data = {
        "strDptRsStnCd": dep_code,
        "strArvRsStnCd": arr_code,
        "strDptDt": date,
        "strDptTm": time,
        "radioInfo": "11",   # KTX 포함 전체
        "seatAttCd": "015",  # 기본석
        "psgInfoPerPrnb1": "1",
        "psgInfoPerPrnb5": "0",
        "psgInfoPerPrnb4": "0",
        "psgInfoPerPrnb2": "0",
        "psgInfoPerPrnb3": "0",
        "psgInfoPerPrnb6": "0",
        "psgInfoPerPrnb7": "0",
    }
    try:
        r = requests.post(url, data=data, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception as e:
        log.error("Korail search error: %s", e)
        raise

    result = []
    for t in r.json().get("trnsRdr", {}).get("trns", []):
        dep_t = t.get("dptTm", "")[:6]
        arr_t = t.get("arvTm", "")[:6]
        info = TrainInfo(
            service="KTX",
            train_no=t.get("trnNo", ""),
            dep_station=dep,
            arr_station=arr,
            dep_time=f"{dep_t[:2]}:{dep_t[2:4]}",
            arr_time=f"{arr_t[:2]}:{arr_t[2:4]}",
            date=date,
            duration=_duration(dep_t, arr_t),
            has_general=t.get("gnrmRsvPsbStr") != "매진",
            has_special=t.get("spcRsvPsbStr") != "매진",
            raw=t,
        )
        result.append(info)
    return result


# ── SRT 공개 조회 ──────────────────────────────────────────────────

def search_srt(dep: str, arr: str, date: str, time: str = "000000") -> list[TrainInfo]:
    dep_code = SRT_STATION_CODES.get(dep)
    arr_code = SRT_STATION_CODES.get(arr)
    if not dep_code or not arr_code:
        raise ValueError(f"역 코드 없음: {dep} → {arr}")

    url = "https://etk.srail.kr/hpg/hra/01/selectScheduleList.do"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://etk.srail.kr/main.do",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    }
    data = {
        "dptRsStnCd": dep_code,
        "arvRsStnCd": arr_code,
        "dptDt": date,
        "dptTm": time[:4],   # HHMM
        "psgNum": "1",
        "isRequest": "Y",
    }
    try:
        r = requests.post(url, data=data, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception as e:
        log.error("SRT search error: %s", e)
        raise

    result = []
    for t in r.json().get("resultMap", [{}])[0].get("trainListMap", []):
        dep_t = t.get("dptTm", "")[:4]   # HHMM
        arr_t = t.get("arvTm", "")[:4]
        dep_fmt = f"{dep_t[:2]}:{dep_t[2:]}"
        arr_fmt = f"{arr_t[:2]}:{arr_t[2:]}"
        info = TrainInfo(
            service="SRT",
            train_no=t.get("stlbTrnClsfCd", "SRT") + " " + t.get("trnNo", ""),
            dep_station=dep,
            arr_station=arr,
            dep_time=dep_fmt,
            arr_time=arr_fmt,
            date=date,
            duration=_duration(dep_t + "00", arr_t + "00"),
            has_general=t.get("gnrmRsvPsbStr") != "매진",
            has_special=t.get("spcRsvPsbStr") != "매진",
            raw=t,
        )
        result.append(info)
    return result
