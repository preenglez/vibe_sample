from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Optional
from SRT import SRT
from SRT.passenger import Adult
from config import SRT_ID, SRT_PW, SRT_CARD_NUMBER, SRT_CARD_EXPIRY, SRT_CARD_BIRTH

log = logging.getLogger(__name__)


@dataclass
class TrainInfo:
    service: str  # "SRT"
    train_no: str
    dep_station: str
    arr_station: str
    dep_time: str
    arr_time: str
    date: str
    duration: str
    has_general: bool
    has_special: bool
    raw: object


class SRTClient:
    def __init__(self):
        self._srt: Optional[SRT] = None

    def _ensure_login(self):
        if self._srt is None:
            s = SRT(SRT_ID, SRT_PW)
            self._srt = s
        return self._srt

    def search_trains(self, dep: str, arr: str, date: str, time: str = "000000") -> list[TrainInfo]:
        """date: YYYYMMDD, time: HHMMSS"""
        s = self._ensure_login()
        hhmm = time[:4]
        trains = s.search_train(dep, arr, date, hhmm, available_only=False)
        result = []
        for t in trains:
            dep_t = t.dep_time.replace(":", "")
            arr_t = t.arr_time.replace(":", "")
            info = TrainInfo(
                service="SRT",
                train_no=t.train_name + " " + t.train_number,
                dep_station=t.dep_station_name,
                arr_station=t.arr_station_name,
                dep_time=t.dep_time[:5],
                arr_time=t.arr_time[:5],
                date=t.dep_date,
                duration=self._calc_duration(dep_t, arr_t),
                has_general=t.general_seat_available(),
                has_special=t.special_seat_available(),
                raw=t,
            )
            result.append(info)
        return result

    def reserve(self, train_info: TrainInfo, seat_type: str = "general") -> dict:
        s = self._ensure_login()
        t = train_info.raw
        try:
            if seat_type == "special":
                reservation = s.reserve(t, passengers=[Adult()], special_seat=True)
            else:
                reservation = s.reserve(t, passengers=[Adult()])
            return {
                "success": True,
                "rsv_no": reservation.reservation_number,
                "total_price": reservation.total_cost,
                "pay_limit_time": reservation.pay_limit_date,
            }
        except Exception as e:
            log.warning("SRT reserve failed: %s", e)
            return {"success": False, "error": str(e)}

    def pay(self, rsv_no: str) -> dict:
        s = self._ensure_login()
        try:
            reservations = s.get_reservations()
            target = next((r for r in reservations if r.reservation_number == rsv_no), None)
            if target is None:
                return {"success": False, "error": "예약을 찾을 수 없습니다."}
            s.pay_with_card(
                target,
                card_number=SRT_CARD_NUMBER,
                card_expiry=SRT_CARD_EXPIRY,
                card_birth=SRT_CARD_BIRTH,
            )
            return {"success": True}
        except Exception as e:
            log.warning("SRT pay failed: %s", e)
            return {"success": False, "error": str(e)}

    def _calc_duration(self, dep: str, arr: str) -> str:
        dh, dm = int(dep[:2]), int(dep[2:4])
        ah, am = int(arr[:2]), int(arr[2:4])
        total = (ah * 60 + am) - (dh * 60 + dm)
        if total < 0:
            total += 1440
        return f"{total // 60}h {total % 60}m"
