from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional
from korail2 import Korail, Train, ReserveOption
from config import KORAIL_ID, KORAIL_PW, KORAIL_CARD_NUMBER, KORAIL_CARD_EXPIRY, KORAIL_CARD_BIRTH

log = logging.getLogger(__name__)


@dataclass
class TrainInfo:
    service: str  # "KTX"
    train_no: str
    dep_station: str
    arr_station: str
    dep_time: str   # "HH:MM"
    arr_time: str
    date: str       # "YYYYMMDD"
    duration: str
    has_general: bool
    has_special: bool
    raw: object  # korail2 Train object


class KorailClient:
    def __init__(self):
        self._korail: Optional[Korail] = None

    def _ensure_login(self):
        if self._korail is None:
            k = Korail(KORAIL_ID, KORAIL_PW, auto_login=True)
            self._korail = k
        return self._korail

    def search_trains(self, dep: str, arr: str, date: str, time: str = "000000") -> list[TrainInfo]:
        """date: YYYYMMDD, time: HHMMSS"""
        k = self._ensure_login()
        trains = k.search_train_allday(dep, arr, date, time, available_only=False)
        result = []
        for t in trains:
            info = TrainInfo(
                service="KTX",
                train_no=t.train_no,
                dep_station=t.dep_name,
                arr_station=t.arr_name,
                dep_time=f"{t.dep_time[:2]}:{t.dep_time[2:4]}",
                arr_time=f"{t.arr_time[:2]}:{t.arr_time[2:4]}",
                date=t.dep_date,
                duration=self._calc_duration(t.dep_time, t.arr_time),
                has_general=t.general_seat_state != "매진",
                has_special=t.special_seat_state != "매진",
                raw=t,
            )
            result.append(info)
        return result

    def reserve(self, train_info: TrainInfo, seat_type: str = "general") -> dict:
        """seat_type: 'general' or 'special'. Returns reservation info dict."""
        k = self._ensure_login()
        t = train_info.raw
        option = ReserveOption.GENERAL_ONLY if seat_type == "general" else ReserveOption.SPECIAL_ONLY
        try:
            reservation = k.reserve(t, option=option)
            return {
                "success": True,
                "rsv_no": reservation.rsv_no,
                "total_price": reservation.total_price,
                "seat_no": reservation.seat_no_count,
                "pay_limit_time": reservation.buy_limit_date + " " + reservation.buy_limit_time,
            }
        except Exception as e:
            log.warning("KTX reserve failed: %s", e)
            return {"success": False, "error": str(e)}

    def pay(self, rsv_no: str) -> dict:
        """결제 처리 (등록 카드 사용)"""
        k = self._ensure_login()
        try:
            k.pay_with_card(
                rsv_no,
                card_number=KORAIL_CARD_NUMBER,
                expiry=KORAIL_CARD_EXPIRY,
                birth=KORAIL_CARD_BIRTH,
                pwd_2digit="",  # 필요 시 환경변수로 추가
            )
            return {"success": True}
        except Exception as e:
            log.warning("KTX pay failed: %s", e)
            return {"success": False, "error": str(e)}

    def _calc_duration(self, dep: str, arr: str) -> str:
        dh, dm = int(dep[:2]), int(dep[2:4])
        ah, am = int(arr[:2]), int(arr[2:4])
        total = (ah * 60 + am) - (dh * 60 + dm)
        if total < 0:
            total += 1440
        return f"{total // 60}h {total % 60}m"
