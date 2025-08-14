# arXiv-feed-SlackBot

arXiv（学術論文のプレプリントサーバー）から新着論文を取得し、設定されたキーワードに基づいてフィルタリングしてSlackに通知するPythonボットです。

## 特徴

- **自動論文取得**: 指定されたarXivカテゴリから新着論文を自動取得
- **キーワードフィルタリング**: タイトルや要約に特定キーワードが含まれる論文のみを抽出
- **スコアリングシステム**: タイトル一致（×2）と要約一致（×1）でスコアを計算
- **重複防止**: 既読管理により同じ論文の重複通知を防止
- **Slack通知**: フィルタリングされた論文をSlackに自動投稿
- **翻訳機能**: Google Cloud Translation APIを使用した要約の翻訳（オプション）

## 設定ファイル

### メイン設定 (`configs/config.yaml`)
基本的な動作設定を行います。

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

### 表示設定
メイン設定ファイル (`configs/config.yaml`) の `display` セクションで、Slackに表示する内容を制御できます。

```yaml
display:
  show_keywords: true      # マッチしたキーワードを表示
  show_abstract: false     # 論文の概要を表示
  show_translate: false    # 翻訳された概要を表示（翻訳が有効な場合のみ）
```

## 使用方法

1. **設定ファイルの編集**
   - `configs/categories.yaml`: 興味のある分野のカテゴリを設定
   - `configs/keywords.yaml`: 追跡したいキーワードを設定

2. **環境変数の設定**
   ```bash
   export SLACK_WEBHOOK_URL="your_slack_webhook_url"
   ```

3. **実行**
   ```bash
   python src/main.py --config configs/config.yaml
   ```

## カテゴリ一覧（参考）

- `cs.CV`: Computer Vision and Pattern Recognition
- `cs.AI`: Artificial Intelligence
- `cs.LG`: Machine Learning
- `cs.CL`: Computation and Language
- `cs.NE`: Neural and Evolutionary Computing
- `cs.IR`: Information Retrieval
- `cs.SE`: Software Engineering
- `cs.DC`: Distributed, Parallel, and Cluster Computing

## 依存関係

```bash
pip install -r requirements.txt
```

## GitHub Actionsでの使用

GitHub Actionsでは以下のSecretsを設定してください：

### 必須設定
- `SLACK_WEBHOOK_URL`: SlackのWebhook URL

### 翻訳機能を使用する場合（オプション）
- `GOOGLE_CREDENTIALS_BASE64`: GCP認証情報（Base64エンコード済み）

## GCP認証の設定手順（翻訳機能使用時）

翻訳機能を使用する場合は、以下の手順でGCP認証を設定してください：

### 1. Google Cloud Projectの準備
1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. プロジェクトを作成または選択
3. Cloud Translation APIを有効化

### 2. サービスアカウントの作成
1. IAM & Admin > Service Accounts に移動
2. "Create Service Account" をクリック
3. サービスアカウント名を入力（例: `arxiv-translate-bot`）
4. "Create and Continue" をクリック

### 3. 権限の設定
1. "Grant this service account access to project" で以下を選択：
   - `Cloud Translation API User`
2. "Continue" をクリック
3. "Done" をクリック

### 4. キーの作成
1. 作成したサービスアカウントをクリック
2. "Keys" タブを選択
3. "Add Key" > "Create new key" をクリック
4. "JSON" を選択して "Create" をクリック
5. ダウンロードされたJSONファイルを保存

### 5. Base64エンコード
```bash
# macOS/Linux
base64 -i path/to/service-account-key.json

# Windows (PowerShell)
[Convert]::ToBase64String([IO.File]::ReadAllBytes("path/to/service-account-key.json"))
```

### 6. GitHub Secretsの設定
1. リポジトリの "Settings" > "Secrets and variables" > "Actions" に移動
2. "New repository secret" をクリック
3. Name: `GOOGLE_CREDENTIALS_BASE64`
4. Value: ステップ5で生成したBase64文字列
5. "Add secret" をクリック

### 7. 設定ファイルの更新
`configs/config.yaml` で翻訳機能を有効化：

```yaml
translate:
  enabled: true
  target_language: "ja"  # 翻訳先言語
```