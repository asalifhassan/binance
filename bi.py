import requests
import time
import os
import logging
from datetime import datetime, timedelta
import json
import sys
import numpy as np
from collections import defaultdict
import concurrent.futures
from threading import Lock
import pandas as pd

# ইউনিকোড সাপোর্ট নিশ্চিত করা
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# লগিং সিস্টেম সেটআপ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('live_trading_bot.log', encoding='utf-8')
    ]
)

# এনভায়রনমেন্ট ভেরিয়েবল থেকে API কী লোড করা
API_KEY = os.getenv("BINANCE_API_KEY", "83Z1SiHNpUaViSMS5vCgiCS4DQJXYG9aMI0duTs3k3z68q3jiqOkITWbprrs3OlE")
headers = {"X-MBX-APIKEY": API_KEY}

# অপ্টিমাইজড রেট লিমিট ম্যানেজমেন্ট
last_request_time = 0
MIN_REQUEST_INTERVAL = 0.2  # 0.5 এর পরিবর্তে 0.2 সেকেন্ড
request_lock = Lock()

# নেটওয়ার্ক সমস্যা হ্যান্ডলিং
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=30,
    pool_maxsize=100,
    max_retries=3
)
session.mount('http://', adapter)
session.mount('https://', adapter)

# টপ কয়েন ব্ল্যাকলিস্ট
BLACKLISTED_COINS = [
    "BTCUSDC", "ETHUSDC", "BNBUSDC", 
    "SOLUSDC", "XRPUSDC", "ADAUSDC",
    "AVAXUSDC", "DOGEUSDC", "DOTUSDC", "MATICUSDC", "LINKUSDC", "UNIUSDC",
    "LTCUSDT", "BCHUSDT", "ATOMUSDT", "ETCUSDT"
]

# ট্রেডিং প্যারামিটার
INVESTMENT_AMOUNT = 100
LEVERAGE = 10
COOLDOWN_PERIOD = 15 * 60  # 15 মিনিট কুলডাউন
MIN_ACCURACY_THRESHOLD = 70  # ন্যূনতম 70% অ্যাকুরেসি
MAX_SYMBOLS_TO_SCAN = 200  # সর্বোচ্চ ২০০টি সিম্বল স্ক্যান করা হবে

# সিগন্যাল হিস্ট্রি ট্র্যাকিং
signal_history = {}
signal_performance = {}
market_regime = {}

def rate_limit():
    global last_request_time
    with request_lock:
        current_time = time.time()
        elapsed = current_time - last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        last_request_time = time.time()

def get_all_futures_symbols():
    """সব USDT পেয়ার ফিউচার্স সিম্বল পাওয়া"""
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        rate_limit()
        res = session.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        
        # সব USDT পেয়ার ফিউচার্স সিম্বল নির্বাচন
        symbols = []
        for s in data['symbols']:
            if (s['contractType'] == 'PERPETUAL' and 
                s['status'] == 'TRADING' and 
                s['symbol'] not in BLACKLISTED_COINS and
                'USDT' in s['symbol'] and
                s['quoteAsset'] == 'USDT'):
                symbols.append(s['symbol'])
        
        # সব সিম্বলের ২৪ ঘন্টার টিকার ডেটা পাওয়া
        rate_limit()
        ticker_url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
        ticker_res = session.get(ticker_url, headers=headers, timeout=10)
        ticker_data = ticker_res.json()
        
        # সিম্বল অনুযায়ী ভলিউম ম্যাপ করা
        symbol_volume_map = {}
        for ticker in ticker_data:
            symbol = ticker['symbol']
            if symbol in symbols:
                try:
                    volume = float(ticker['quoteVolume'])
                    symbol_volume_map[symbol] = volume
                except:
                    continue
        
        # ভলিউম অনুযায়ী সাজানো
        sorted_symbols = sorted(symbol_volume_map.items(), key=lambda x: x[1], reverse=True)
        
        # সর্বোচ্চ MAX_SYMBOLS_TO_SCAN সংখ্যক সিম্বল নেওয়া
        final_symbols = [s[0] for s in sorted_symbols[:MAX_SYMBOLS_TO_SCAN]]
        
        logging.info(f"Found {len(final_symbols)} symbols to scan (sorted by volume)")
        return final_symbols
        
    except Exception as e:
        logging.error(f"Error fetching symbols: {e}")
        # ফলব্যাক সিম্বল
        fallback_symbols = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", 
            "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT",
            "LINKUSDT", "UNIUSDT", "LTCUSDT", "BCHUSDT", "ATOMUSDT",
            "ETCUSDT", "XLMUSDT", "FTMUSDT", "NEARUSDT", "SANDUSDT",
            "MANAUSDT", "AXSUSDT", "AAVEUSDT", "ALGOUSDT", "COMPUSDT",
            "MKRUSDT", "YFIUSDT", "CRVUSDT", "SNXUSDT", "UNIUSDT",
            "SUSHIUSDT", "1INCHUSDT", "ENJUSDT", "CHZUSDT", "BATUSDT",
            "ZECUSDT", "DASHUSDT", "EOSUSDT", "TRXUSDT", "VETUSDT",
            "THETAUSDT", "XTZUSDT", "BSVUSDT", "BTTUSDT", "HOTUSDT",
            "IOTAUSDT", "XMRUSDT", "ETCUSDT", "ZRXUSDT", "BATUSDT",
            "ZILUSDT", "WAVESUSDT", "KNCUSDT", "REPUSDT", "RENUSDT",
            "KSMUSDT", "FILUSDT", "RUNEUSDT", "AKROUSDT", "ANTUSDT",
            "BANDUSDT", "CVCUSDT", "DNTUSDT", "KEYUSDT", "OCEANUSDT",
            "QNTUSDT", "SRMUSDT", "STORJUSDT", "TRBUSDT", "UMAUSDT",
            "YFIIUSDT", "ZENUSDT", "BADGERUSDT", "FARMUSDT", "KEEPUSDT",
            "NUUSDT", "PERPUSDT", "POLSUSDT", "RADUSDT", "RARIUSDT",
            "SXPUSDT", "SWRVUSDT", "TORNUSDT", "UNIUSDT", "XVSUSDT",
            "ALPHAUSDT", "ANKRUSDT", "BALUSDT", "BNTUSDT", "CELRUSDT",
            "CROUSDT", "CTSIUSDT", "DIAUSDT", "DOSEUSDT", "EGLDUSDT",
            "ELFUSDT", "FETUSDT", "GRTUSDT", "ICXUSDT", "IOSTUSDT",
            "IOTXUSDT", "KAVAUSDT", "LRCUSDT", "MATICUSDT", "MDTUSDT",
            "MKRUSDT", "MTLUSDT", "NKNUSDT", "OMGUSDT", "OXTUSDT",
            "REEFUSDT", "RLCUSDT", "RSRUSDT", "RVNUSDT", "SKLUSDT",
            "SNTUSDT", "STORMUSDT", "STRAXUSDT", "TCTUSDT", "TROYUSDT",
            "TUSDUSDT", "USDCUSDT", "USTUSDT", "WINGUSDT", "WINUSDT",
            "WRXUSDT", "XEMUSDT", "ZECUSDT", "ZENUSDT", "ZRXUSDT"
        ]
        return [s for s in fallback_symbols if s not in BLACKLISTED_COINS][:MAX_SYMBOLS_TO_SCAN]

def fetch_single_timeframe(symbol, interval, limit=200):
    """একটি টাইমফ্রেমের জন্য ডেটা ফেচ করা"""
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        rate_limit()
        res = session.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logging.warning(f"Error fetching {symbol} {interval}: {e}")
        return None

def fetch_multi_timeframe_data(symbol):
    """মাল্টিপল টাইমফ্রেম ডেটা ফেচ করা (অপ্টিমাইজড)"""
    timeframes = ['15m', '1h', '4h']
    data = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(fetch_single_timeframe, symbol, tf): tf 
            for tf in timeframes
        }
        
        for future in concurrent.futures.as_completed(futures):
            tf = futures[future]
            try:
                tf_data = future.result()
                if tf_data and len(tf_data) >= 100:
                    data[tf] = tf_data
            except Exception as e:
                logging.error(f"Error processing {symbol} {tf}: {e}")
    
    return data if data else None

# অপ্টিমাইজড ইন্ডিকেটর ক্যালকুলেশন ফাংশন
def calculate_ema(data, length):
    if len(data) < length:
        return None
    return pd.Series(data).ewm(span=length, adjust=False).mean().iloc[-1]

def calculate_sma(data, length):
    if len(data) < length:
        return None
    return np.mean(data[-length:])

def calculate_rsi(data, length=14):
    if len(data) < length + 1:
        return None
    delta = np.diff(data)
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = pd.Series(gain).rolling(window=length).mean().iloc[-1]
    avg_loss = pd.Series(loss).rolling(window=length).mean().iloc[-1]
    rs = avg_gain / avg_loss if avg_loss != 0 else 0
    return 100 - (100 / (1 + rs))

def calculate_macd(data, fast=12, slow=26, signal=9):
    if len(data) < slow:
        return None, None, None
    ema_fast = pd.Series(data).ewm(span=fast, adjust=False).mean()
    ema_slow = pd.Series(data).ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line.iloc[-1], signal_line.iloc[-1], histogram.iloc[-1]

def calculate_bollinger_bands(data, length=20, std_dev=2):
    if len(data) < length:
        return None, None, None
    middle = pd.Series(data).rolling(window=length).mean().iloc[-1]
    std = pd.Series(data).rolling(window=length).std().iloc[-1]
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    return upper, middle, lower

def calculate_stochastic(highs, lows, closes, k_period=14, d_period=3):
    if len(closes) < k_period:
        return None, None
    low_min = pd.Series(lows).rolling(window=k_period).min()
    high_max = pd.Series(highs).rolling(window=k_period).max()
    k_percent = 100 * (closes - low_min) / (high_max - low_min)
    d_percent = k_percent.rolling(window=d_period).mean()
    return k_percent.iloc[-1], d_percent.iloc[-1]

def calculate_adx(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return None
    df = pd.DataFrame({'high': highs, 'low': lows, 'close': closes})
    df['up_move'] = df['high'].diff()
    df['down_move'] = df['low'].diff().apply(lambda x: -x)
    df['+dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
    df['-dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
    df['tr'] = np.maximum(df['high'] - df['low'], 
                         np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                   abs(df['low'] - df['close'].shift(1))))
    df['+di'] = 100 * (df['+dm'].rolling(window=period).mean() / df['tr'].rolling(window=period).mean())
    df['-di'] = 100 * (df['-dm'].rolling(window=period).mean() / df['tr'].rolling(window=period).mean())
    df['dx'] = 100 * abs(df['+di'] - df['-di']) / (df['+di'] + df['-di'])
    return df['dx'].rolling(window=period).mean().iloc[-1]

def calculate_comprehensive_indicators(multi_tf_data):
    """সব টাইমফ্রেমের জন্য কম্প্রিহেনসিভ ইন্ডিকেটর ক্যালকুলেশন (অপ্টিমাইজড)"""
    all_indicators = {}
    
    for tf, data in multi_tf_data.items():
        closes = np.array([float(c[4]) for c in data])
        highs = np.array([float(c[2]) for c in data])
        lows = np.array([float(c[3]) for c in data])
        volumes = np.array([float(c[5]) for c in data])
        
        if len(closes) < 200:
            continue
        
        indicators = {}
        
        # মুভিং এভারেজেস
        indicators['ema20'] = calculate_ema(closes, 20) or closes[-1]
        indicators['ema50'] = calculate_ema(closes, 50) or closes[-1]
        indicators['ema200'] = calculate_ema(closes, 200) or closes[-1]
        indicators['sma20'] = calculate_sma(closes, 20) or closes[-1]
        indicators['sma50'] = calculate_sma(closes, 50) or closes[-1]
        
        # RSI
        indicators['rsi14'] = calculate_rsi(closes, 14) or 50
        indicators['rsi21'] = calculate_rsi(closes, 21) or 50
        
        # স্টোকাস্টিক
        stoch_k, stoch_d = calculate_stochastic(highs, lows, closes, 14, 3)
        indicators['stoch_k'] = stoch_k or 50
        indicators['stoch_d'] = stoch_d or 50
        
        # MACD
        macd, macdsignal, macdhist = calculate_macd(closes, 12, 26, 9)
        indicators['macd'] = macd or 0
        indicators['macd_signal'] = macdsignal or 0
        indicators['macd_hist'] = macdhist or 0
        
        # বলিঙ্গার ব্যান্ড
        upper, middle, lower = calculate_bollinger_bands(closes, 20, 2)
        indicators['bb_upper'] = upper or closes[-1]
        indicators['bb_middle'] = middle or closes[-1]
        indicators['bb_lower'] = lower or closes[-1]
        indicators['bb_width'] = ((upper - middle) / middle * 100) if middle != 0 else 0
        
        # ADX
        indicators['adx'] = calculate_adx(highs, lows, closes, 14) or 25
        
        # ভলিউম ইন্ডিকেটর
        indicators['volume_sma'] = calculate_sma(volumes, 20) or volumes[-1]
        indicators['volume_ratio'] = volumes[-1] / indicators['volume_sma'] if indicators['volume_sma'] != 0 else 1
        
        # প্রাইস অ্যাকশন
        indicators['price_change_5'] = ((closes[-1] - closes[-5]) / closes[-5] * 100) if len(closes) > 5 else 0
        indicators['price_change_10'] = ((closes[-1] - closes[-10]) / closes[-10] * 100) if len(closes) > 10 else 0
        
        # ভোলাটিলিটি
        indicators['volatility'] = indicators['bb_width']
        
        all_indicators[tf] = indicators
    
    return all_indicators

def determine_market_regime(indicators):
    """মার্কেট রেজিম ডিটারমাইন করা (সরলীকৃত)"""
    tf15m = indicators.get('15m', {})
    tf1h = indicators.get('1h', {})
    
    # ট্রেন্ডিং মার্কেট কন্ডিশন
    trending = 0
    if tf15m.get('ema20', 0) > tf15m.get('ema50', 0) > tf15m.get('ema200', 0):
        trending += 1
    if tf1h.get('ema20', 0) > tf1h.get('ema50', 0) > tf1h.get('ema200', 0):
        trending += 1
    if tf15m.get('adx', 0) > 25:
        trending += 1
    
    # রেঞ্জিং মার্কেট কন্ডিশন
    ranging = 0
    if tf15m.get('bb_width', 0) < 5:
        ranging += 1
    if tf1h.get('bb_width', 0) < 5:
        ranging += 1
    if tf15m.get('adx', 0) < 20:
        ranging += 1
    
    if trending >= 2:
        return 'trending'
    elif ranging >= 2:
        return 'ranging'
    else:
        return 'neutral'

def get_strict_signal(indicators, market_regime, symbol):
    """স্ট্রিক্ট সিগন্যাল জেনারেশন (সরলীকৃত)"""
    tf15m = indicators.get('15m', {})
    tf1h = indicators.get('1h', {})
    
    current_price = tf15m.get('ema20', 0)
    
    # বাই সিগন্যাল কন্ডিশন
    buy_score = 0
    
    # মাল্টিপল টাইমফ্রেম কনফার্মেশন
    if tf15m.get('ema20', 0) > tf15m.get('ema50', 0) > tf15m.get('ema200', 0):
        buy_score += 2
    if tf1h.get('ema20', 0) > tf1h.get('ema50', 0) > tf1h.get('ema200', 0):
        buy_score += 2
    
    # RSI কনফার্মেশন
    if 50 < tf15m.get('rsi14', 0) < 70:
        buy_score += 1
    if 50 < tf1h.get('rsi14', 0) < 70:
        buy_score += 1
    
    # MACD কনফার্মেশন
    if tf15m.get('macd', 0) > tf15m.get('macd_signal', 0) and tf15m.get('macd_hist', 0) > 0:
        buy_score += 1
    if tf1h.get('macd', 0) > tf1h.get('macd_signal', 0) and tf1h.get('macd_hist', 0) > 0:
        buy_score += 1
    
    # স্টোকাস্টিক কনফার্মেশন
    if tf15m.get('stoch_k', 0) > tf15m.get('stoch_d', 0) and tf15m.get('stoch_k', 0) < 80:
        buy_score += 1
    
    # ADX কনফার্মেশন
    if tf15m.get('adx', 0) > 25:
        buy_score += 1
    
    # ভলিউম কনফার্মেশন
    if tf15m.get('volume_ratio', 0) > 1.2:
        buy_score += 1
    
    # সেল সিগন্যাল কন্ডিশন
    sell_score = 0
    
    # মাল্টিপল টাইমফ্রেম কনফার্মেশন
    if tf15m.get('ema20', 0) < tf15m.get('ema50', 0) < tf15m.get('ema200', 0):
        sell_score += 2
    if tf1h.get('ema20', 0) < tf1h.get('ema50', 0) < tf1h.get('ema200', 0):
        sell_score += 2
    
    # RSI কনফার্মেশন
    if 30 < tf15m.get('rsi14', 0) < 50:
        sell_score += 1
    if 30 < tf1h.get('rsi14', 0) < 50:
        sell_score += 1
    
    # MACD কনফার্মেশন
    if tf15m.get('macd', 0) < tf15m.get('macd_signal', 0) and tf15m.get('macd_hist', 0) < 0:
        sell_score += 1
    if tf1h.get('macd', 0) < tf1h.get('macd_signal', 0) and tf1h.get('macd_hist', 0) < 0:
        sell_score += 1
    
    # স্টোকাস্টিক কনফার্মেশন
    if tf15m.get('stoch_k', 0) < tf15m.get('stoch_d', 0) and tf15m.get('stoch_k', 0) > 20:
        sell_score += 1
    
    # ADX কনফার্মেশন
    if tf15m.get('adx', 0) > 25:
        sell_score += 1
    
    # ভলিউম কনফার্মেশন
    if tf15m.get('volume_ratio', 0) > 1.2:
        sell_score += 1
    
    # ডিসিশন মেকিং
    if buy_score >= 7:
        return "BUY"
    elif sell_score >= 7:
        return "SELL"
    else:
        return "NO SIGNAL"

def calculate_dynamic_levels(price, signal, indicators):
    """ডায়নামিক TP/SL লেভেল ক্যালকুলেশন (সরলীকৃত)"""
    tf15m = indicators.get('15m', {})
    volatility = tf15m.get('volatility', 2)
    
    # ভোলাটিলিটি অনুযায়ী TP/SL অ্যাডজাস্ট
    if volatility > 3:
        tp_percent = 1.5
        sl_percent = 1.0
    elif volatility > 2:
        tp_percent = 1.2
        sl_percent = 0.8
    else:
        tp_percent = 1.0
        sl_percent = 0.6
    
    if signal == "BUY":
        entry = price
        tp = round(price * (1 + tp_percent/100), 8)
        sl = round(price * (1 - sl_percent/100), 8)
    elif signal == "SELL":
        entry = price
        tp = round(price * (1 - tp_percent/100), 8)
        sl = round(price * (1 + sl_percent/100), 8)
    else:
        entry = tp = sl = price
    
    return entry, tp, sl

def calculate_signal_score(indicators, signal):
    """সিগন্যাল স্কোর ক্যালকুলেশন (সরলীকৃত)"""
    tf15m = indicators.get('15m', {})
    tf1h = indicators.get('1h', {})
    
    score = 0
    
    # মাল্টিপল টাইমফ্রেম অ্যালাইনমেন্ট
    if (tf15m.get('ema20', 0) > tf15m.get('ema50', 0)) == (tf1h.get('ema20', 0) > tf1h.get('ema50', 0)):
        score += 30
    
    # ট্রেন্ড স্ট্রেংথ
    if tf15m.get('adx', 0) > 30:
        score += 20
    if tf1h.get('adx', 0) > 30:
        score += 20
    
    # ভলিউম কনফার্মেশন
    if tf15m.get('volume_ratio', 0) > 1.5:
        score += 15
    
    # ভোলাটিলিটি
    volatility = tf15m.get('volatility', 1)
    if 1 < volatility < 3:
        score += 15
    
    return score

def analyze_trade_opportunity(symbol):
    """ট্রেড অপরচুনিটি অ্যানালাইসিস (অপ্টিমাইজড)"""
    try:
        # মাল্টিপল টাইমফ্রেম ডেটা ফেচ
        multi_tf_data = fetch_multi_timeframe_data(symbol)
        
        if not multi_tf_data:
            return None
        
        # কম্প্রিহেনসিভ ইন্ডিকেটর ক্যালকুলেশন
        indicators = calculate_comprehensive_indicators(multi_tf_data)
        
        if not indicators:
            return None
        
        # মার্কেট রেজিম ডিটারমাইনেশন
        market_regime = determine_market_regime(indicators)
        
        # স্ট্রিক্ট সিগন্যাল জেনারেশন
        signal = get_strict_signal(indicators, market_regime, symbol)
        
        if signal in ["BUY", "SELL"]:
            tf15m = indicators.get('15m', {})
            price = tf15m.get('ema20', 0)
            
            if price == 0:
                return None
            
            # ডায়নামিক TP/SL ক্যালকুলেশন
            entry, tp, sl = calculate_dynamic_levels(price, signal, indicators)
            
            # সিগন্যাল স্কোর ক্যালকুলেশন
            score = calculate_signal_score(indicators, signal)
            
            # কম স্কোর হলে সিগন্যাল বাতিল
            if score < 80:
                return None
            
            signal_data = {
                'symbol': symbol,
                'price': price,
                'signal': signal,
                'entry': entry,
                'tp': tp,
                'sl': sl,
                'indicators': indicators,
                'market_regime': market_regime,
                'score': score,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return signal_data
    except Exception as e:
        logging.error(f"Error analyzing {symbol}: {e}")
    
    return None

def scan_best_signal():
    """সেরা সিগন্যাল স্ক্যান করা (অপ্টিমাইজড)"""
    symbols = get_all_futures_symbols()
    
    if not symbols:
        logging.warning("No symbols available")
        return None
    
    logging.info(f"Scanning {len(symbols)} symbols: {', '.join(symbols[:10])}... (and {len(symbols)-10} more)")
    
    best = None
    best_score = 0
    
    current_time = time.time()
    
    # প্যারালাল প্রসেসিং ব্যবহার করে সব সিম্বল একসাথে প্রসেস করা
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        future_to_symbol = {
            executor.submit(analyze_trade_opportunity, symbol): symbol 
            for symbol in symbols
        }
        
        for future in concurrent.futures.as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                data = future.result()
                if data and data['score'] > best_score:
                    best = data
                    best_score = data['score']
            except Exception as e:
                logging.error(f"Error processing {symbol}: {e}")
    
    return best

def display_signal(signal):
    indicators = signal['indicators']
    tf15m = indicators.get('15m', {})
    tf1h = indicators.get('1h', {})
    
    print("\n" + "="*80)
    print("🔔 HIGH ACCURACY TRADING SIGNAL DETECTED!")
    print("="*80)
    print(f"📅 Time: {signal['timestamp']}")
    print(f"🪙 Symbol: {signal['symbol']}")
    print(f"📊 Direction: {signal['signal']}")
    print(f"⭐ Signal Score: {signal['score']}/100")
    print("-"*80)
    print(f"💰 Current Price: ${signal['price']:.8f}")
    print(f"🎯 Entry: ${signal['entry']:.8f}")
    print(f"📈 Take Profit: ${signal['tp']:.8f}")
    print(f"📉 Stop Loss: ${signal['sl']:.8f}")
    print("-"*80)
    print("📈 15m INDICATORS:")
    print(f"   EMA20: {tf15m.get('ema20', 0):.8f} | EMA50: {tf15m.get('ema50', 0):.8f}")
    print(f"   RSI14: {tf15m.get('rsi14', 0):.2f} | MACD: {tf15m.get('macd', 0):.6f}")
    print(f"   ADX: {tf15m.get('adx', 0):.2f} | Volume: {tf15m.get('volume_ratio', 0):.2f}x")
    print("-"*80)
    print("📈 1h CONFIRMATION:")
    print(f"   EMA20: {tf1h.get('ema20', 0):.8f} | EMA50: {tf1h.get('ema50', 0):.8f}")
    print(f"   RSI14: {tf1h.get('rsi14', 0):.2f} | ADX: {tf1h.get('adx', 0):.2f}")
    print("="*80 + "\n")

def save_signal_to_file(signal):
    profit_percent = ((signal['tp'] - signal['entry']) / signal['entry'] * 100) if signal['entry'] != 0 else 0
    loss_percent = ((signal['sl'] - signal['entry']) / signal['entry'] * 100) if signal['entry'] != 0 else 0
    
    profit_usd = INVESTMENT_AMOUNT * LEVERAGE * (profit_percent / 100)
    loss_usd = INVESTMENT_AMOUNT * LEVERAGE * (loss_percent / 100)
    
    signal_with_profit = signal.copy()
    signal_with_profit['investment'] = INVESTMENT_AMOUNT
    signal_with_profit['leverage'] = LEVERAGE
    signal_with_profit['potential_profit_usd'] = round(profit_usd, 2)
    signal_with_profit['potential_loss_usd'] = round(loss_usd, 2)
    signal_with_profit['profit_percent'] = round(profit_percent, 2)
    signal_with_profit['loss_percent'] = round(loss_percent, 2)
    
    with open('trading_signals.json', 'a', encoding='utf-8') as f:
        json.dump(signal_with_profit, f)
        f.write('\n')

def main():
    logging.info("HIGH ACCURACY TRADING BOT STARTED")
    
    signal_count = 0
    
    while True:
        try:
            logging.info("Scanning for high accuracy signals...")
            
            best_signal = scan_best_signal()
            
            if best_signal:
                signal_count += 1
                symbol = best_signal['symbol']
                
                # সিগন্যাল হিস্ট্রি আপডেট
                signal_history[symbol] = time.time()
                
                # পারফরম্যান্স ট্র্যাকিং
                if symbol not in signal_performance:
                    signal_performance[symbol] = {'total': 0, 'success': 0}
                
                logging.info(f"High accuracy signal #{signal_count} found for {symbol}")
                display_signal(best_signal)
                save_signal_to_file(best_signal)
                
        except Exception as e:
            logging.error(f"Main loop error: {e}")
            
        time.sleep(30)  # ৩০ সেকেন্ড স্ক্যানিং ইন্টারভাল

if __name__ == "__main__":
    main()