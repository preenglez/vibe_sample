"""SRT 예약 클라이언트 - HTTP 직접 구현 (라이브러리 불필요)"""
from __future__ import annotations
import logging
import requests
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from base64 import b64decode, b64encode
from config import SRT_ID, SRT_PW, SRT_CARD_NUMBER, SRT_CARD_EXPIRY, SRT_CARD_BIRTH
from public_search import TrainInfo, SRT_STATION_CODES

log = logging.getLogger(__name__)

BASE = "https://etk.srail.kr"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": f"{BASE}/main.do",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}


class SRTClient:
    def __init__(self):
        self._session: requests.Session | None = None

    def _ensure_login(self) -> requests.Session:
        if self._session:
            return self._session

        s = requests.Session()
        s.headers.update(HEADERS)

        # 공개키 가져오기
        r = s.post(f"{BASE}/cmc/01/selectPublicKey.do")
        pub_key_pem = r.json().get("publicKey", "")
        if not pub_key_pem:
            raise RuntimeError("SRT 공개키 획득 실패")

        # 비밀번호 RSA 암호화
        key = RSA.import_key(b64decode(pub_key_pem))
        cipher = PKCS1_v1_5.new(key)
        enc_pw = b64encode(cipher.encrypt(SRT_PW.encode())).decode()

        # 로그인
        data = {
            "srchDvNm": SRT_ID,
            "hmpgPwdCphd": enc_pw,
            "srchDvCd": "2",   # 회원번호
            "loginRememberYn": "N",
        }
        r = s.post(f"{BASE}/cmc/01/selectLoginInfo.do", data=data)
        resp = r.json()
        if resp.get("strResult") != "SUCC":
            raise RuntimeError(f"SRT 로그인 실패: {resp.get('MSG', '')}")

        self._session = s
        return s

    def reserve(self, train_info: TrainInfo, seat_type: str = "general") -> dict:
        s = self._ensure_login()
        dep_code = SRT_STATION_CODES.get(train_info.dep_station, "")
        arr_code = SRT_STATION_CODES.get(train_info.arr_station, "")
        train_no = train_info.train_no.split()[-1]  # "SRT 123" → "123"

        data = {
            "dptRsStnCd": dep_code,
            "arvRsStnCd": arr_code,
            "dptDt": train_info.date,
            "dptTm": train_info.dep_time.replace(":", ""),
            "trnNo": train_no,
            "psrmClCd": "2" if seat_type == "special" else "1",
            "psgNum": "1",
        }
        try:
            r = s.post(f"{BASE}/tmc/01/selectSeatReservationInfo.do", data=data)
            resp = r.json()
            if resp.get("strResult") != "SUCC":
                return {"success": False, "error": resp.get("MSG", "예약 실패")}
            rsv = resp.get("reservListMap", [{}])[0]
            return {
                "success": True,
                "rsv_no": rsv.get("pnrNo", ""),
                "total_price": rsv.get("rcvdAmt", "?"),
                "pay_limit_time": rsv.get("iseLmtDt", "") + " " + rsv.get("iseLmtTm", ""),
            }
        except Exception as e:
            log.warning("SRT reserve failed: %s", e)
            return {"success": False, "error": str(e)}

    def pay(self, rsv_no: str) -> dict:
        s = self._ensure_login()
        try:
            # 예약 목록에서 해당 예약 확인
            r = s.post(f"{BASE}/tmc/01/selectReservationList.do", data={"pageIndex": "1"})
            reservations = r.json().get("reservListMap", [])
            target = next((x for x in reservations if x.get("pnrNo") == rsv_no), None)
            if not target:
                return {"success": False, "error": "예약을 찾을 수 없습니다."}

            data = {
                "pnrNo": rsv_no,
                "stlbTrnClsfCd": target.get("stlbTrnClsfCd", "17"),
                "dptDt": target.get("dptDt", ""),
                "dptTm": target.get("dptTm", ""),
                "arvTm": target.get("arvTm", ""),
                "dptRsStnNm": target.get("dptRsStnNm", ""),
                "arvRsStnNm": target.get("arvRsStnNm", ""),
                "totPrnb": "1",
                "cardNo": SRT_CARD_NUMBER,
                "cardExpireDt": SRT_CARD_EXPIRY,
                "birthDt": SRT_CARD_BIRTH,
            }
            r = s.post(f"{BASE}/tmc/01/selectPaymentInfo.do", data=data)
            resp = r.json()
            if resp.get("strResult") != "SUCC":
                return {"success": False, "error": resp.get("MSG", "결제 실패")}
            return {"success": True}
        except Exception as e:
            log.warning("SRT pay failed: %s", e)
            return {"success": False, "error": str(e)}
