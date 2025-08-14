<div align="center">

<img src="https://taiga10969.github.io/images/arXiv-feed-SlackBot.png" alt="arXiv-feed-SlackBot" width="200" height="200">

# arXiv-feed-SlackBot

arXiv-feed-SlackBotは，arXiv（学術論文のプレプリントサーバー）から新着論文を取得し、設定されたキーワードに基づいてフィルタリングしてSlackに通知するボットです。

<img src="https://raw.githubusercontent.com/Taiga10969/arXiv-feed-SlackBot/refs/heads/main/data/image/%E3%82%B9%E3%82%AF%E3%83%AA%E3%83%BC%E3%83%B3%E3%82%B7%E3%83%A7%E3%83%83%E3%83%88%202025-08-14%2016.31.10.png" alt="arXiv-feed-SlackBot" width="350">

</div>

## 機能特徴

- **自動論文取得**: 指定されたarXivカテゴリから新着論文を自動取得
- **キーワードフィルタリング**: タイトルや要約に特定キーワードが含まれる論文のみを抽出
- **Slack通知**: フィルタリングされた論文をSlackに自動投稿
- **翻訳機能**: Google Cloud Translation APIを使用した要約の翻訳（オプション）
- **GitHub Actions対応**: 定期実行による自動化

## 利用方法

### 準備・セットアップ
最初にこのプロジェクトで必要なAPI keyなどを準備します

#### 1.リポジトリのフォーク
このリポジトリをフォークして自分のアカウントにリポジトリを作成してください．

#### 2. 各種Keyを取得

- `SLACK_WEBHOOK_URL`  
  配信するSlackチャンネルの Incoming Webhook URL を設定します。  
  Slack ワークスペースで **Incoming Webhooks** を追加し、対象チャンネルを選んで生成された URL を使用してください。

- `GOOGLE_CREDENTIALS_BASE64`（任意）  
  abstract を日本語に翻訳して表示する場合のみ必要です。  
  [Google Cloud Console](https://console.cloud.google.com/) で以下の手順を行います。

  1. **Cloud Translation API** を有効化  
  2. **課金**を有効化（無料枠はありますが課金設定が必要です）  
  3. **サービスアカウント**を作成 → JSON キーを発行してダウンロード  
     - 役割は最小権限でOK（例：`Cloud Translation API User`）
  4. JSON キーを Base64 エンコードしてファイルに保存（ローカルで実行）  
     - macOS / Linux:
       ```bash
       base64 -w 0 path/to/your-service-account.json > credentials.json.b64
       ```
     - Windows (PowerShell):
       ```powershell
       [Convert]::ToBase64String([IO.File]::ReadAllBytes("path\to\your-service-account.json")) > credentials.json.b64
       ```
  5. GitHub のリポジトリで **Settings → Secrets and variables → Actions → New repository secret** を開き、  
     Name に `GOOGLE_CREDENTIALS_BASE64`、Secret に `credentials.json.b64` の中身を貼り付けて保存します。

### カスタマイズ
自分の研究テーマに合わせて論文のカテゴリ・キーワードを設定します．

#### 1. 検索カテゴリの設定
`configs/categories.yaml`の中身を編集して、興味のあるarXivカテゴリを設定してください。

```yaml
categories:
  - cs.CV    # コンピュータビジョン
  - cs.AI    # 人工知能
  - cs.LG    # 機械学習
  - cs.CL    # 自然言語処理
```

#### 2. 検索キーワードの設定
`configs/keywords.yaml`の中身を編集して、興味のあるキーワードを設定してください。

```yaml
keywords:
  - "vector"
  - "diffusion"
  - "LoRA"
  - "vision-language|VLM|caption"  # 正規表現も使用可能
```

#### 3. その他の設定
`configs/config.yaml`で以下の設定をカスタマイズできます：

- 検索時間範囲（`hours_back`）
- 最大通知件数（`max_posts`）
- 表示オプション（キーワード、要約の表示）
- 翻訳設定
- Slack通知設定
くわしくは，下部の `（補足）設定ファイルの詳細` を御覧ください．

### GitHub Actionsでの運用

#### 1. 環境変数の設定
リポジトリのSettings → Secrets and variables → Actionsで以下の環境変数を設定：

- `SLACK_WEBHOOK_URL`: SlackのWebhook URL
- `GOOGLE_CREDENTIALS_BASE64`: 翻訳機能を使用する場合のGoogle Cloud認証情報（keyのjsonファイルをBASE64でエンコードして保存）

#### 2. Run workflowの確認

GitHub Actionsのワークフローが正しく動作するかを確認する方法：

1. **手動実行での確認**
   - リポジトリの「Actions」タブを開く
   - 「arXiv Bot」ワークフローを選択
   - 「Run workflow」ボタンをクリック
   - ブランチを選択して「Run workflow」を実行

2. **実行結果の確認**
   - ワークフローの実行状況をリアルタイムで確認
   - 各ステップのログを確認してエラーがないかチェック
   - Slackに通知が届くか確認

3. **定期実行の確認**
   - 設定したcronスケジュールで自動実行される
   - 「Actions」タブで定期実行の履歴を確認可能
   - 最新の実行時刻と次回実行予定時刻を確認

#### 3. 定期実行の設定

GitHub Actionsでの定期実行を設定するには、`.github/workflows/arxiv-feed-SlackBot.yml`ファイルを確認：

```yaml
name: arXiv Bot

on:
  schedule:
    - cron: '0 */6 * * *'  # 6時間ごとに実行（毎時0分）
    # 他のスケジュール例：
    # - cron: '0 9,18 * * *'  # 毎日9時と18時に実行
    # - cron: '0 9 * * 1-5'   # 平日の9時に実行
  workflow_dispatch:  # 手動実行も可能


**cron式の説明：**
- `0 */6 * * *`: 毎時0分に6時間ごと（0時、6時、12時、18時）
- `0 9,18 * * *`: 毎日9時と18時
- `0 9 * * 1-5`: 平日（月〜金）の9時
- `0 0 * * *`: 毎日0時（日次実行）
```


## （補足）設定ファイルの詳細

### config.yaml
メインの設定ファイルです。以下の項目を設定できます：

- **timezone**: タイムゾーン設定
- **search.hours_back**: 過去何時間分の論文を検索するか
- **max_posts**: 1回の通知で送る最大件数
- **display**: 表示オプション（キーワード、要約の表示）
- **slack**: Slack通知設定
- **translate**: 翻訳機能の設定

### 翻訳設定の詳細
翻訳機能では以下の設定が可能です：

```yaml
translate:
  enabled: true                # 翻訳機能を有効にするかどうか
  target_language: "ja"         # 翻訳先言語（例: "ja"=日本語, "en"=英語）
  show_translated: true        # 翻訳された概要を表示するかどうか（enabled=trueの場合のみ有効）
  hide_original_when_translated: true  # 翻訳表示時に元の英語概要を非表示にするかどうか
```

**設定の動作パターン：**
- `enabled: true` + `show_translated: true` + `hide_original_when_translated: true` → 英語のabstractは非表示、日本語翻訳のみ表示
- `enabled: true` + `show_translated: true` + `hide_original_when_translated: false` → 英語のabstractと日本語翻訳の両方表示
- `enabled: false` → 翻訳機能無効、英語のabstractのみ表示（`show_abstract: true`の場合）

### categories.yaml
arXivカテゴリの設定ファイルです。複数のカテゴリを指定できます。

### keywords.yaml
検索キーワードの設定ファイルです。正規表現を使用してOR条件での指定も可能です。

## 技術仕様

- **Python 3.9+**: メインの実行環境
- **arXiv Atom API**: 論文データの取得
- **Slack Webhook API**: 通知の送信
- **Google Cloud Translation API**: 翻訳機能（オプション）
- **YAML**: 設定ファイルの形式
- **GitHub Actions**: 定期実行の自動化

## トラブルシューティング

### よくある問題

1. **Slack通知が送信されない**
   - `SLACK_WEBHOOK_URL`が正しく設定されているか確認
   - Webhook URLが有効か確認

2. **翻訳機能が動作しない**
   - `GOOGLE_CREDENTIALS_BASE64`が設定されているか確認
   - Google Cloud Translation APIが有効化されているか確認

3. **論文が取得されない**
   - カテゴリ設定が正しいか確認
   - ネットワーク接続を確認



## 貢献

バグ報告や機能要望、プルリクエストを歓迎します。貢献する前に、まずissueを作成して議論してください。
