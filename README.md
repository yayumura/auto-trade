# 🚀 Auto-Trade — V152.0 Profit Pursuit (利益追求型・究極設定)

日本株市場を対象とした、**高期待値・逆張り（Mean Reversion）特化型の自律投資システム**です。
「最強のリーダー銘柄だけが、一時的に売られすぎた瞬間を狩る」というソブリン（主権者）の投資哲学を具現化しています。

荒れた相場環境においても資産を守り抜く「Aegis（エッジス）防御システム」を搭載しつつ、最適化された窓開け制限とレバレッジ3.0倍の採用により、**5年間で +565.26%（勝率 57.60%）** という異次元のパフォーマンスを達成しました。

---

## 🌟 システムの主な機能 (Features)

*   **Sovereign Selection (リーダー選別)**: 100日間の絶対騰落率をベースに、市場平均を凌駕する「真のリーダー銘柄」4社のみを厳選。
*   **High-Conviction Mean Reversion**: RSI(2) を極限まで研ぎ澄まし、暴落時の「恐怖の底」を精密に狙い撃ちます。
*   **Aegis 防御システム**: 月間ドローダウンに応じて損切りラインを自動調整。-5%（注意）/-10%（危険）ゾーンで防御力を動的に高めます。
*   **Trend Snap プロトコル**: インデックスが短期的な崩れを見せた際、瞬時に「逃げ」の決済しきい値を調整し、利益を確保。
*   **完全自律自動運用**: `run_imperial_oracle.bat` により、データの取得から Kabucom API を通じた盤石な執行まで一気通貫で完結。

---

## 💎 バックテスト実績 (V152.0 Profit Pursuit / 2021.04〜2026.04)

| V152.0 The Absolute Apex | 投資実績 |
|:---|---:|
| **総利益率** | **+565.26%** |
| **最終資産** | **6,652,649 円** |
| **勝率** | **57.60%** |
| **総取引回数** | 375 回 (精鋭集中投資) |
| 初期資産 | 1,000,000 円 |
| 期間 | 2021年4月5日 〜 2026年4月3日 |

---

## 🏗️ リポジトリ主要構成

```
auto-trade/
├── core/
│   ├── config.py         # パラメータ (ATR係数、ポジション数等) の管理
│   ├── logic.py          # V152.0 コアロジック (RSI逆張り & 絶対力 RS)
│   ├── kabucom_broker.py # auカブコム証券 API 執行エンジン
│   └── sim_broker.py     # デバッグ用シミュレーター
├── backtest.py           # 核心シミュレーションエンジン (Sovereign Logic)
├── jp_backtest.py        # パフォーマンス検証・レポート出力
├── jp_optimizer.py       # パラメータ最適化 (グリッドサーチ)
├── auto_trade.py         # リアルタイム執行ボット
└── run_imperial_oracle.bat # 運用スタートアップスイッチ
```

---

## 🛠️ デプロイ・セットアップ手順

### 1. 動作環境とライブラリのインストール
Python 3.10以上が必要です。
```bash
pip install -r requirements.txt
```

### 2. 環境変数 (.env) の完全な設定
プロジェクトのルートディレクトリに `.env` という名前のファイルを作成し、以下の全項目を設定してください。

```ini
# ==== auカブコム証券 API設定 ====
TRADE_MODE=KABUCOM_TEST         # SIM (仮想資金), KABUCOM_TEST (検証API), KABUCOM_LIVE (本番API)
KABUCOM_API_PASSWORD=xxxxxxxx   # Kabuステーションの「API設定」で自身で決めたパスワード
KABUCOM_LOGIN_PASSWORD=yyyyyyyy # Kabuステーション自体のログインパスワード
KABUCOM_ACCOUNT_TYPE=4          # 口座種別 (2: 一般, 4: 特定口座)

# ==== JQuants (JPX公式データ) 設定 ====
JQUANTS_REFRESH_TOKEN=zzz...    # JQuants APIから取得したリフレッシュトークン

# ==== AI ニュース定性監査用 APIキー ====
GEMINI_API_KEY=AIzaSy...        # Google Gemini APIキー (メイン監査用)
GEMINI_MODEL=gemini-2.5-flash   # 推奨モデル
GROQ_API_KEY=gsk_xxx...         # Groq APIキー (フェイルオーバー/予備用)
GROQ_MODEL=llama-3.3-70b-versatile

# ==== 通知・デバッグ機能 ====
DISCORD_WEBHOOK_URL=https://... # 注文発生時やエラー時のDiscord通知用URL
DEBUG_MODE=true                 # trueにすると詳細なログを出力
```

### 3. 初期データの構築 (初回のみ)
株価データのキャッシュを初めて構築するため、以下のコマンドを手動で実行します。
```bash
python jp_jquants_fetcher_v2.py
```

---

## 📅 本番運用 (オーケストレーター実行)

日々の運用は、コマンドを個別に叩く必要はありません。
**`run_imperial_oracle.bat`** をダブルクリックするだけで、1日の全フローがシームレスに連続実行されます。

### 🔄 BATの実行フロー (シリアル実行)
1. **🌞 STEP 1: データ更新** (`jp_jquants_fetcher_v2.py`)
2. **🤖 STEP 2: 自律トレード監視** (`auto_trade.py`)
   - 独自の超高速スキャンで銘柄を抽出し、**15:30の市場終了時間まで** リアルタイムの相場監視・自動売買注文・利確損切のトレイリングを継続します。
3. **📊 STEP 3: オフマーケット監査** (`jp_backtest.py`)
   - 15:30にボットが安全に終了した直後、直近5年のバックテストが自動で走ります。

### ⏰ Windows タスクスケジューラでの完全自動化設定
毎日手動で起動する手間を省くため、Windowsタスクスケジューラを利用して全自動化します。
1. タスクスケジューラを開き、「基本タスクの作成」をクリック。
2. 名前: `Imperial Oracle Auto-Trade`
3. トリガー: **「毎日」** 時間を **「午前 8:30」** に設定。（※8:30〜9:00 の間に起動させれば間に合います）
4. 操作: **「プログラムの開始」**
5. プログラム/スクリプト: `C:\Users\yayum\git_work\auto-trade\run_imperial_oracle.bat` を参照して指定。
   - **(重要)** 「開始（オプション）」に作業ディレクトリ（例: `C:\Users\yayum\git_work\auto-trade`）を必ず指定してください。
6. 設定完了。PCとKabuステーションが起動していれば、毎朝8:30に自動で発進します。

---

## 📊 開発・テスト用スクリプトの実行方法

ご自身でロジックをカスタマイズしたり、バックテストの数値をチューニングしたい場合は、以下のスクリプトを直接実行可能です。

### 1. バックテストの実行 (`jp_backtest.py`)
現在のロジックとパラメータが、過去5年間でいかに機能するかを数秒で再現し、最終資産額と勝率をグラフ/コンソールに出力します。
```bash
python jp_backtest.py
```

### 2. パラメータのオプティマイザ (`jp_optimizer.py`)
さらなるアルファ（超過収益）を求めて、「SMA期間」や「ATR利確倍率」などを自動で総当たり探索し、最もリターンの高いパラメータの組み合わせを発見します。
```bash
python jp_optimizer.py
```
> 見つかった最適なパラメータは `core/config.py` 内の変数（`TARGET_PROFIT_MULT` や `ATR_STOP_LOSS` 等）に反映させてください。

---
*Last updated: 2026-04-12 — V152.0 Profit Pursuit (The Absolute Apex)*  
*Profit Magnitude: +565.26% (Diamond Standard V152.0)*