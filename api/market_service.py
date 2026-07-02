import json
import time
from decimal import Decimal
from urllib.error import URLError
from urllib.request import Request, urlopen
from django.conf import settings

CACHE_TTL = 30
_cache = {}


def _binance_base():
    return settings.BINANCE_BASE_URL.rstrip('/')


def _binance_symbol():
    return settings.BINANCE_SYMBOL


def _fetch_json(url, timeout=8):
    headers = {}
    if settings.BINANCE_API_KEY:
        headers['X-MBX-APIKEY'] = settings.BINANCE_API_KEY
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def _interval_map(timeframe='15m'):
    return {
        '1m': '1m',
        '5m': '5m',
        '15m': '15m',
        '1H': '1h',
        '4H': '4h',
        '1D': '1d',
    }.get(timeframe, '15m')


def get_btc_market(timeframe='15m', use_cache=True):
    now = time.time()
    symbol = _binance_symbol()
    cache_key = f'market_{symbol}_{timeframe}'
    if use_cache and _cache.get(cache_key) and now - _cache.get(f'{cache_key}_at', 0) < CACHE_TTL:
        return _cache[cache_key]

    base = _binance_base()
    ticker = _fetch_json(f'{base}/ticker/24hr?symbol={symbol}')
    interval = _interval_map(timeframe)
    klines = _fetch_json(f'{base}/klines?symbol={symbol}&interval={interval}&limit=30')
    trades = _fetch_json(f'{base}/trades?symbol={symbol}&limit=10')

    candles = []
    for i, k in enumerate(klines):
        candles.append({
            'time': i,
            'open': float(k[1]),
            'high': float(k[2]),
            'low': float(k[3]),
            'close': float(k[4]),
        })

    live_trades = []
    for trade in reversed(trades):
        live_trades.append({
            'type': 'SELL' if trade.get('isBuyerMaker') else 'BUY',
            'price': float(trade['price']),
            'amount': float(trade['qty']),
            'time': trade.get('time'),
        })

    result = {
        'symbol': symbol.replace('USDT', '/USDT') if 'USDT' in symbol else symbol,
        'price': float(ticker['lastPrice']),
        'change': float(ticker['priceChangePercent']),
        'high_24h': float(ticker['highPrice']),
        'low_24h': float(ticker['lowPrice']),
        'volume_24h': ticker['volume'],
        'candles': candles,
        'live_trades': live_trades,
        'source': 'binance',
    }

    _cache[cache_key] = result
    _cache[f'{cache_key}_at'] = now
    return result


def get_btc_price():
    market = get_btc_market()
    return Decimal(str(market['price']))
