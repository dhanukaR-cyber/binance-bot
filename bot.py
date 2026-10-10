import re
import math
import io
import os
import datetime
import asyncio
from PIL import Image, ImageDraw, ImageFont
import pytesseract
from telethon import TelegramClient, events
from binance.client import Client

# Termux/Cloud Tesseract Path Handler (Render/Cloud වලදී Error නොවීමට සකසා ඇත)
try:
    termux_tesseract = '/data/data/com.termux/files/usr/bin/tesseract'
    if os.path.exists(termux_tesseract):
        pytesseract.pytesseract.tesseract_cmd = termux_tesseract
    else:
        # Cloud සර්වර් සඳහා Default path එක බැලීම
        pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
except Exception:
    pass

# 1. TELEGRAM API DETAILS
API_ID = 30864992
API_HASH = 'e7f7f96e78dbe7ae1c705adc7ebe43f1'

# 2. BINANCE DEMO API DETAILS
BINANCE_API_KEY = 'xRteorAHsUkMMruIckEW2EN0SsUIQyMfp3fU8wgdggTtkx9LjDsW8WhlrhoxPXn1'
BINANCE_API_SECRET = 'YKMXR9yNOzeZkNpranCjjUCXtnUDkpOB0bmsOpMdMGFlOcp0DG93a4eC9T0Nta9u'

# 3. INITIALIZE CLIENTS (Cloud එකේ Lock නොවීමට Render session නම පාවිච්චි කරයි)
telegram_client = TelegramClient('render_bot_session', API_ID, API_HASH)
binance_client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

async def send_telegram_msg(message, file_path=None):
    try:
        if file_path and os.path.exists(file_path):
            await telegram_client.send_file(
                'me',
                file=file_path,
                caption=message,
                force_document=False
            )
        else:
            await telegram_client.send_message('me', message)
    except Exception as e:
        print(f"[ERROR Sending Telegram Msg]: {e}")

def get_symbol_precisions_and_limits(symbol, leverage):
    info = binance_client.futures_exchange_info()
    price_precision = 2
    qty_precision = 3
    max_qty = 1000000.0
    min_qty = 0.001

    for s in info.get('symbols', []):
        if s['symbol'] == symbol:
            price_precision = s.get('pricePrecision', 2)
            qty_precision = s.get('quantityPrecision', 3)
            for f in s.get('filters', []):
                if f['filterType'] == 'LOT_SIZE':
                    max_qty = float(f.get('maxQty', 1000000.0))
                    min_qty = float(f.get('minQty', 0.001))
            break

    max_notional = 1000000.0
    try:
        brackets = binance_client.futures_leverage_bracket(symbol=symbol)
        for b in brackets:
            if b.get('symbol') == symbol:
                for bracket in b.get('brackets', []):
                    if bracket.get('initialLeverage', 1) >= leverage:
                        max_notional = float(bracket.get('notionalCap', 1000000.0))
                        break
                break
    except Exception as e:
        print(f"[WARNING Fetching Leverage Bracket]: {e}")

    return price_precision, qty_precision, max_qty, min_qty, max_notional

def round_step(val, precision):
    return round(val, precision)

def create_profit_card(symbol, side, leverage, roi_pct, entry_price, close_price):
    try:
        width, height = 750, 950
        bg_color = (12, 12, 12)
        card = Image.new('RGB', (width, height), color=bg_color)
        draw = ImageDraw.Draw(card)

        font_paths = [
            "/system/fonts/Roboto-Bold.ttf",
            "/system/fonts/DroidSans-Bold.ttf",
            "/system/fonts/Roboto-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ]
        loaded_font = None
        for path in font_paths:
            if os.path.exists(path):
                loaded_font = path
                break

        try:
            if loaded_font:
                font_brand = ImageFont.truetype(loaded_font, 28)
                font_symbol = ImageFont.truetype(loaded_font, 46)
                font_sub = ImageFont.truetype(loaded_font, 28)
                font_roi = ImageFont.truetype(loaded_font, 80)
                font_label = ImageFont.truetype(loaded_font, 26)
                font_val = ImageFont.truetype(loaded_font, 34)
            else:
                font_brand = ImageFont.load_default(size=28)
                font_symbol = ImageFont.load_default(size=46)
                font_sub = ImageFont.load_default(size=28)
                font_roi = ImageFont.load_default(size=80)
                font_label = ImageFont.load_default(size=26)
                font_val = ImageFont.load_default(size=34)
        except Exception:
            font_brand = font_symbol = font_sub = font_roi = font_label = font_val = ImageFont.load_default()

        draw.text((50, 50), "UNIVERSAL PLUS OFFICIAL", fill=(255, 255, 255), font=font_brand)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((50, 90), now_str, fill=(120, 120, 120), font=font_label)

        clean_symbol = symbol if symbol.endswith('USDT') else f"{symbol}USDT"
        draw.text((50, 320), f"{clean_symbol} Perpetual", fill=(255, 255, 255), font=font_symbol)

        side_formatted = "Long" if side in ['LONG', 'BUY'] else "Short"
        side_color = (14, 203, 129) if side_formatted == "Long" else (246, 70, 93)
        draw.text((50, 380), f"{side_formatted}  |  {leverage}x", fill=side_color, font=font_sub)

        roi_color = (14, 203, 129) if roi_pct >= 0 else (246, 70, 93)
        roi_str = f"+{roi_pct:.2f}%" if roi_pct >= 0 else f"{roi_pct:.2f}%"
        draw.text((50, 460), roi_str, fill=roi_color, font=font_roi)

        draw.text((50, 600), "Entry Price", fill=(132, 142, 156), font=font_label)
        draw.text((50, 640), f"{entry_price:.6f}".rstrip('0').rstrip('.'), fill=(255, 255, 255), font=font_val)

        draw.text((420, 600), "Last Price", fill=(132, 142, 156), font=font_label)
        draw.text((420, 640), f"{close_price:.6f}".rstrip('0').rstrip('.'), fill=(255, 255, 255), font=font_val)

        draw.line([(50, 830), (700, 830)], fill=(40, 40, 40), width=2)
        draw.text((50, 850), "BINANCE FUTURES", fill=(255, 255, 255), font=font_brand)

        file_path = f"card_{clean_symbol}.png"
        card.save(file_path, "PNG")
        return file_path
    except Exception as img_err:
        print(f"[CARD CREATION ERROR]: {img_err}")
        return None

def extract_coin_from_text(text):
    if not text:
        return None
    perp_match = re.search(r'([A-Za-z0-9]+)\s*Perpetual', text, re.IGNORECASE)
    if perp_match:
        c = perp_match.group(1).upper()
        return c if c.endswith('USDT') else f"{c}USDT"

    coin_match = re.search(r'(?:COIN\s*:\s*#?|#)\b([A-Za-z0-9]+)\b', text, re.IGNORECASE)
    if coin_match:
        c = coin_match.group(1).upper()
        ignored = ['CLOSE', 'EXIT', 'CANCEL', 'BOOK', 'NOW', 'PROFIT', 'FULL', 'TRADE', 'GUYZ', 'THE', 'ALL', 'USDT', 'PERPETUAL', 'SHORT', 'LONG', 'BUY', 'SELL']
        if c not in ignored:
            return c if c.endswith('USDT') else f"{c}USDT"
    return None

def run_ocr_sync(image_bytes):
    try:
        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image)
    except Exception:
        return ""

async def get_ocr_text_async(image_bytes):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, run_ocr_sync, image_bytes)

async def close_single_position(symbol):
    try:
        binance_client.futures_cancel_all_open_orders(symbol=symbol)
        positions = binance_client.futures_position_information(symbol=symbol)
        pos_amt, entry_p, unrealized_pnl, lev = 0.0, 0.0, 0.0, 20
        for p in positions:
            if float(p.get('positionAmt', 0)) != 0:
                pos_amt = float(p.get('positionAmt', 0))
                entry_p = float(p.get('entryPrice', 0))
                unrealized_pnl = float(p.get('unRealizedProfit', 0))
                lev = int(p.get('leverage', 20))
                break

        if pos_amt != 0:
            close_side = 'SELL' if pos_amt > 0 else 'BUY'
            ticker = binance_client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker.get('price', entry_p))

            binance_client.futures_create_order(
                symbol=symbol, side=close_side, type='MARKET',
                quantity=abs(pos_amt), reduceOnly=True
            )

            initial_margin = (abs(pos_amt) * entry_p) / lev if lev > 0 else 1
            roi_pct = (unrealized_pnl / initial_margin) * 100 if initial_margin > 0 else 0
            side_str = 'LONG' if pos_amt > 0 else 'SHORT'

            card_file = create_profit_card(symbol, side_str, lev, roi_pct, entry_p, current_price)
            await send_telegram_msg(
                f"🛑 **CLOSED TRADE FOR #{symbol}**\n💵 **PnL:** ${unrealized_pnl:.2f} USDT ({roi_pct:.2f}%)",
                file_path=card_file
            )

            if card_file and os.path.exists(card_file):
                try:
                    os.remove(card_file)
                except Exception:
                    pass
            return True
        else:
            await send_telegram_msg(f"🛑 **CANCELLED ALL OPEN ORDERS FOR #{symbol}**")
            return True
    except Exception as e:
        print(f"[ERROR Closing Single Position {symbol}]: {e}")
        return False

async def monitor_and_move_sl(symbol, side, entry_price, price_prec):
    close_side = 'SELL' if side == 'BUY' else 'BUY'
    print(f"[*] Started monitoring TP1 for #{symbol} to move SL to entry price...")

    while True:
        try:
            positions = binance_client.futures_position_information(symbol=symbol)
            pos_amt = 0.0
            for p in positions:
                if float(p.get('positionAmt', 0)) != 0:
                    pos_amt = float(p.get('positionAmt', 0))
                    break

            if pos_amt == 0:
                print(f"[*] Position for #{symbol} closed. Stopping TP1 monitor.")
                break

            open_orders = binance_client.futures_get_open_orders(symbol=symbol)
            tp_orders_exist = any(o['type'] == 'TAKE_PROFIT_MARKET' for o in open_orders)

            if not tp_orders_exist:
                print(f"[!] TP1 Hit detected for #{symbol}! Moving SL to Entry Price (${entry_price})...")

                for o in open_orders:
                    if o['type'] == 'STOP_MARKET':
                        binance_client.futures_cancel_order(symbol=symbol, orderId=o['orderId'])

                binance_client.futures_create_order(
                    symbol=symbol, side=close_side, type='STOP_MARKET',
                    stopPrice=entry_price, quantity=abs(pos_amt), priceProtect=True
                )

                await send_telegram_msg(f"🛡️ **TP1 HIT! SL MOVED TO ENTRY PRICE** for #{symbol} at `${entry_price}`")
                break

        except Exception as e:
            print(f"[ERROR in monitor_and_move_sl for {symbol}]: {e}")

        await asyncio.sleep(10)

@telegram_client.on(events.NewMessage)
async def main(event):
    raw_text = event.message.text or event.message.caption or ""; import unicodedata; raw_text = unicodedata.normalize("NFKD", raw_text).replace("200b", "").replace("200c", "").replace("200d", "").replace("Feff", "")

    # ==========================================
    # TELEGRAM COMMANDS HANDLER
    # ==========================================
    cmd = raw_text.strip().lower()

    if cmd == '/balance':
        try:
            account_info = binance_client.futures_account()
            total_bal = float(account_info.get('totalWalletBalance', 0))
            avail_bal = float(account_info.get('availableBalance', 0))
            unrealized_pnl = float(account_info.get('totalUnrealizedProfit', 0))

            msg = (
                f"💰 **BINANCE ACCOUNT BALANCE** 💰\n\n"
                f"💼 **Total Wallet Balance:** `${total_bal:.2f} USDT`\n"
                f"💵 **Available Balance:** `${avail_bal:.2f} USDT`\n"
                f"📊 **Unrealized PnL:** `${unrealized_pnl:.2f} USDT`"
            )
            await send_telegram_msg(msg)
        except Exception as e:
            await send_telegram_msg(f"❌ Error fetching balance: {e}")
        return

    elif cmd == '/status':
        try:
            all_positions = binance_client.futures_position_information()
            active_pos = [p for p in all_positions if float(p.get('positionAmt', 0)) != 0]
            open_orders = binance_client.futures_get_open_orders()

            msg = f"📊 **BOT STATUS REPORT** 📊\n\n"
            msg += f"🟢 **Active Positions:** {len(active_pos)}\n"
            for p in active_pos:
                sym = p['symbol']
                amt = float(p['positionAmt'])
                side = "LONG" if amt > 0 else "SHORT"
                entry = float(p['entryPrice'])
                pnl = float(p['unRealizedProfit'])
                lev = p['leverage']
                msg += f"• #{sym} | {side} | {lev}x | Entry: ${entry} \vert{} PnL:${pnl:.2f}\n"

            msg += f"\n⏳ **Total Open Orders (TP/SL/Limits):** {len(open_orders)}"
            await send_telegram_msg(msg)
        except Exception as e:
            await send_telegram_msg(f"❌ Error fetching status: {e}")
        return

    elif cmd == '/pnl':
        try:
            all_positions = binance_client.futures_position_information()
            active_pos = [p for p in all_positions if float(p.get('positionAmt', 0)) != 0]

            if not active_pos:
                await send_telegram_msg("📉 No active positions found right now.")
                return

            msg = f"📈 **LIVE PNL REPORT** 📈\n\n"
            total_pnl = 0.0
            for p in active_pos:
                sym = p['symbol']
                pnl = float(p['unRealizedProfit'])
                entry = float(p['entryPrice'])
                amt = float(p['positionAmt'])
                lev = int(p['leverage'])
                total_pnl += pnl

                initial_margin = (abs(amt) * entry) / lev if lev > 0 else 1
                roi_pct = (pnl / initial_margin) * 100 if initial_margin > 0 else 0

                msg += f"• #{sym}: **${pnl:.2f} USDT** ({roi_pct:+.2f}%)\n"

            msg += f"\n💵 **Total Unrealized PnL:** `${total_pnl:.2f} USDT`"
            await send_telegram_msg(msg)
        except Exception as e:
            await send_telegram_msg(f"❌ Error fetching PnL: {e}")
        return

    elif cmd == '/help':
        help_msg = (
            "🤖 **BOT COMMANDS LIST** 🤖\n\n"
            "• `/balance` - View account wallet & available balance\n"
            "• `/status` - View active positions & open orders\n"
            "• `/pnl` - View live profit and loss (PnL %)\n"
            "• `/help` - Show this help message"
        )
        await send_telegram_msg(help_msg)
        return

    # ==========================================
    # OCR & SIGNAL PROCESSING
    # ==========================================
    image_ocr_text = ""
    if event.message.media:
        try:
            photo_bytes = await event.message.download_media(file=bytes)
            image_ocr_text = await get_ocr_text_async(photo_bytes)
        except Exception as ocr_err:
            print(f"[OCR READ FAILED]: {ocr_err}")

    combined_text = f"{raw_text}\n{image_ocr_text}".strip()

    # 1. SMART CLOSE / EXIT SIGNAL LOGIC
    close_keywords = ['CLOSE', 'EXIT', 'ක්ලෝස්', 'අයින්', 'වහන්න', 'BOOK PROFIT']
    is_close_signal = any(k in combined_text.upper() for k in close_keywords) and 'STOP LOSS' not in combined_text.upper()

    if is_close_signal:
        print(f"\n[CLOSE SIGNAL DETECTED]\nContent: {combined_text}")
        found_coin = extract_coin_from_text(combined_text)

        if not found_coin and event.message.is_reply:
            reply_msg = await event.message.get_reply_message()
            if reply_msg:
                r_text = reply_msg.text or reply_msg.caption or ""
                if reply_msg.media:
                    try:
                        r_bytes = await reply_msg.download_media(file=bytes)
                        r_ocr = await get_ocr_text_async(r_bytes)
                        r_text += f"\n{r_ocr}"
                    except Exception:
                        pass
                found_coin = extract_coin_from_text(r_text)

        try:
            all_positions = binance_client.futures_position_information()
            active_positions = [p['symbol'] for p in all_positions if float(p.get('positionAmt', 0)) != 0]

            if found_coin:
                await close_single_position(found_coin)
                return
            if len(active_positions) == 1:
                await close_single_position(active_positions[0])
                return
            if len(active_positions) > 1:
                matched = False
                for active_symbol in active_positions:
                    base_coin = active_symbol.replace('USDT', '')
                    if re.search(r'\b' + re.escape(base_coin) + r'\b', combined_text, re.IGNORECASE):
                        await close_single_position(active_symbol)
                        matched = True
                        break
                if matched:
                    return
        except Exception as e:
            print(f"[ERROR Checking Active Positions]: {e}")

        try:
            open_orders = binance_client.futures_get_open_orders()
            for order in open_orders:
                binance_client.futures_cancel_all_open_orders(symbol=order['symbol'])

            all_positions = binance_client.futures_position_information()
            closed_any = False
            for pos in all_positions:
                pos_amt = float(pos.get('positionAmt', 0))
                sym = pos.get('symbol')
                if pos_amt != 0:
                    await close_single_position(sym)
                    closed_any = True

            if not closed_any:
                await send_telegram_msg("🛑 **ALL OPEN ORDERS CANCELLED & NO ACTIVE POSITIONS FOUND.**")
        except Exception as e:
            print(f"[ERROR Closing All Trades]: {e}")
        return

    # 2. NEW ENTRY SIGNAL LOGIC
    if 'COIN' in combined_text or 'BUY' in combined_text or 'SELL' in combined_text or 'LONG' in combined_text or 'SHORT' in combined_text:
        print(f"\n[NEW SIGNAL RECEIVED]\n{combined_text}")

        try:
            coin_match = re.search(r'COIN\s*:\s*#?([A-Z0-9]+)', combined_text, re.IGNORECASE)
            side_match = re.search(r'(BUY|SELL|LONG|SHORT)', combined_text, re.IGNORECASE)
            leverage_match = re.search(r'LEVERAGE\s*:\s*(\d+)X', combined_text, re.IGNORECASE)
            entry_match = re.search(r'(?:ENTRY|PRICE)\s*:\s*([0-9.]+)', combined_text, re.IGNORECASE)
            sl_match = re.search(r'(?:SL|STOP\s*LOSS)\s*:\s*([0-9.]+)', combined_text, re.IGNORECASE)
            tp_matches = re.findall(r'(?:TP\d*|\d+️⃣|\d+\))\s*:?\s*([0-9.]+)%', combined_text, re.IGNORECASE)

            has_moon = bool(re.search(r'MOON', combined_text, re.IGNORECASE))

            if coin_match and side_match:
                symbol = coin_match.group(1).upper()
                if not symbol.endswith('USDT'):
                    symbol += 'USDT'

                raw_side = side_match.group(1).upper()
                side = 'BUY' if raw_side in ['BUY', 'LONG'] else 'SELL'
                close_side = 'SELL' if side == 'BUY' else 'BUY'

                leverage = int(leverage_match.group(1)) if leverage_match else 20
                price_prec, qty_prec, max_qty, min_qty_limit, max_notional = get_symbol_precisions_and_limits(symbol, leverage)

                try:
                    binance_client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
                except Exception:
                    pass

                try:
                    binance_client.futures_change_leverage(symbol=symbol, leverage=leverage)
                except Exception as e:
                    print(f"[WARNING Setting Leverage]: {e}")

                account_info = binance_client.futures_account()
                available_balance = float(account_info.get('availableBalance', 0))
                ticker = binance_client.futures_symbol_ticker(symbol=symbol)
                current_market_price = float(ticker.get('price', 0))

                is_limit_order = False
                if entry_match:
                    limit_entry_price = round_step(float(entry_match.group(1)), price_prec)
                    entry_price = limit_entry_price
                    is_limit_order = True
                else:
                    entry_price = current_market_price

                # Wallet balance එකෙන් 5%ක් (අවශ්‍ය නම් 0.10 මඟින් 10% කළ හැක)
                margin_to_use = available_balance * 0.05
                position_val = margin_to_use * leverage

                if position_val > max_notional:
                    position_val = max_notional * 0.95

                raw_qty = position_val / entry_price if entry_price > 0 else 0
                total_quantity = round_step(raw_qty, qty_prec)

                if total_quantity > max_qty:
                    total_quantity = max_qty

                min_qty = max(min_qty_limit, round_step(10 ** (-qty_prec), qty_prec))
                if total_quantity < min_qty:
                    total_quantity = min_qty

                if is_limit_order:
                    binance_client.futures_create_order(
                        symbol=symbol, side=side, type='LIMIT',
                        timeInForce='GTC', price=entry_price, quantity=total_quantity
                    )
                    init_msg = (
                        f"⏳ **NEW LIMIT ORDER PLACED** ⏳\n\n"
                        f"🪙 **Coin:** #{symbol}\n"
                        f"📊 **Side:** {side}\n"
                        f"⚡ **Leverage:** {leverage}x\n"
                        f"🎯 **Limit Price:** ${entry_price}\n"
                        f"📦 **Quantity:** {total_quantity}"
                    )
                else:
                    binance_client.futures_create_order(
                        symbol=symbol, side=side, type='MARKET', quantity=total_quantity
                    )
                    init_msg = (
                        f"🚀 **NEW MARKET TRADE OPENED** 🚀\n\n"
                        f"🪙 **Coin:** #{symbol}\n"
                        f"📊 **Side:** {side}\n"
                        f"⚡ **Leverage:** {leverage}x\n"
                        f"💵 **Entry Price:** ${entry_price}\n"
                        f"📦 **Quantity:** {total_quantity}"
                    )

                await send_telegram_msg(init_msg)

                if tp_matches:
                    tp_percentages = [float(tp) for tp in tp_matches]
                else:
                    tp_percentages = [100.0, 150.0, 200.0]

                calculated_tps = []
                for tp_pct in tp_percentages:
                    p_factor = (tp_pct / leverage) / 100
                    if side == 'BUY':
                        target_p = round_step(entry_price * (1 + p_factor), price_prec)
                    else:
                        target_p = round_step(entry_price * (1 - p_factor), price_prec)
                    calculated_tps.append((tp_pct, target_p))

                total_parts = len(calculated_tps) + 1 if has_moon else len(calculated_tps)
                split_qty = round_step(total_quantity / total_parts, qty_prec)
                if split_qty < min_qty:
                    split_qty = min_qty

                tp_summary_str = ""
                for i, (pct, tp_price) in enumerate(calculated_tps, 1):
                    try:
                        binance_client.futures_create_order(
                            symbol=symbol, side=close_side, type='TAKE_PROFIT_MARKET',
                            stopPrice=tp_price, quantity=split_qty, priceProtect=True
                        )
                        tp_summary_str += f"🎯 **TP{i} ({pct}%):** ${tp_price}\n"
                    except Exception as e:
                        print(f"[ERROR placing TP{i}]: {e}")

                if has_moon:
                    tp_summary_str += f"🚀 **Moon Slot:** {split_qty} Qty (No TP - Ride until Admin Close)\n"

                if sl_match:
                    sl_price = round_step(float(sl_match.group(1)), price_prec)
                else:
                    p_100 = (100 / leverage) / 100
                    sl_price = round_step(entry_price * (1 - p_100), price_prec) if side == 'BUY' else round_step(entry_price * (1 + p_100), price_prec)

                try:
                    binance_client.futures_create_order(
                        symbol=symbol, side=close_side, type='STOP_MARKET',
                        stopPrice=sl_price, quantity=total_quantity, priceProtect=True
                    )
                except Exception as e:
                    print(f"[ERROR placing SL]: {e}")

                orders_msg = (
                    f"✅ **ORDERS PLACED FOR #{symbol}**\n\n"
                    f"{tp_summary_str}"
                    f"🛑 **Stop Loss:** ${sl_price}"
                )
                await send_telegram_msg(orders_msg)


        except Exception as e:
            err_msg = f"❌ **Signal Failed:** {e}"
            await send_telegram_msg(err_msg)

# ==========================================
# ALWAYS-ON RECONNECTION LOOP
# ==========================================
async def main_loop():
    while True:
        try:
            print("[*] Telegram Client එක Start කරමින් පවතී...")
            await telegram_client.start()
            print("[*] Bot එක සාර්ථකව සක්‍රීය විය! Signal සහ Commands සඳහා බලාගෙන සිටියි...")
            await telegram_client.run_until_disconnected()
        except Exception as e:
            print(f"[NETWORK ERROR / DISCONNECTED]: {e}")
            print("[*] Network නැත. තත්පර 5කින් නැවත reconnect වීමට උත්සාහ කරයි...")
            await asyncio.sleep(5)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_loop())
