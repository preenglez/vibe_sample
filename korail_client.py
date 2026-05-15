from __future__ import annotations
import logging
from typing import Optional
from korail2 import Korail, ReserveOption
from config import KORAIL_ID, KORAIL_PW, KORAIL_CARD_NUMBER, KORAIL_CARD_EXPIRY, KORAIL_CARD_BIRTH
from public_search import TrainInfo

log = logging.getLogger(__name__)


class KorailClient:
    def __init__(self):
        self._korail: Optional[Korail] = None

    def _ensure_login(self) -> Korail:
        if self._korail is None:
            self._korail = Korail(KORAIL_ID, KORAIL_PW, auto_login=True)
        return self._korail

    def reserve(self, train_info: TrainInfo, seat_type: str = "general") -> dict:
        """public_search.TrainInfo 를 받아서 korail2로 재검색 후 예약."""
        k = self._ensure_login()
        option = ReserveOption.GENERAL_ONLY if seat_type == "general" else ReserveOption.SPECIAL_ONLY
        try:
            # korail2로 다시 조회해서 Train 객체 확보
            trains = k.search_train(
                train_info.dep_station,
                train_info.arr_station,
                train_info.date,
                train_info.dep_time.replace(":", "") + "00",
                available_only=False,
            )
            target = next(
                (t for t in trains if t.train_no == train_info.train_no), None
            )
            if target is None:
                return {"success": False, "error": "열차를 찾을 수 없습니다. 시간이 지났을 수 있습니다."}

            rsv = k.reserve(target, option=option)
            return {
                "success": True,
                "rsv_no": rsv.rsv_no,
                "total_price": rsv.total_price,
                "pay_limit_time": rsv.buy_limit_date + " " + rsv.buy_limit_time,
            }
        except Exception as e:
            log.warning("KTX reserve failed: %s", e)
            return {"success": False, "error": str(e)}

    def pay(self, rsv_no: str) -> dict:
        k = self._ensure_login()
        try:
            k.pay_with_card(
                rsv_no,
                card_number=KORAIL_CARD_NUMBER,
                expiry=KORAIL_CARD_EXPIRY,
                birth=KORAIL_CARD_BIRTH,
                pwd_2digit="",
            )
            return {"success": True}
        except Exception as e:
            log.warning("KTX pay failed: %s", e)
            return {"success": False, "error": str(e)}
