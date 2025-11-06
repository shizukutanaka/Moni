# Moni システムモニター

Moni は、個人利用を想定した総合システム監視ソフトウェアです。リソース監視、最適化、セキュリティ保護を単一のワークフローで提供し、長期運用に耐える堅牢性と保守性を備えています。

## 多言語サポート実装ガイド

### 基本アーキテクチャ

1. **国際化 (i18n) レイヤー**
   - テキストリソースをコードから分離
   - Unicode (UTF-8) を標準エンコーディングとして採用
   - ロケールに依存するデータ処理の抽象化

2. **多言語リソース管理**
   - JSON ベースの翻訳ファイルを採用
   - 言語ごとのリソースファイルを `resources/locales/` 以下に配置
   - 例: 
     - `resources/locales/ja.json`
     - `resources/locales/en.json`
     - `resources/locales/zh-CN.json`

### 実装のベストプラクティス

#### 1. テキストの外部化
```python
# 推奨される実装例
from flask_babel import _

# ハードコードされた文字列の代わりに
# 翻訳キーを使用
welcome_message = _('welcome_message')
```

#### 2. 数値・日付・通貨のフォーマット
```python
from babel.dates import format_date, format_datetime
from babel.numbers import format_currency

# 日付のローカライズ
localized_date = format_date(date_obj, locale=user_locale)

# 通貨のフォーマット
formatted_currency = format_currency(amount, 'JPY', locale=user_locale)
```

#### 3. 多言語対応データ構造
```json
// resources/locales/ja.json
{
  "monitoring": {
    "cpu_usage": "CPU使用率: {percentage}%",
    "memory_usage": "メモリ使用量: {used}GB / {total}GB"
  },
  "alerts": {
    "high_cpu": "CPU使用率が{threshold}%を超えています"
  }
}
```

### 技術的考慮事項

1. **文字列補間**
   - 可変部分を明示的にマークアップ
   - プレースホルダーには意味のある名前を使用

2. **動的コンテンツ**
   - 翻訳が必要な動的コンテンツには翻訳キーを使用
   - ユーザー生成コンテンツは翻訳APIと統合

3. **RTL言語サポート**
   - アラビア語やヘブライ語などの右から左への記述に対応
   - CSSの `direction` プロパティを動的に制御

### パフォーマンス最適化

1. **翻訳の遅延読み込み**
   - 必要に応じて言語リソースを動的に読み込み
   - 翻訳キャッシュの実装

2. **バンドル最適化**
   - 言語ごとのチャンク分割
   - 不要な翻訳のバンドルからの除外

### ローカライゼーションツールチェーン

1. **翻訳管理システム**
   - Lokalise や Transifex の統合
   - 翻訳メモリと用語集の活用

2. **自動翻訳**
   - DeepL や Google Translate API との連携
   - 人間による校正ワークフローの構築

### テスト戦略

1. **ユニットテスト**
   - 翻訳キーの存在確認
   - プレースホルダーの整合性チェック

2. **UIテスト**
   - テキストの折り返しとレイアウトの検証
   - ローカライズされた日付/数値の表示確認

### 展開とメンテナンス

1. **バージョン管理**
   - 翻訳リソースのバージョン管理
   - 変更履歴の追跡

2. **継続的インテグレーション**
   - 翻訳の自動更新パイプライン
   - 翻訳品質チェックの自動化

---

## 主な特徴

### セキュリティとプライバシー

- プライバシーガードによるネットワーク、ファイル、クリップボード、カメラ、マイクの監視
- 広告およびトラッキングサーバーへのアクセス検知と遮断
- 機密データ参照の記録と警告、監査可能なログ
- HTTPS 通信の厳格な許可リスト制御と TLS 1.3 による暗号化通信

### 自動システム最適化

- メモリ開放、スタートアップ管理、プロセス優先度調整
- 一時ファイル削除、SSD TRIM、自動 DNS キャッシュクリア
- ネットワーク品質計測と履歴データの保存

### リアルタイム監視

- CPU、GPU、メモリ、ストレージ、ネットワーク、温度、ファン速度を統合表示
- グラフ化された履歴としきい値ベースのアラート
- プロセス別のリソース使用状況と接続情報の確認

### 利用シナリオに応じたプロファイル

- ゲーミング、開発、録画、最小構成のプリセット
- テーマ、ウィンドウ配置、更新間隔の柔軟な調整
- グローバルホットキーと自動化スケジュール

---

## インストール

### 前提条件

- Python 3.10 以上
- Windows 10/11、macOS 12 以降、Ubuntu 20.04 以降
- メモリ 4GB 以上（8GB 以上を推奨）

### 手順

```bash
# 1. リポジトリを取得
cd Moni

# 2. 仮想環境を用意
python -m venv venv

# 3. 仮想環境を有効化
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 4. 依存関係を導入
pip install --upgrade pip
pip install -r requirements.txt

# 5. 開発用にインストール
pip install -e .

# 6. 起動
moni
```

Dockerfile と docker-compose.yml も同梱しており、コンテナ環境での検証が可能です。

---

## 基本的な使い方

### 起動コマンド

```bash
moni                     # 標準設定で起動
moni --profile gaming    # ゲーミング向けプロファイル
moni --secure            # 暗号化設定を強制
moni --mode daemon       # バックグラウンド実行
```

### 初期セットアップ

1. オーバーレイを好きな位置にドラッグして固定します。
2. 右クリックメニューからテーマとプロファイルを選択します。
3. `config.json` でメトリクス、アラート、ログの制御を行います。

---

## 課金モデル（Stripe サブスクリプション）

Moni は長期的なセキュリティ改善のため、サブスクリプション型の課金モデルを採用しています。Stripe を利用することで、購入手続きや更新管理を安全に運用できます。

### サービス階層

- **Essential**
  コア監視ダッシュボードと週次セキュリティベースラインを提供します。
- **Enterprise**
  侵入検知の強化、RBAC 自動化、コンプライアンスレポート出力を追加します。

### 必須環境変数

課金 API を起動する前に以下の環境変数を設定してください。`MONI_STRIPE_TIER_*` は `price_id|説明|機能1,機能2|interval|trial_days` 形式です。

```bash
export MONI_STRIPE_SECRET_KEY=sk_live_xxx
export MONI_STRIPE_PUBLISHABLE_KEY=pk_live_xxx
export MONI_STRIPE_WEBHOOK_SECRET=whsec_xxx
export MONI_STRIPE_SUCCESS_URL=https://example.com/moni/billing/success
export MONI_STRIPE_CANCEL_URL=https://example.com/moni/billing/cancel
export MONI_STRIPE_CURRENCY=usd
export MONI_STRIPE_TIER_ESSENTIAL=price_essential|Essential Monitoring|Dashboards,Weekly Baselines|month|0
export MONI_STRIPE_TIER_ENTERPRISE=price_enterprise|Enterprise Security|RBAC,Compliance Exports|month|14
```

### Billing API の起動

```bash
moni-billing-api
# または
uvicorn moni.billing_api:app --host 0.0.0.0 --port 8080
```

- **ヘルスチェック**: `GET /health`
- **料金プラン一覧**: `GET /tiers`
- **チェックアウト生成**: `POST /checkout`（例: `{ "price_id": "price_...", "email": "user@example.com" }`）
- **サブスクリプション参照**: `GET /subscription/{customer_id}`
- **Webhook エンドポイント**: `POST /webhook`

Stripe ダッシュボードから `customer.subscription.created`、`customer.subscription.updated`、`customer.subscription.deleted` を `https://<billing-host>/webhook` に送信してください。

### 運用上の推奨事項

- **専用サービスとして運用**: `moni-billing-api` を HTTPS リバースプロキシ配下で稼働させ、TLS 終端を行います。
- **永続化**: サブスクリプション情報は `~/.config/moni/stripe_subscriptions.json` に保存されます。冗長構成が必要な場合はデータベース化を検討してください。
- **キーのローテーション**: Webhook シークレットと Stripe 秘密鍵は四半期ごとに更新し、環境変数を更新後 Billing API を再起動してください。

---

## セキュリティ機能

### プライバシーガード

```python
from moni.privacy_guard import get_privacy_guard

guard = get_privacy_guard()
result = guard.scan_system()
print(guard.get_privacy_report())
```

- 検出したリスクはスコア化され、監査ログに記録されます。
- クリップボード、機密ファイル、ネットワーク接続を統合管理します。

### ネットワーク監視

- `network_monitor.py` が接続状況、品質、VPN/プロキシ状態を集約
- VPN やプロキシを検知した場合はレポートに明示
- HTTPS 通信は `_is_allowed_https_target()` により許可されたエンドポイントのみ使用

### 標準セキュリティポリシー

- AES-256-GCM による設定暗号化
- TOTP ベースの二要素認証オプション
- HMAC 署名付き監査ログ
- レートリミットによる DoS 防止

詳細は `SECURITY.md` を参照してください。

---

## システム最適化

```python
from moni.system_optimizer import get_system_optimizer

optimizer = get_system_optimizer()
results = optimizer.full_optimization()
for name, outcome in results.items():
    print(f"{name}: {outcome.message}")
```

- メモリ、ディスク、ネットワークを対象にした自動最適化
- スケジューラにより定期実行を構成可能
- 最適化レポートを JSON で取得し、履歴を追跡できます。

---

## 設定例

```json
{
  "overlay": {
    "visible": true,
    "refresh_interval_ms": 1000,
    "opacity": 0.85,
    "show_sparklines": true
  },
  "alerts": {
    "enabled": true,
    "thresholds": {
      "cpu_percent": 85.0,
      "memory_percent": 90.0,
      "gpu_temperature_celsius": 85.0,
      "battery_percent": 20.0
    }
  },
  "privacy_guard": {
    "enabled": true,
    "auto_scan_interval_minutes": 30
  }
}
```

---

## プロファイル

- **Gaming**: 高頻度更新、GPU 優先指標、通知最小化
- **Development**: プロセス別メトリクス、ログ収集、ディスク I/O 監視
- **Recording**: CPU、メモリ、ディスク使用を重点的に表示
- **Minimal**: CPU、メモリ、稼働時間のみを低負荷で表示

各プロファイルは `config.json` でカスタマイズでき、用途に応じて切り替え可能です。

---

## 高度な機能

- 自動化スケジュール: プライバシースキャンや最適化を定期実行
- カスタムルール: 監視対象ドメインやファイルパターンを追加
- API 連携: Python スクリプトから最適化や監視の開始を制御

---

## レポートとエクスポート

- `moni --mode export --export-format json --export-file metrics.json`
- CSV、HTML エクスポートに対応
- `network_monitor.export_network_data()` により接続情報と品質指標をまとめて保存

すべてのエクスポートはサンドボックス化されたディレクトリに保存され、サイズ上限とローテーションが適用されます。

---

## テーマと表示

- Light、Dark、Ocean Blue、Forest Green、High Contrast のプリセットテーマ
- カスタムテーマは `config.json` で色とフォントサイズを指定
- マルチモニター配置とコンパクト表示をサポート

---

## ホットキー

- `Ctrl+Shift+M`: オーバーレイ表示切り替え
- `Ctrl+Shift+P`: プライバシースキャン
- `Ctrl+Shift+O`: システム最適化
- `Ctrl+,`: 設定画面
- `F5`: メトリクス更新
- `Ctrl+Q`: アプリケーション終了

---

## トラブルシューティング

- オーバーレイが表示されない場合は、ホットキーと `overlay.visible` 設定を確認
- GPU 情報が取得できない場合は NVIDIA ドライバーと NVML の初期化を確認
- 高負荷時は更新間隔、履歴件数、グラフ表示を調整
- 権限エラーが出る場合は管理者権限または sudo で再実行

ケース別の推奨設定は運用ガイドラインに沿って整備してください。

---

## サポート

- バグ報告は GitHub Issues へ、OS、Python バージョン、再現手順、ログを含めて提出してください。
- セキュリティ脆弱性は `SECURITY.md` に記載した非公開チャネルを利用してください。

---

## ライセンス

MIT License。詳細は `LICENSE` を参照してください。

---

## 付記

- `pytest` によるテストスイート、`ruff` と `mypy` による静的解析ツールチェーンを同梱
- Docker および仮想環境による再現性の高いデプロイメントを想定
- 設定ディレクトリ (`~/.config/moni/` または `%APPDATA%\moni\`) にログとエクスポートを保存します

運用環境で利用する場合は、暗号鍵の定期ローテーションと構成バックアップを実施し、監査ログの保全ポリシーを整備してください。

### 個人利用向け最適化

- **ゲームモード検出**: フルスクリーンゲーム時の自動最適化
- **生産性トラッキング**: アクティブ時間、アイドル時間の自動追跡
- **プロファイル**: ゲーミング、開発、録画、最小限の4種類
- **カスタマイズ**: テーマ、配置、透明度、すべて自由に調整

---

## インストール

### 必要要件

- Python 3.10以上
- Windows 10/11、macOS 12+、Ubuntu 20.04+
- 4GB RAM（推奨: 8GB）

### クイックインストール

```bash
# 1. リポジトリをクローンまたはダウンロード
cd Moni

# 2. 仮想環境を作成
python -m venv venv

# 3. 仮想環境を有効化
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 4. 依存関係をインストール
pip install --upgrade pip
pip install -r requirements.txt

# 5. Moniをインストール
pip install -e .

# 6. 起動！
moni
```

---

## 基本的な使い方

### 起動

```bash
# デフォルト設定で起動
moni

# ゲーミングプロファイルで起動
moni --profile gaming

# セキュアモードで起動（暗号化有効）
moni --secure
```

### 初回セットアップ

1. オーバーレイが画面右上に表示されます
2. ドラッグして好きな位置に移動
3. 右クリックで設定メニューを開く
4. テーマとプロファイルを選択

---

## セキュリティ機能

### プライバシーガード

#### ネットワーク保護

```python
from moni.privacy_guard import get_privacy_guard

guard = get_privacy_guard()

# システムスキャン実行
results = guard.scan_system()

# レポート表示
print(guard.get_privacy_report())
```

**出力例:**
```
==========================================================
MONI PRIVACY GUARD - セキュリティレポート
==========================================================
スキャン日時: 2025-10-06T15:30:00
総合リスクレベル: LOW
リスクスコア: 15.0/100

【ネットワーク監視】
  総接続数: 45
  ブロック数: 3  ← 広告・トラッキングをブロック
  監視プロセス数: 12

【ファイルアクセス監視】
  機密ファイルアクセス: 0 件

【クリップボード監視】
  機密データ検出: 1 件
  検出率: 12.5%

【デバイスアクセス監視】
  ✓ カメラ: 未使用
  ✓ マイク: 未使用
==========================================================
```

#### 自動ブロック対象

**トラッキングサーバー**
- Google Analytics, DoubleClick
- Facebook Pixel, Facebook Connect
- 広告配信（Criteo, Outbrain, Taboola）

**機密ファイル保護**
- SSH鍵 (/.ssh/)
- GPG鍵 (/.gnupg/)
- 暗号通貨ウォレット (wallet.dat)
- パスワードデータベース (*.kdbx)
- 秘密鍵 (*.key, *.pem)

**クリップボード監視**
- パスワード
- クレジットカード番号
- APIキー・トークン
- 秘密鍵

### システム最適化

```python
from moni.system_optimizer import get_system_optimizer

optimizer = get_system_optimizer()

# 完全最適化実行
results = optimizer.full_optimization()

# 結果表示
for category, result in results.items():
    print(f"{category}: {result.message}")
```

**出力例:**
```
memory: メモリ使用率: 78.5% → 65.2% (13.3% 削減)
temp_files: 234 ファイル削除、1,245.3 MB 解放
dns_cache: DNSキャッシュをクリア
```

---

## 設定

### config.json（推奨設定）

```json
{
  "overlay": {
    "visible": true,
    "refresh_interval_ms": 1000,
    "opacity": 0.85,
    "compact_mode": false,
    "show_sparklines": true,
    "animate_transitions": true
  },
  "alerts": {
    "enabled": true,
    "thresholds": {
      "cpu_percent": 85.0,
      "memory_percent": 90.0,
      "gpu_temperature_celsius": 85.0,
      "battery_percent": 20.0
    },
    "notifications": {
      "play_sound": true,
      "sound_volume": 0.5,
      "minimize_gaming_mode": true
    }
  },
  "privacy_guard": {
    "enabled": true,
    "auto_scan_interval_minutes": 30,
    "network_protection": {
      "block_trackers": true,
      "block_ads": true
    },
    "file_protection": {
      "monitor_sensitive_files": true,
      "alert_on_access": true
    },
    "clipboard_protection": {
      "monitor_clipboard": true,
      "alert_on_sensitive_data": true
    },
    "device_protection": {
      "monitor_camera": true,
      "monitor_microphone": true
    }
  },
  "system_optimizer": {
    "enabled": true,
    "auto_optimize_interval_hours": 6,
    "memory_optimization": {
      "auto_cleanup": true
    },
    "disk_optimization": {
      "auto_clean_temp": true,
      "ssd_trim": true
    }
  }
}
```

---

## プロファイル

### ゲーミング

```json
{
  "profile": "gaming",
  "refresh_interval_ms": 500,
  "compact_mode": true,
  "metrics": ["cpu_usage", "gpu_usage", "gpu_temperature", "memory_usage"]
}
```

**特徴:**
- 超高速更新（500ms）
- GPU優先表示
- ゲーム検出で通知最小化

### 開発

```json
{
  "profile": "development",
  "metrics": [
    "cpu_usage", "memory_usage", "disk_io", "network_io",
    "top_cpu_processes", "top_memory_processes"
  ]
}
```

**特徴:**
- 包括的な監視
- プロセス詳細表示
- ログ記録有効

### 最小限

```json
{
  "profile": "minimal",
  "metrics": ["cpu_usage", "memory_usage", "system_uptime"],
  "refresh_interval_ms": 3000
}
```

**特徴:**
- 最軽量
- 基本メトリクスのみ
- 低リソース消費

---

## 高度な機能

### 自動化スケジュール

```python
# config.json
{
  "automation": {
    "privacy_scan": {
      "enabled": true,
      "interval_minutes": 30
    },
    "system_optimization": {
      "enabled": true,
      "interval_hours": 6,
      "actions": ["memory", "disk", "network"]
    }
  }
}
```

### カスタムルール

```python
# privacy_guard カスタマイズ
guard = get_privacy_guard()

# 信頼済みドメイン追加
guard.network_monitor.SAFE_DOMAINS.add("mytrustedapp.com")

# カスタム機密ファイルパターン
guard.file_monitor.SENSITIVE_PATTERNS.append(r'.*\.secret')
```

### プログラマティック制御

```python
import threading
import time

def auto_protect():
    guard = get_privacy_guard()
    optimizer = get_system_optimizer()

    while True:
        # 30分ごとにスキャン
        results = guard.scan_system()

        # リスクが高ければ最適化
        if results['overall_risk'] != 'low':
            optimizer.full_optimization()

        time.sleep(1800)

# バックグラウンドで実行
thread = threading.Thread(target=auto_protect, daemon=True)
thread.start()
```

---

## レポートとエクスポート

### プライバシーレポート

```bash
# レポート生成
moni --privacy-report

# JSONエクスポート
moni --export-privacy-log privacy_report.json
```

### システム最適化レポート

optimizer = get_system_optimizer()
print(optimizer.get_optimization_report())
4. **Forest Green** - 自然な緑系
5. **High Contrast** - 高コントラスト（アクセシビリティ）

### カスタムテーマ作成

```json
{
  "themes": {
    "my_custom": {
      "name": "マイカスタムテーマ",
      "colors": {
        "background": "#1a1a1a",
        "text": "#ffffff",
        "primary": "#ff6b6b",
        "success": "#51cf66",
        "warning": "#ffd43b",
        "error": "#ff6b6b"
      },
      "font_size": 11
    }
  }
}
```

---

## ホットキー

- `Ctrl+Shift+M` - オーバーレイ表示/非表示
- `Ctrl+Shift+P` - プライバシースキャン実行
- `Ctrl+Shift+O` - システム最適化実行
- `Ctrl+,` - 設定を開く
- `F5` - 手動更新
- `Ctrl+Q` - 終了

---

## トラブルシューティング

### プライバシーガードが動作しない

```bash
# ログ確認
cat ~/.config/moni/logs/privacy.log

# データベース確認
sqlite3 ~/.config/moni/privacy.db
```

### 最適化が効果ない

- **管理者権限で実行**: `sudo moni` (Linux/Mac) または 右クリック→管理者として実行 (Windows)
- **ウイルス対策の確認**: セキュリティソフトがブロックしていないか確認

### GPU情報が表示されない

```bash
# NVIDIA GPU確認
python -c "import pynvml; pynvml.nvmlInit(); print('OK')"

# ドライバー更新
# https://www.nvidia.com/Download/index.aspx
```

### 高リソース使用

```json
{
  "overlay": {
    "refresh_interval_ms": 3000,  // 更新頻度を下げる
    "show_sparklines": false       // グラフ無効化
  },
  "automation": {
    "history": {
      "max_entries": 300            // 履歴を減らす
    },
    "logging": {
      "enabled": false              // ログ無効化
    }
  }
}
```

---

## ドキュメント

- [基本ガイド](README.md) - 英語版README
- [セキュリティポリシー](SECURITY.md) - セキュリティ報告方法

---

## サポート

### バグ報告

GitHubのIssuesで報告してください：
1. OS、Pythonバージョン
2. エラーメッセージ
3. 再現手順

### セキュリティ脆弱性

**公開Issueで報告しないでください**

GitHub Security Advisoriesで報告：
- リポジトリのSecurityタブから報告

---

## ライセンス

MIT License - 詳細は [LICENSE](LICENSE) ファイルを参照

---

## 機能ハイライト

### なぜMoniを選ぶのか？

- **完全なプライバシー保護**
- すべてローカル処理
- 外部サーバーへの通信なし
- 機密データの自動検出と保護

- **自動最適化**
- メモリ、ディスク、ネットワークを自動最適化
- スタートアップ管理で起動を高速化
- ワンクリックで完全最適化

- **個人利用に最適**
- ゲーマー、開発者、一般ユーザー向けプロファイル
- カスタマイズ自由
- 使いやすいUI

- **高機能**
- リアルタイム監視
- 履歴分析とトレンド予測
- スマートアラート

---

## すぐ始める

```bash
# インストール
pip install -r requirements.txt
pip install -e .

# 起動
moni

# プライバシー保護開始
from moni.privacy_guard import get_privacy_guard
guard = get_privacy_guard()
guard.enable_auto_protect()

# システム最適化
from moni.system_optimizer import get_system_optimizer
optimizer = get_system_optimizer()
optimizer.full_optimization()
```

**安全で快適なPC環境を維持するために活用してください。**
