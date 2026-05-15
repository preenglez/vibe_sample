"""취소표 모니터링 - 백그라운드에서 주기적으로 빈 자리를 확인하고 자동 예약."""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable, Awaitable
import public_search

log = logging.getLogger(__name__)


@dataclass
class WatchItem:
    user_id: int
    service: str        # "KTX" | "SRT"
    dep: str
    arr: str
    date: str           # YYYYMMDD
    time: str           # HHMMSS
    seat_type: str      # "general" | "special"
    train_nos: list[str] = field(default_factory=list)  # 빈 리스트 = 모든 열차
    on_reserve: Callable[..., Awaitable] = field(repr=False, default=None)
    active: bool = True


class Watchlist:
    def __init__(self, interval: int = 30):
        self._items: list[WatchItem] = []
        self._interval = interval
        self._task: asyncio.Task | None = None
        self._korail = None
        self._srt = None

    def set_clients(self, korail, srt):
        self._korail = korail
        self._srt = srt

    def add(self, item: WatchItem):
        self._items.append(item)
        log.info("Watchlist added: %s %s→%s %s", item.service, item.dep, item.arr, item.date)

    def remove(self, user_id: int, service: str, dep: str, arr: str, date: str):
        before = len(self._items)
        self._items = [
            i for i in self._items
            if not (i.user_id == user_id and i.service == service
                    and i.dep == dep and i.arr == arr and i.date == date)
        ]
        return len(self._items) < before

    def list_for_user(self, user_id: int) -> list[WatchItem]:
        return [i for i in self._items if i.user_id == user_id and i.active]

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    def stop(self):
        if self._task:
            self._task.cancel()

    async def _loop(self):
        while True:
            await asyncio.sleep(self._interval)
            active = [i for i in self._items if i.active]
            for item in active:
                try:
                    await self._check(item)
                except Exception as e:
                    log.exception("Watch check error: %s", e)

    async def _check(self, item: WatchItem):
        # 조회는 공개 API (로그인 불필요)
        search_fn = public_search.search_korail if item.service == "KTX" else public_search.search_srt
        reserve_client = self._korail if item.service == "KTX" else self._srt
        if reserve_client is None:
            return

        trains = await asyncio.get_event_loop().run_in_executor(
            None, search_fn, item.dep, item.arr, item.date, item.time
        )

        for t in trains:
            if item.train_nos and t.train_no not in item.train_nos:
                continue
            available = t.has_general if item.seat_type == "general" else t.has_special
            if not available:
                continue

            log.info("Seat found! %s %s %s→%s", item.service, t.train_no, item.dep, item.arr)
            item.active = False  # 중복 예약 방지

            result = await asyncio.get_event_loop().run_in_executor(
                None, reserve_client.reserve, t, item.seat_type
            )

            if item.on_reserve:
                await item.on_reserve(item, t, result)
            break
