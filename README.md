# arXiv-feed-SlackBot

arXiv（学術論文のプレプリントサーバー）から新着論文を取得し、設定されたキーワードに基づいてフィルタリングしてSlackに通知するPythonボットです。

## 🚀 特徴

- **自動論文取得**: 指定されたarXivカテゴリから新着論文を自動取得
- **キーワードフィルタリング**: タイトルや要約に特定キーワードが含まれる論文のみを抽出
- **スコアリングシステム**: タイトル一致（×2）と要約一致（×1）でスコアを計算
- **重複防止**: 既読管理により同じ論文の重複通知を防止
- **Slack通知**: フィルタリングされた論文をSlackに自動投稿
- **翻訳機能**: Google Cloud Translation APIを使用した要約の翻訳（オプション）
- **GitHub Actions対応**: 定期実行による自動化

## 📋 目次

- [セットアップ](#セットアップ)
- [設定ファイル](#設定ファイル)
- [GitHub Actionsでの運用](#github-actionsでの運用)
- [手動実行](#手動実行)
- [トラブルシューティング](#トラブルシューティング)
- [カスタマイズ](#カスタマイズ)

## 🛠️ セットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/your-username/arXiv-feed-SlackBot.git
cd arXiv-feed-SlackBot
```

### 2. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 3. 設定ファイルの準備

設定ファイルの詳細は[設定ファイル](#設定ファイル)セクションを参照してください。

## ⚙️ 設定ファイル

### メイン設定 (`configs/config.yaml`)

基本的な動作設定を行います。

```yaml
timezone: "Asia/Tokyo"          # タイムゾーン

# カテゴリとキーワードの設定ファイルパス
categories_file: "configs/categories.yaml"
keywords_file: "configs/keywords.yaml"

# 検索設定
search:
  hours_back: 48             # 過去何時間分の論文を検索するか

# 通知設定
max_posts: 15                # 1回の通知で送る最大件数

# 表示設定
display:
  show_keywords: true        # マッチしたキーワードを表示
  show_abstract: false       # 論文の概要を表示

# Slack設定
slack:
  username: "arXiv-feed-SlackBot"
  icon_url: "https://example.com/icon.png"

# 翻訳設定
translate:
  enabled: false             # 翻訳機能を有効にするかどうか
  target_language: "ja"      # 翻訳先言語
  show_translated: false     # 翻訳された概要を表示するかどうか
```

### カテゴリ設定 (`configs/categories.yaml`)

興味のあるarXivカテゴリを指定します。

```yaml
categories:
  - cs.CV    # コンピュータビジョン
  - cs.AI    # 人工知能
  - cs.LG    # 機械学習
  - cs.CL    # 自然言語処理
```

### キーワード設定 (`configs/keywords.yaml`)

通知したい論文に含まれるキーワードを指定します。

```yaml
keywords:
  - "vector"
  - "diffusion"
  - "LoRA"
  - "TikZ"
```

## 🚀 GitHub Actionsでの運用

### 1. リポジトリの設定

#### Secrets の設定

リポジトリの "Settings" > "Secrets and variables" > "Actions" で以下を設定：

**必須設定:**
- `SLACK_WEBHOOK_URL`: SlackのWebhook URL

**翻訳機能を使用する場合（オプション）:**
- `GOOGLE_CREDENTIALS_BASE64`: GCP認証情報（Base64エンコード済み）

#### Slack Webhook URL の取得

1. Slackワークスペースでアプリを作成
2. "Incoming Webhooks" を有効化
3. 通知したいチャンネルを選択
4. Webhook URLをコピーしてSecretsに設定

### 2. ワークフローの設定

`.github/workflows/arxiv-feed-SlackBot.yml` が自動的に設定されます。

#### 実行スケジュール

```yaml
on:
  schedule:
    - cron: "0 0 * * *"      # 毎日UTC 00:00（日本時間09:00）
  workflow_dispatch:          # 手動実行も可能
```

#### カスタムスケジュール

必要に応じて `cron` を変更：

```yaml
# 毎週月曜日の09:00（日本時間）
- cron: "0 0 * * 1"

# 毎日2回（09:00と21:00）
- cron: "0 0,12 * * *"

# 平日のみ
- cron: "0 0 * * 1-5"
```

### 3. 初回実行

1. リポジトリにプッシュ
2. GitHub Actionsが自動的に実行開始
3. "Actions" タブで実行状況を確認

### 4. 実行ログの確認

GitHub Actionsの実行ログで以下を確認：

- 論文の取得状況
- フィルタリング結果
- Slack通知の成功/失敗
- エラーの詳細

## 🖥️ 手動実行

### ローカル環境での実行

```bash
# 基本実行
python src/main.py --config configs/config.yaml

# 環境変数の設定
export SLACK_WEBHOOK_URL="your_slack_webhook_url"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/credentials.json"

# 実行
python src/main.py --config configs/config.yaml
```

### Docker での実行

```bash
# Dockerfile が提供されている場合
docker build -t arxiv-feed-slackbot .
docker run -e SLACK_WEBHOOK_URL="your_url" arxiv-feed-slackbot
```

## 🔧 カスタマイズ

### カテゴリの追加・変更

`configs/categories.yaml` を編集：

```yaml
categories:
  - cs.CV    # Computer Vision
  - cs.AI    # Artificial Intelligence
  - cs.LG    # Machine Learning
  - cs.CL    # Computation and Language
  - cs.NE    # Neural and Evolutionary Computing
  - cs.IR    # Information Retrieval
  - cs.SE    # Software Engineering
  - cs.DC    # Distributed, Parallel, and Cluster Computing
```

### キーワードの調整

`configs/keywords.yaml` を編集：

```yaml
keywords:
  # 機械学習・AI関連
  - "transformer"
  - "attention"
  - "neural network"
  
  # 正規表現を使用した複数キーワード
  - "vision-language|VLM|caption"
  - "detection|segmentation"
```

### 検索時間の調整

`configs/config.yaml` の `search.hours_back` を変更：

```yaml
search:
  hours_back: 24    # 過去24時間
  # hours_back: 48  # 過去48時間
  # hours_back: 168 # 過去1週間
```

### 表示内容のカスタマイズ

`configs/config.yaml` の `display` セクションを調整：

```yaml
display:
  show_keywords: true      # キーワードを表示
  show_abstract: true      # 概要を表示
```

## 🐛 トラブルシューティング

### よくある問題と解決方法

#### 1. Slack通知が失敗する

**症状**: `400 Client Error: Bad Request`

**原因と解決方法**:
- Webhook URLが正しく設定されているか確認
- Slackアプリの権限設定を確認
- 通知チャンネルが存在するか確認

#### 2. 論文が取得できない

**症状**: "No papers fetched from arXiv"

**原因と解決方法**:
- インターネット接続を確認
- arXivのサービス状況を確認
- カテゴリ設定が正しいか確認

#### 3. 翻訳機能が動作しない

**症状**: "Translation failed"

**原因と解決方法**:
- GCP認証情報が正しく設定されているか確認
- Cloud Translation APIが有効化されているか確認
- クォータ制限に達していないか確認

#### 4. GitHub Actionsが失敗する

**症状**: ワークフローが失敗する

**原因と解決方法**:
- Secretsが正しく設定されているか確認
- 依存関係のインストールが成功しているか確認
- 設定ファイルの構文が正しいか確認

### ログの確認方法

#### GitHub Actions のログ

1. リポジトリの "Actions" タブを開く
2. 失敗したワークフローをクリック
3. 失敗したジョブをクリック
4. 詳細なログを確認

#### ローカル実行時のログ

```bash
# 詳細ログを有効化
export PYTHONPATH=.
python src/main.py --config configs/config.yaml 2>&1 | tee arxiv-bot.log
```


## 🤝 貢献

### バグ報告

1. GitHub Issues で問題を報告
2. 再現手順を詳細に記載
3. エラーログを添付

### 機能要望

1. GitHub Issues で要望を記載
2. ユースケースを具体的に説明
3. 実装案があれば提案

### プルリクエスト

1. 機能ブランチを作成
2. 変更内容を明確に記載
3. テストを実行してから提出

## お問い合わせ

問題や質問がある場合は、GitHub Issues でお気軽にお問い合わせください。