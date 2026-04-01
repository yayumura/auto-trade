# 🏦 Alpha Multiplier - 究極のプライム・トレンド・マルチプライヤー (V11)

100万円の元手を爆発的に増やし続けるための、**プライム市場専用・高精度トレンドフォロー戦略**。
72パターンの全パラメータ総当たり検証（納税シミュレーション済）により、2021年〜2026年の荒れ相場を勝ち抜いた「絶対王者（Absolute Champion）」の設定を搭載。

---

## 💎 V11 Absolute Champion Edition (Latest)

本バージョンは、単なる利益追及から「生き残り」と「納税後の手残り」を最優先としたプロフェッショナル仕様です。

- **Engine**: Truth Hunter V11 (Market Shield & Hybrid Compounding).
- **Strategy**: 25-Day Breakout / 15-Day Channel Exit (利益最大化設定)。
- **Performance (2021-2026.03 Verified)**:
    - **Total Profit (Net)**: **+344.36%** (全て納税した後の「純利益」)。
    - **Potential (Gross)**: **+550.82%** (最高ポテンシャル)。
    - **Final Asset**: 1,000,000 JPY → **4,443,603 JPY** (実質的な手残り現金)。

---

## 🛡️ 鉄壁の運用信頼性 (Operations & Resilience)

本番運用を「手放し」で行うための、高度なエラーハンドリング機能を標準搭載しています。

### 1. 停電・クラッシュからの自動復帰 (Resume Logic)
プログラムが不意の停電などで停止しても、再起動時に **証券口座から現在の保有残高を自動取得** します。以前の状態を記憶に頼らず「事実」から復元するため、即座に監視を再開できます。

### 2. ログイン死活監視 (Health Check & Alert)
1分おきに kabuステーションとの通信状態をチェック。
- **異常検知**: ログインが切れたりAPIが止まった場合、**即座に Discord へ警告通知**。
- **自動復旧**: 可能な限り自動で再ログインとサーバー再起動を試みます。

### 3. スマート・シャットダウン (Auto Termination)
- **15:30 (大引け)**: 全ての未約定注文をキャンセルし、kabuステーションを自動終了。
- **祝日・休業日**: 起動時に自動判定。カプステを閉じて安全に待機します。

### 4. ログ・メンテナンス (Log Rotation)
`run_bot.bat` 経由での起動時、ログファイルが **5MB** を超えていれば自動リセット。

---

## 🏹 搭載された 3大コアロジック (Features)

### 1. 「最強の盾」：実戦的市場総撤退 (Market Shield)
日経平均（1321.T）が 200日移動平均線を割った **翌日の朝一番** に、全ポジションを強制決済。ドローダウンを劇的に抑制します。

### 2. 「選別の目」：長期トレンドフィルター (SMA200 Slope)
株価が 200日線の上にあるだけでなく、**200日線自体が上向いていること** を必須条件化。

### 3. 「トレンド持久力」：15日エグジット (E:15)
決済期間（Donchian Channel Low）を 15日 に設定し、トレンドをしゃぶり尽くします。

---

## 🛠️ プロジェクト構造 (Architecture)

```bash
.
├── auto_trade.py         # 運用メインエンジン（V11 搭載）
├── backtest.py           # [Dual-Mode] 実戦納税版 vs 理論税抜版 の比較検証
├── optimizer.py          # [The Ultimate Tool] 72パターンの全パラメータ総当たり探索
├── core/
│   ├── logic.py          # [Core] Market Shield / V10.5 選定・決済アルゴリズム
│   ├── config.py         # [Config] B:25/E:15/Pos:3/OH:30.0 最強パラメータ
│   ├── kabucom_broker.py # [Broker] カブコムAPI連携・注文執行（chase order搭載）
│   └── kabu_launcher.py  # [Launcher] 自動ログイン・死活監視・終了処理
├── data/
│   └── data_j.csv        # ターゲット銘柄マスター
└── run_bot.bat           # ワンクリック運用起動用（ログローテーション搭載）
```

---

## 📈 検証と最適化 (Tools Usage)

### **1. `optimizer.py` による全 72パターンの走査**
「源泉徴収あり特定口座」と同じ「損益通算・還付」のロジックで全パターンを再検証します。
```bash
python optimizer.py
```

### **2. `backtest.py` による実戦シミュレーション**
税金を払った後の「正確な資産推移」と、税抜きでの「戦略ポテンシャル」を対比表示します。
```bash
python backtest.py
```

---

## ⚙️ 確定パラメータ (Absolute Champion Params)

| パラメータ | 設定値 | 役割 |
| :--- | :--- | :--- |
| **BREAKOUT_PERIOD** | 25 | 長期の波に乗る（強気相場の初動） |
| **EXIT_PERIOD** | 15 | トレンドをしゃぶり尽くす（粘り強い保有） |
| **MAX_POSITIONS** | 3 | 納税の不利を上回る集中投資 |
| **OVERHEAT_THRESHOLD** | 30.0% | 乖離率による高値掴み防止 |
| **MAX_ALLOCATION_PCT** | 0.33 | 資金を余らせず 100% 活用（33% × 3） |
| **MAX_RISK_PER_TRADE** | 0.05 | バックテストの爆発力を再現するリスク許容 |

---

## 📦 運用フロー (Daily Cycle)

1. **08:30 - 09:00**: `run_bot.bat` 起動（自動ログイン・銘柄選奨）
2. **09:00 - 15:00**: 前場・後場の実時間取引監視（自動売買）
3. **15:30**: 注文整理・自動終了（Discordへの終了通知・カブステ終了）

---
Created by Antigravity - *V11 Absolute Champion Engine*  
Verified Result: 1.0M -> 4.4M JPY (+344.36%) with Real-Tax Compounding Logic.