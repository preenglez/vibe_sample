"""KTX/SRT 텔레그램 예약 봇"""
import logging
import asyncio
from datetime import datetime, timedelta
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters,
)
from config import (
    TELEGRAM_BOT_TOKEN, ALLOWED_USER_IDS, WATCH_INTERVAL,
    KORAIL_ID, KORAIL_PW, SRT_ID, SRT_PW, KORAIL_STATIONS, SRT_STATIONS,
)
from korail_client import KorailClient
from srt_client import SRTClient
from watchlist import Watchlist, WatchItem
import public_search

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# --- 대화 상태 ---
(
    S_SERVICE, S_DEP, S_ARR, S_DATE, S_TIME,
    S_TRAINS, S_SEAT_TYPE, S_CONFIRM, S_PAY,
) = range(9)

korail = KorailClient() if KORAIL_ID else None
srt = SRTClient() if SRT_ID else None
watchlist = Watchlist(interval=WATCH_INTERVAL)
watchlist.set_clients(korail, srt)


def auth_required(func):
    @wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if ALLOWED_USER_IDS and uid not in ALLOWED_USER_IDS:
            await update.effective_message.reply_text("접근 권한이 없습니다.")
            return ConversationHandler.END
        return await func(update, ctx)
    return wrapper


def kb(buttons: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text, callback_data=data) for text, data in row]
        for row in buttons
    ])


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ────────────────────────────── /start ──────────────────────────────

@auth_required
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    rows = []
    if korail:
        rows.append([("🚄 KTX (Korail)", "KTX")])
    if srt:
        rows.append([("🚅 SRT", "SRT")])
    if not rows:
        await update.message.reply_text("❌ 로그인 정보가 설정되지 않았습니다. .env를 확인하세요.")
        return ConversationHandler.END
    await update.message.reply_text("어떤 열차를 예약할까요?", reply_markup=kb(rows))
    return S_SERVICE


@auth_required
async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.effective_message.reply_text("예약 과정을 취소했습니다. /start 로 다시 시작하세요.")
    return ConversationHandler.END


@auth_required
async def cmd_watchlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    items = watchlist.list_for_user(uid)
    if not items:
        await update.message.reply_text("현재 감시 중인 열차가 없습니다.")
        return
    lines = []
    for i, w in enumerate(items, 1):
        date_str = f"{w.date[:4]}-{w.date[4:6]}-{w.date[6:]}"
        lines.append(f"{i}. [{w.service}] {w.dep}→{w.arr} {date_str} ({w.seat_type})")
    await update.message.reply_text("🔍 감시 목록:\n" + "\n".join(lines))


# ────────────────────────────── 서비스 선택 ──────────────────────────────

async def cb_service(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    service = q.data  # "KTX" | "SRT"
    ctx.user_data["service"] = service
    stations = KORAIL_STATIONS if service == "KTX" else SRT_STATIONS
    ctx.user_data["stations"] = stations
    rows = list(chunk([(s, s) for s in stations], 3))
    await q.edit_message_text(f"[{service}] 출발역을 선택하세요:", reply_markup=kb(rows))
    return S_DEP


# ────────────────────────────── 출발역 ──────────────────────────────

async def cb_dep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data["dep"] = q.data
    stations = [s for s in ctx.user_data["stations"] if s != q.data]
    rows = list(chunk([(s, s) for s in stations], 3))
    await q.edit_message_text(f"도착역을 선택하세요 (출발: {q.data}):", reply_markup=kb(rows))
    return S_ARR


# ────────────────────────────── 도착역 ──────────────────────────────

async def cb_arr(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data["arr"] = q.data

    today = datetime.now()
    dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(14)]
    date_data = [(today + timedelta(days=i)).strftime("%Y%m%d") for i in range(14)]
    rows = list(chunk(list(zip(dates, date_data)), 2))
    await q.edit_message_text(
        f"날짜를 선택하세요 ({ctx.user_data['dep']}→{ctx.user_data['arr']}):",
        reply_markup=kb(rows),
    )
    return S_DATE


# ────────────────────────────── 날짜 ──────────────────────────────

async def cb_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data["date"] = q.data  # YYYYMMDD
    hours = [f"{h:02d}:00" for h in range(0, 24, 2)]
    hour_data = [f"{h:02d}0000" for h in range(0, 24, 2)]
    rows = list(chunk(list(zip(hours, hour_data)), 4))
    date_disp = f"{q.data[:4]}-{q.data[4:6]}-{q.data[6:]}"
    await q.edit_message_text(
        f"출발 시간대를 선택하세요 ({date_disp}):",
        reply_markup=kb(rows),
    )
    return S_TIME


# ────────────────────────────── 시간 & 열차 조회 ──────────────────────────────

async def cb_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data["time"] = q.data  # HHMMSS

    svc = ctx.user_data["service"]
    dep = ctx.user_data["dep"]
    arr = ctx.user_data["arr"]
    date = ctx.user_data["date"]
    time = ctx.user_data["time"]

    await q.edit_message_text("🔍 열차를 조회하는 중...")

    # 조회는 로그인 없이 공개 API 사용
    search_fn = public_search.search_korail if svc == "KTX" else public_search.search_srt
    try:
        trains = await asyncio.get_event_loop().run_in_executor(
            None, search_fn, dep, arr, date, time
        )
    except Exception as e:
        await q.edit_message_text(f"조회 실패: {e}\n/start 로 다시 시도하세요.")
        return ConversationHandler.END

    if not trains:
        await q.edit_message_text("해당 시간대에 열차가 없습니다. /start 로 다시 시도하세요.")
        return ConversationHandler.END

    ctx.user_data["trains"] = trains
    lines = []
    buttons = []
    for i, t in enumerate(trains):
        seat_icons = []
        if t.has_general:
            seat_icons.append("일반O")
        else:
            seat_icons.append("일반✗")
        if t.has_special:
            seat_icons.append("특실O")
        else:
            seat_icons.append("특실✗")
        label = f"{t.dep_time}→{t.arr_time} ({t.duration}) {' '.join(seat_icons)}"
        lines.append(f"{i+1}. {t.train_no} {label}")
        buttons.append((f"{i+1}번", str(i)))

    rows = list(chunk(buttons, 3))
    date_disp = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    msg = f"[{svc}] {dep}→{arr} {date_disp}\n\n" + "\n".join(lines) + "\n\n예약할 열차를 선택하세요:"
    await q.edit_message_text(msg, reply_markup=kb(rows))
    return S_TRAINS


# ────────────────────────────── 열차 선택 ──────────────────────────────

async def cb_train_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    idx = int(q.data)
    train = ctx.user_data["trains"][idx]
    ctx.user_data["selected_train"] = train

    rows = [
        [("🪑 일반실", "general"), ("💺 특실", "special")],
        [("👁 취소표 감시 (일반)", "watch_general"), ("👁 취소표 감시 (특실)", "watch_special")],
    ]
    t = train
    msg = (
        f"선택: {t.train_no}  {t.dep_station}→{t.arr_station}\n"
        f"출발: {t.dep_time}  도착: {t.arr_time}  소요: {t.duration}\n"
        f"일반: {'✅' if t.has_general else '❌'}  특실: {'✅' if t.has_special else '❌'}\n\n"
        "좌석 유형을 선택하거나 취소표 감시를 시작하세요:"
    )
    await q.edit_message_text(msg, reply_markup=kb(rows))
    return S_SEAT_TYPE


# ────────────────────────────── 좌석 유형 선택 / 감시 등록 ──────────────────────────────

async def cb_seat_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data  # "general" | "special" | "watch_general" | "watch_special"

    if data.startswith("watch_"):
        seat_type = data.split("_")[1]
        return await _start_watch(q, ctx, seat_type)

    ctx.user_data["seat_type"] = data
    train = ctx.user_data["selected_train"]
    svc = ctx.user_data["service"]

    # 예약 전 로그인 계정 확인
    has_credentials = (svc == "KTX" and korail) or (svc == "SRT" and srt)
    if not has_credentials:
        await q.edit_message_text(
            f"ℹ️ 열차 조회는 성공했으나 예약하려면 .env에 {svc} 계정 정보를 설정해야 합니다."
        )
        return ConversationHandler.END

    available = train.has_general if data == "general" else train.has_special
    if not available:
        await q.edit_message_text(
            f"❌ 해당 좌석이 매진입니다.\n취소표 감시를 원하시면 /start 후 '취소표 감시'를 선택하세요."
        )
        return ConversationHandler.END

    seat_label = "일반실" if data == "general" else "특실"
    t = train
    msg = (
        f"예약을 확인해 주세요:\n\n"
        f"열차: {t.train_no}\n"
        f"구간: {t.dep_station}→{t.arr_station}\n"
        f"날짜: {ctx.user_data['date'][:4]}-{ctx.user_data['date'][4:6]}-{ctx.user_data['date'][6:]}\n"
        f"출발: {t.dep_time}  도착: {t.arr_time}\n"
        f"좌석: {seat_label}\n\n"
        "예약하시겠습니까?"
    )
    await q.edit_message_text(msg, reply_markup=kb([[("✅ 예약", "yes"), ("❌ 취소", "no")]]))
    return S_CONFIRM


async def _start_watch(q, ctx, seat_type: str):
    uid = q.from_user.id
    train = ctx.user_data["selected_train"]
    item = WatchItem(
        user_id=uid,
        service=ctx.user_data["service"],
        dep=ctx.user_data["dep"],
        arr=ctx.user_data["arr"],
        date=ctx.user_data["date"],
        time=ctx.user_data["time"],
        seat_type=seat_type,
        train_nos=[train.train_no],
        on_reserve=_on_watch_reserved,
    )
    item._app = ctx.application
    watchlist.add(item)
    date_disp = f"{item.date[:4]}-{item.date[4:6]}-{item.date[6:]}"
    await q.edit_message_text(
        f"👁 취소표 감시 시작!\n"
        f"{item.service} {item.dep}→{item.arr} {date_disp}\n"
        f"열차: {train.train_no}  좌석: {seat_type}\n\n"
        f"빈 자리가 생기면 즉시 예약 후 알려드립니다.\n"
        f"/watchlist 로 감시 목록 확인, /cancel_watch 로 중단"
    )
    return ConversationHandler.END


async def _on_watch_reserved(item: WatchItem, train, result: dict):
    """감시 중 자리 발견 후 예약 완료 시 텔레그램 알림."""
    app = getattr(item, "_app", None)
    if app is None:
        return
    if result["success"]:
        msg = (
            f"🎉 예약 성공!\n"
            f"[{item.service}] {train.train_no} {train.dep_station}→{train.arr_station}\n"
            f"출발: {train.dep_time}\n"
            f"예약번호: {result.get('rsv_no', '?')}\n"
            f"총 금액: {result.get('total_price', '?')}원\n"
            f"결제 기한: {result.get('pay_limit_time', '?')}\n\n"
            f"결제하려면 /pay_{result.get('rsv_no', '')}_{item.service.lower()} 을 입력하세요."
        )
    else:
        msg = f"⚠️ 자리를 발견했지만 예약 실패: {result.get('error')}"
    await app.bot.send_message(chat_id=item.user_id, text=msg)


# ────────────────────────────── 예약 확인 ──────────────────────────────

async def cb_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "no":
        await q.edit_message_text("예약을 취소했습니다. /start 로 다시 시작하세요.")
        return ConversationHandler.END

    await q.edit_message_text("⏳ 예약 중...")
    svc = ctx.user_data["service"]
    train = ctx.user_data["selected_train"]
    seat_type = ctx.user_data["seat_type"]

    client = korail if svc == "KTX" else srt
    result = await asyncio.get_event_loop().run_in_executor(
        None, client.reserve, train, seat_type
    )

    if not result["success"]:
        await q.edit_message_text(
            f"❌ 예약 실패: {result['error']}\n/start 로 다시 시도하세요."
        )
        return ConversationHandler.END

    ctx.user_data["rsv_no"] = result["rsv_no"]
    ctx.user_data["rsv_service"] = svc.lower()
    msg = (
        f"✅ 예약 완료!\n"
        f"예약번호: {result['rsv_no']}\n"
        f"총 금액: {result.get('total_price', '?')}원\n"
        f"결제 기한: {result.get('pay_limit_time', '?')}\n\n"
        "지금 결제하시겠습니까?"
    )
    await q.edit_message_text(msg, reply_markup=kb([[("💳 결제", "pay"), ("나중에", "later")]]))
    return S_PAY


# ────────────────────────────── 결제 ──────────────────────────────

async def cb_pay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "later":
        rsv_no = ctx.user_data.get("rsv_no", "")
        svc = ctx.user_data.get("rsv_service", "")
        await q.edit_message_text(
            f"나중에 결제하려면:\n/pay_{rsv_no}_{svc}"
        )
        return ConversationHandler.END

    await q.edit_message_text("💳 결제 처리 중...")
    svc = ctx.user_data["rsv_service"]
    rsv_no = ctx.user_data["rsv_no"]

    client = korail if svc == "ktx" else srt
    result = await asyncio.get_event_loop().run_in_executor(None, client.pay, rsv_no)

    if result["success"]:
        await q.edit_message_text(f"🎉 결제 완료! 예약번호: {rsv_no}\n즐거운 여행 되세요!")
    else:
        await q.edit_message_text(f"❌ 결제 실패: {result['error']}")
    return ConversationHandler.END


# ────────────────────────────── /pay_<rsv>_<svc> ──────────────────────────────

@auth_required
async def cmd_pay(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.split("_")
    if len(parts) < 3:
        await update.message.reply_text("올바른 형식: /pay_예약번호_ktx 또는 /pay_예약번호_srt")
        return
    rsv_no = parts[1]
    svc = parts[2].lower()
    client = korail if svc == "ktx" else srt
    await update.message.reply_text("💳 결제 처리 중...")
    result = await asyncio.get_event_loop().run_in_executor(None, client.pay, rsv_no)
    if result["success"]:
        await update.message.reply_text(f"🎉 결제 완료! 예약번호: {rsv_no}")
    else:
        await update.message.reply_text(f"❌ 결제 실패: {result['error']}")


@auth_required
async def cmd_cancel_watch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "중단할 감시 항목을 /watchlist 에서 확인 후\n"
        "취소 기능은 추후 업데이트 예정입니다.\n"
        "긴급 시 봇을 재시작하세요."
    )


# ────────────────────────────── 메인 ──────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            S_SERVICE: [CallbackQueryHandler(cb_service, pattern="^(KTX|SRT)$")],
            S_DEP: [CallbackQueryHandler(cb_dep)],
            S_ARR: [CallbackQueryHandler(cb_arr)],
            S_DATE: [CallbackQueryHandler(cb_date)],
            S_TIME: [CallbackQueryHandler(cb_time)],
            S_TRAINS: [CallbackQueryHandler(cb_train_select)],
            S_SEAT_TYPE: [CallbackQueryHandler(cb_seat_type)],
            S_CONFIRM: [CallbackQueryHandler(cb_confirm)],
            S_PAY: [CallbackQueryHandler(cb_pay)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("cancel_watch", cmd_cancel_watch))
    app.add_handler(MessageHandler(filters.Regex(r"^/pay_"), cmd_pay))

    async def on_startup(application):
        watchlist.start()
        log.info("봇 시작됨")

    app.post_init = on_startup
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
