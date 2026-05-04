import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import sys
import requests

# --- CONFIGURACIÓN VISUAL "INSTITUTIONAL TERMINAL" ---
plt.style.use('dark_background')
plt.rcParams['savefig.facecolor'] = '#0f0f0f'
plt.rcParams['figure.facecolor']  = '#0f0f0f'
plt.rcParams['axes.edgecolor']    = '#333333'
plt.rcParams['text.color']        = '#ffffff'

COLORS = {
    'price':        '#E0E0E0',
    'zscore':       '#00E676',
    'over':         '#FF1744',
    'under':        '#00B0FF',
    'accumulation': '#FFD700',
    'bg_bull':      '#004D40',
    'bg_bear':      '#3E2723',
}

TIMEFRAMES = ['4h', '1d', '1w', '1M']

SUPPLY_FALLBACK = {
    'BTC': 19_500_000,
    'ETH': 120_000_000,
}

COINGECKO_IDS = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
}


class ZScoreElite:
    def __init__(self, symbol: str):
        self.symbol      = symbol.upper()
        self.symbol_pair = f"{self.symbol}/USDT"
        # OKX → Bybit → Binance — se intentan en orden
        self.exchanges   = [ccxt.okx(), ccxt.bybit(), ccxt.binance()]

    # ------------------------------------------------------------------
    async def get_circulating_supply(self) -> float:
        coin_id  = COINGECKO_IDS.get(self.symbol, self.symbol.lower())
        fallback = SUPPLY_FALLBACK.get(self.symbol, 21_000_000)
        try:
            r    = requests.get(
                f'https://api.coingecko.com/api/v3/coins/{coin_id}',
                timeout=5,
            )
            r.raise_for_status()
            data = r.json()
            supply = data['market_data']['circulating_supply']
            if not supply or supply <= 0:
                raise ValueError("Invalid supply value")
            return float(supply)
        except Exception as exc:
            print(f"⚠️  CoinGecko failed ({exc}). Using fallback supply: {fallback:,}")
            return float(fallback)

    # ------------------------------------------------------------------
    async def fetch_ohlcv(self, tf: str, limit: int = 500) -> pd.DataFrame:
        """Intenta OKX → Bybit → Binance; lanza excepción si todos fallan."""
        last_exc = None
        for ex in self.exchanges:
            try:
                await ex.load_markets()
                print(f"📡 Fetching {self.symbol} {tf} from {ex.id}…")
                raw = await ex.fetch_ohlcv(self.symbol_pair, tf, limit=limit)
                if not raw:
                    raise ValueError("Empty OHLCV response")
                return pd.DataFrame(raw, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            except Exception as exc:
                print(f"❌ {ex.id} failed: {exc}")
                last_exc = exc
                continue
        raise RuntimeError(
            f"Could not fetch {self.symbol} {tf} from any exchange. Last error: {last_exc}"
        )

    # ------------------------------------------------------------------
    async def close_exchanges(self):
        for ex in self.exchanges:
            try:
                await ex.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    def calculate_metrics(self, df: pd.DataFrame, supply: float) -> pd.DataFrame:
        if len(df) < 50:
            raise ValueError(f"Insufficient data ({len(df)} rows) for Z-Score calculation")

        df = df.copy()
        df['date'] = pd.to_datetime(df['ts'], unit='ms')

        # 1. Market Cap
        df['market_cap'] = df['c'] * supply

        # 2. Realized Cap — VWAP con Time Decay (fórmula canónica, no modificar)
        df['vwap'] = (df['c'] * df['v']).cumsum() / df['v'].cumsum()
        decay = np.power(0.995, np.arange(len(df))[::-1])
        df['realized_cap'] = (df['vwap'] * decay) * supply

        # 3. MVRV Ratio
        df['mvrv'] = (df['market_cap'] / df['realized_cap'].replace(0, np.nan)) - 1

        # 4. Z-Score Rolling
        window = min(200, len(df) - 1)
        df['mvrv_mean']     = df['mvrv'].rolling(window=window, min_periods=50).mean()
        df['mvrv_std']      = df['mvrv'].rolling(window=window, min_periods=50).std()
        raw_std             = df['mvrv_std'].replace(0, np.nan)
        df['zscore']        = (df['mvrv'] - df['mvrv_mean']) / raw_std
        df['zscore_smooth'] = df['zscore'].ewm(alpha=0.05).mean()

        # 5. Fase Wyckoff simplificada
        df['phase'] = 'Neutral'
        for i in range(30, len(df)):
            z   = df['zscore_smooth'].iloc[i]
            c   = df['c'].iloc[i]
            c20 = df['c'].iloc[i - 20]
            if z < -0.3 and c > c20:
                df.loc[df.index[i], 'phase'] = 'Accumulation'
            elif z > 0.4 and c < c20:
                df.loc[df.index[i], 'phase'] = 'Distribution'
            elif z > 0.4:
                df.loc[df.index[i], 'phase'] = 'Distribution'

        return df

    # ------------------------------------------------------------------
    def get_institutional_score(self, z: float, phase: str) -> int:
        """Score 0-100 basado en extremos de Z-Score y fase Wyckoff."""
        if not np.isfinite(z):
            return 50

        score = 50

        if z < -0.5:   score += 30
        elif z > 0.5:  score -= 30

        if phase == 'Accumulation':  score += 20
        if phase == 'Distribution':  score -= 20

        return max(0, min(100, int(score)))

    # ------------------------------------------------------------------
    def plot_chart(self, df: pd.DataFrame, tf: str, supply: float,
                   z: float, phase: str, score: int) -> str:

        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(14, 10),
            gridspec_kw={'height_ratios': [2.5, 1]},
            sharex=True,
            facecolor='#0f0f0f',
        )
        ax1.set_facecolor('#0f0f0f')
        ax2.set_facecolor('#0f0f0f')

        status_color = (
            COLORS['zscore'] if score > 60
            else COLORS['over'] if score < 40
            else 'yellow'
        )
        status_text = (
            "🟢 STRONG ACCUMULATION" if score > 60
            else "🔴 DISTRIBUTION" if score < 40
            else "🟡 NEUTRAL"
        )

        fig.suptitle(
            f'MVRV Z-SCORE ÉLITE  •  {self.symbol}  •  {tf.upper()}  •  '
            f'{datetime.now().strftime("%d/%m %H:%M")}\n'
            f'Institutional Score: {score}/100',
            fontsize=16, color='gold', fontweight='bold',
        )

        # ---- Panel 1: Precio ----
        ax1.plot(df['date'], df['c'], color=COLORS['price'], linewidth=2, label='Price')
        trend_up = df['c'].iloc[-1] > df['c'].iloc[0]
        ax1.fill_between(
            df['date'], df['c'].min(), df['c'].max(),
            color=COLORS['bg_bull'] if trend_up else COLORS['bg_bear'],
            alpha=0.15,
        )
        ax1.set_ylabel('Price (USDT)', fontsize=12, color='#AAAAAA')
        ax1.grid(True, color='#333333', linestyle='--', linewidth=0.5)
        ax1.legend(loc='upper left', facecolor='#1A1A1A', edgecolor='#555555')
        ax1.tick_params(colors='#AAAAAA')

        # ---- Panel 2: Z-Score ----
        valid = df['zscore_smooth'].dropna()
        ax2.plot(df['date'], df['zscore_smooth'], color=COLORS['zscore'],
                 linewidth=2.5, label='MVRV Z-Score')
        ax2.axhline(0,     color='white',          linestyle='--', alpha=0.5,  label='Fair Value')
        ax2.axhline( 0.25, color=COLORS['over'],   linestyle='-',  alpha=0.8,  label='Overvalued Zone')
        ax2.axhline(-0.25, color=COLORS['under'],  linestyle='-',  alpha=0.8,  label='Undervalued Zone')

        ax2.fill_between(df['date'], df['zscore_smooth'], 0,
                         where=(df['zscore_smooth'] > 0),
                         color=COLORS['over'],  alpha=0.25)
        ax2.fill_between(df['date'], df['zscore_smooth'], 0,
                         where=(df['zscore_smooth'] < 0),
                         color=COLORS['under'], alpha=0.25)

        # Límites dinámicos con margen
        if len(valid) > 0:
            z_min = max(valid.min() - 0.3, -3.0)
            z_max = min(valid.max() + 0.3,  3.0)
            ax2.set_ylim(z_min, z_max)
        else:
            ax2.set_ylim(-2.5, 2.5)

        ax2.set_ylabel('Z-Score', color='#AAAAAA')
        ax2.legend(loc='upper left', facecolor='#1A1A1A', edgecolor='#555555')
        ax2.grid(True, color='#333333', linestyle='--', linewidth=0.5)
        ax2.tick_params(colors='#AAAAAA')

        # ---- HUD ----
        hud_text = (
            f"{status_text}\n"
            f"Z-SCORE: {z:.3f}\n"
            f"PHASE:   {phase}\n"
            f"SUPPLY:  {supply:,.0f}"
        )
        props = dict(boxstyle='round', facecolor='#1A1A1A', alpha=0.92,
                     edgecolor=status_color)
        ax2.text(
            0.02, 0.95, hud_text,
            transform=ax2.transAxes, fontsize=11,
            verticalalignment='top', bbox=props,
            color='white', fontfamily='monospace', fontweight='bold',
        )

        plt.tight_layout()
        filename = f'zscore_{self.symbol.lower()}_{tf}.png'
        plt.savefig(filename, dpi=200, facecolor='#0f0f0f',
                    edgecolor='none', bbox_inches='tight')
        plt.close(fig)
        return filename

    # ------------------------------------------------------------------
    def generate_caption(self, tf: str, z: float, phase: str,
                          score: int, price: float) -> str:
        if score > 70:
            status = "🟢 **ALZA MACRO**"
            advice = "Activo infravalorado históricamente. Zona de compra institucional."
        elif score < 30:
            status = "🔴 **RIESGO MACRO**"
            advice = "Activo sobrevalorado. Riesgo de corrección o distribución."
        else:
            status = "🟡 **NEUTRALIDAD**"
            advice = "Precio en rango justo. Esperar confirmación de dirección."

        return (
            f"{status}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 **Activo:** {self.symbol} ({tf.upper()})\n"
            f"💰 **Precio:** ${price:,.2f}\n"
            f"📊 **Z-Score:** `{z:.3f}`\n"
            f"📈 **Score:** `{score}/100`\n"
            f"🏛️ **Fase:** `{phase}`\n"
            f"💡 **Insight:** {advice}"
        )


# ----------------------------------------------------------------------
async def main(symbol: str):
    bot = ZScoreElite(symbol)
    output_files = []

    try:
        print(f"🚀 INICIANDO ANÁLISIS Z-SCORE PARA {symbol}…")
        supply = await bot.get_circulating_supply()
        print(f"📦 Supply: {supply:,.0f} {symbol}")

        for tf in TIMEFRAMES:
            try:
                df      = await bot.fetch_ohlcv(tf)
                df      = bot.calculate_metrics(df, supply)

                latest_z = float(df['zscore_smooth'].iloc[-1])
                if not np.isfinite(latest_z):
                    latest_z = 0.0

                phase   = df['phase'].iloc[-1]
                score   = bot.get_institutional_score(latest_z, phase)
                price   = float(df['c'].iloc[-1])

                img_file = bot.plot_chart(df, tf, supply, latest_z, phase, score)
                caption  = bot.generate_caption(tf, latest_z, phase, score, price)

                output_files.append({'image': img_file, 'caption': caption, 'tf': tf, 'z': latest_z, 'phase': phase, 'score': score, 'price': price})
                print(f"✅ [{tf.upper()}] Score: {score}/100  Z: {latest_z:.3f}  →  {img_file}")

            except Exception as exc:
                print(f"❌ Error procesando {tf}: {exc}")

        # Save JSON summary
        summary = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'timeframes': {
                item['tf']: {
                    'score': item['score'],
                    'zscore': item['z'],
                    'phase': item['phase'],
                    'price': item['price']
                } for item in output_files
            }
        }
        import json
        json_file = f"zscore_elite_{symbol.lower()}.json"
        with open(json_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"📊 JSON summary saved to {json_file}")

    finally:
        await bot.close_exchanges()

    return output_files


# ----------------------------------------------------------------------
if __name__ == '__main__':
    sym     = sys.argv[1].strip().upper() if len(sys.argv) > 1 else 'BTC'
    results = asyncio.run(main(sym))

    for item in results:
        print(f"\n📸 PHOTO: {item['image']}")
        print(f"📝 CAPTION:\n{item['caption']}\n")
