from __future__ import annotations
import logging
from typing import Optional
from SRT import SRT
from SRT.passenger import Adult
from config import SRT_ID, SRT_PW, SRT_CARD_NUMBER, SRT_CARD_EXPIRY, SRT_CARD_BIRTH
from public_search import TrainInfo

log = logging.getLogger(__name__)


class SRTClient:
    def __init__(self):
        self._srt: Optional[SRT] = None

    def _ensure_login(self) -> SRT:
        if self._srt is None:
            self._srt = SRT(SRT_ID, SRT_PW)
        return self._srt

    def reserve(self, train_info: TrainInfo, seat_type: str = "general") -> dict:
        """public_search.TrainInfo 를 받아서 SRT 라이브러리로 재검색 후 예약."""
        s = self._ensure_login()
        try:
            trains = s.search_train(
                train_info.dep_station,
                train_info.arr_station,
                train_info.date,
                train_info.dep_time.replace(":", ""),
                available_only=False,
            )
            target = next(
                (t for t in trains if t.train_number in train_info.train_no), None
            )
            if target is None:
                return {"success": False, "error": "열차를 찾을 수 없습니다."}

            rsv = s.reserve(
                target,
                passengers=[Adult()],
                special_seat=(seat_type == "special"),
            )
            return {
                "success": True,
                "rsv_no": rsv.reservation_number,
                "total_price": rsv.total_cost,
                "pay_limit_time": rsv.pay_limit_date,
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
