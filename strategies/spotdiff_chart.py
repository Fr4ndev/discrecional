import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import zscore
import sys

# --- CONFIGURACIÓN VISUAL "BLOOMBERG" ---
plt.style.use('dark_background')
plt.rcParams['savefig.facecolor'] = '#121212'
plt.rcParams['axes.edgecolor'] = '#333333'
plt.rcParams['figure.facecolor'] = '#121212'

COLORS = {
    'price':   '#E0E0E0',
    'spot':    '#00E676',
    'fut':     '#FF1744',
    'whale':   '#D500F9',
    'funding': '#FFEA00',
    'bull_bg': '#004D40',
    'bear_bg': '#3E2723',
}


class SpotDiffElite:
    def __init__(self, symbol: str):
        self.symbol     = symbol.upper()
        self.symbol_spot = f"{self.symbol}/USDT"
        self.symbol_fut  = f"{self.symbol}/USDT:USDT"
        self.exchange    = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'},
        })

    # ------------------------------------------------------------------
    async def fetch_data(self) -> dict:
        """Descarga OHLCV, Order Book y Funding Rate en paralelo."""
        try:
            await self.exchange.load_markets()

            tfs = {'1d': 400, '1w': 120}
            results = {}

            for tf, limit in tfs.items():
                tasks = [
                    self.exchange.fetch_ohlcv(self.symbol_spot, tf, limit=limit),
                    self.exchange.fetch_ohlcv(self.symbol_fut,  tf, limit=limit),
                    self.exchange.fetch_funding_rate(self.symbol_fut),
                    self.exchange.fetch_order_book(self.symbol_spot, limit=20),
                ]
                raw = await asyncio.gather(*tasks, return_exceptions=True)
                s_ohlcv, f_ohlcv, funding, ob = raw

                if isinstance(s_ohlcv, Exception):
                    print(f"[WARN] spot OHLCV {tf}: {s_ohlcv}")
                    s_ohlcv = []
                if isinstance(f_ohlcv, Exception):
                    print(f"[WARN] fut OHLCV {tf}: {f_ohlcv}")
                    f_ohlcv = []
                if isinstance(funding, Exception):
                    print(f"[WARN] funding {tf}: {funding}")
                    funding = {}
                if isinstance(ob, Exception):
                    print(f"[WARN] order book {tf}: {ob}")
                    ob = {'bids': [], 'asks': []}

                results[tf] = {
                    'spot':    s_ohlcv,
                    'fut':     f_ohlcv,
                    'funding': funding.get('fundingRate', 0) or 0,
                    'ob':      ob,
                }

            return results
        finally:
            await self.exchange.close()

    # ------------------------------------------------------------------
    def _safe_zscore(self, series: pd.Series) -> pd.Series:
        """Z-score robusto: devuelve ceros si la desviación estándar es ~0."""
        arr = series.fillna(0).values
        std = arr.std()
        if std < 1e-10:
            return pd.Series(np.zeros(len(arr)), index=series.index)
        return pd.Series((arr - arr.mean()) / std, index=series.index)

    # ------------------------------------------------------------------
    def calculate_metrics(self, spot_data: list, fut_data: list) -> pd.DataFrame:
        """Núcleo cuantitativo: CVD, IAI, Whale Detection, Divergencia."""
        cols = ['ts', 'o', 'h', 'l', 'c', 'v']
        df_s = pd.DataFrame(spot_data, columns=cols)
        df_f = pd.DataFrame(fut_data,  columns=cols)

        df = pd.merge(df_s, df_f, on='ts', suffixes=('_s', '_f'))
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')

        # ---- CVD ----
        df['range_s'] = (df['h_s'] - df['l_s']).replace(0, np.nan)
        df['delta_s'] = ((df['c_s'] - df['o_s']) / df['range_s']) * df['v_s']
        df['delta_f'] = ((df['c_f'] - df['o_f']) / df['range_s']) * df['v_f']
        df['cvd_s']   = df['delta_s'].cumsum()
        df['cvd_f']   = df['delta_f'].cumsum()

        df['cvd_s_z']   = self._safe_zscore(df['cvd_s'])
        df['cvd_f_z']   = self._safe_zscore(df['cvd_f'])
        df['divergence'] = df['cvd_s_z'] - df['cvd_f_z']

        # ---- IAI ----
        vol_ratio = (df['v_s'] / df['v_f'].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        df['vol_ratio'] = vol_ratio
        df['iai_z']     = self._safe_zscore(vol_ratio)

        # ---- Whale / Iceberg ----
        df['impact']  = df['v_s'] / df['range_s']
        df['whale_z'] = self._safe_zscore(df['impact'])
        df['is_whale'] = df['whale_z'] > 2.2

        return df

    # ------------------------------------------------------------------
    def get_institutional_score(self, df: pd.DataFrame, current_funding: float,
                                 current_obi: float) -> int:
        """Score 0-100 basado en divergencia, IAI, ballenas, OBI y funding."""
        last_div = df['divergence'].iloc[-1]
        last_iai = df['iai_z'].iloc[-1]
        whale_activity = int(df['is_whale'].iloc[-10:].sum())

        if not np.isfinite(last_div): last_div = 0.0
        if not np.isfinite(last_iai): last_iai = 0.0

        score = 50

        # Factor 1 – Divergencia
        if last_div > 0.5:  score += 20
        elif last_div < -0.5: score -= 20

        # Factor 2 – Absorción IAI
        if last_iai > 1.0:  score += 15
        elif last_iai < -1.0: score -= 15

        # Factor 3 – Ballenas
        if whale_activity > 0: score += 10

        # Factor 4 – OBI
        if current_obi > 0.1:  score += 5
        elif current_obi < -0.1: score -= 5

        # Factor 5 – Funding sanity check
        if score > 65 and current_funding > 0.0005:
            score -= 15

        return max(0, min(100, int(score)))

    # ------------------------------------------------------------------
    def plot_chart(self, df: pd.DataFrame, tf: str, score: int,
                   funding: float, obi: float) -> str:
        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(14, 10),
            gridspec_kw={'height_ratios': [2, 1]},
            sharex=True,
            facecolor='#121212',
        )
        ax1.set_facecolor('#121212')
        ax2.set_facecolor('#121212')

        # ---- Panel superior: Precio + Whales ----
        ax1.plot(df['ts'], df['c_s'], color=COLORS['price'], linewidth=2, label='Spot Price')

        trend_up = df['c_s'].iloc[-1] > df['c_s'].iloc[0]
        shade_col = COLORS['bull_bg'] if trend_up else COLORS['bear_bg']
        ax1.fill_between(df['ts'], df['c_s'].min(), df['c_s'].max(),
                         color=shade_col, alpha=0.15)

        whales = df[df['is_whale']]
        if not whales.empty:
            sizes = (whales['whale_z'].clip(lower=0) * 40).fillna(20)
            ax1.scatter(whales['ts'], whales['c_s'],
                        s=sizes, color=COLORS['whale'],
                        edgecolors='white', alpha=0.7,
                        label='Whale / Iceberg', zorder=5)

        ax1.set_title(
            f'SPOTDIFF ÉLITE  •  {self.symbol}  •  {tf.upper()}',
            fontsize=16, color='gold', fontweight='bold',
        )
        ax1.legend(loc='upper left', facecolor='#1A1A1A', edgecolor='#555555')
        ax1.grid(True, color='#333333', linestyle='--', linewidth=0.5)
        ax1.tick_params(colors='#AAAAAA')

        # ---- Panel inferior: CVD / Flow ----
        ax2.plot(df['ts'], df['cvd_s_z'], color=COLORS['spot'],
                 linewidth=2.5, label='Spot Flow (CVD)')
        ax2.plot(df['ts'], df['cvd_f_z'], color=COLORS['fut'],
                 linewidth=1.5, linestyle='--', alpha=0.7, label='Futures Flow')
        ax2.fill_between(
            df['ts'], df['cvd_s_z'], df['cvd_f_z'],
            where=(df['cvd_s_z'] > df['cvd_f_z']),
            color=COLORS['spot'], alpha=0.2, label='Acumulación Institucional',
        )
        ax2.axhline(0, color='white', linewidth=0.5, alpha=0.5)
        ax2.set_ylabel('Flow Z-Score', color='#AAAAAA')
        ax2.legend(loc='upper left', facecolor='#1A1A1A', edgecolor='#555555')
        ax2.grid(True, color='#333333', linestyle='--', linewidth=0.5)
        ax2.tick_params(colors='#AAAAAA')

        # ---- HUD ----
        last_signal = 'WHALE DETECTED' if df['is_whale'].iloc[-1] else 'NORMAL'
        hud_text = (
            f"FLOW INDEX: {score}/100\n"
            f"FUNDING:    {funding * 100:.4f}%\n"
            f"OBI:        {obi:+.1%}\n"
            f"LAST SIG:   {last_signal}"
        )
        hud_color = '#004D40' if score > 60 else '#3E2723' if score < 40 else '#1A1A1A'
        props = dict(boxstyle='round', facecolor=hud_color, alpha=0.92, edgecolor='gold')
        ax2.text(
            0.02, 0.95, hud_text,
            transform=ax2.transAxes, fontsize=11,
            verticalalignment='top', bbox=props,
            color='white', fontfamily='monospace', fontweight='bold',
        )

        plt.tight_layout()
        filename = f'spotdiff_{self.symbol.lower()}_{tf}.png'
        plt.savefig(filename, dpi=200, facecolor='#121212', bbox_inches='tight')
        plt.close(fig)
        return filename

    # ------------------------------------------------------------------
    def generate_caption(self, tf: str, score: int, df: pd.DataFrame,
                          funding: float, obi: float) -> str:
        last_price = df['c_s'].iloc[-1]
        div        = df['divergence'].iloc[-1]

        if score > 70:
            trend  = "🟢 **FUERTE ALZA INSTITUCIONAL**"
            advice = "El flujo Spot domina a Futuros. Absorción detectada."
        elif score < 40:
            trend  = "🔴 **DISTRIBUCIÓN / VENTA**"
            advice = "Futuros lideran la caída. Cuidado con longs."
        else:
            trend  = "🟡 **NEUTRAL / RANGO**"
            advice = "Mercado sin dirección clara. Esperar confirmación."

        funding_alert = ""
        if funding > 0.0005 and score < 50:
            funding_alert = "\n⚠️ **ALERTA:** Funding alto con flujo débil. Posible reversión."

        return (
            f"{trend}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 **Activo:** {self.symbol} ({tf.upper()})\n"
            f"💰 **Precio:** ${last_price:,.2f}\n"
            f"📊 **Institutional Score:** `{score}/100`\n"
            f"🌊 **Spot vs Fut:** `{'Spot > Fut' if div > 0 else 'Fut > Spot'}`\n"
            f"💸 **Funding:** `{funding * 100:.4f}%`\n"
            f"📖 **Insight:** {advice}{funding_alert}"
        )


# ----------------------------------------------------------------------
async def main(symbol: str):
    bot = SpotDiffElite(symbol)

    try:
        data_bundle = await bot.fetch_data()
    except Exception as exc:
        print(f"[ERROR] No se pudo conectar al exchange: {exc}")
        return []

    output_files = []

    for tf in ('1d', '1w'):
        spot_raw = data_bundle[tf]['spot']
        fut_raw  = data_bundle[tf]['fut']

        if len(spot_raw) < 10 or len(fut_raw) < 10:
            print(f"[SKIP] Datos insuficientes para {tf} ({len(spot_raw)} spot / {len(fut_raw)} fut)")
            continue

        try:
            df = bot.calculate_metrics(spot_raw, fut_raw)

            ob   = data_bundle[tf]['ob']
            bids = sum(b[1] for b in ob.get('bids', [])[:10])
            asks = sum(a[1] for a in ob.get('asks', [])[:10])
            obi  = (bids - asks) / (bids + asks + 1e-8)

            score   = bot.get_institutional_score(df, data_bundle[tf]['funding'], obi)
            img     = bot.plot_chart(df, tf, score, data_bundle[tf]['funding'], obi)
            caption = bot.generate_caption(tf, score, df, data_bundle[tf]['funding'], obi)

            output_files.append({'image': img, 'caption': caption})
            print(f"✅ [{tf.upper()}] Score {score}/100  →  {img}")

        except Exception as exc:
            print(f"[ERROR] Procesando {tf}: {exc}")

    return output_files


# ----------------------------------------------------------------------
if __name__ == '__main__':
    symbol_arg = sys.argv[1].strip().upper() if len(sys.argv) > 1 else 'BTC'
    results = asyncio.run(main(symbol_arg))

    for item in results:
        print(f"\n📸 PHOTO: {item['image']}")
        print(f"📝 CAPTION:\n{item['caption']}\n")
