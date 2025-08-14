<div align="center">

<img src="https://taiga10969.github.io/images/arXiv-feed-SlackBot.png" alt="arXiv-feed-SlackBot" width="200" height="200">

# 📚 arXiv-feed-SlackBot

arXiv（学術論文のプレプリントサーバー）から新着論文を取得し、設定されたキーワードに基づいてフィルタリングしてSlackに通知するPythonボットです。

</div>

## 機能特徴

- **自動論文取得**: 指定されたarXivカテゴリから新着論文を自動取得
- **キーワードフィルタリング**: タイトルや要約に特定キーワードが含まれる論文のみを抽出
- **Slack通知**: フィルタリングされた論文をSlackに自動投稿
- **翻訳機能**: Google Cloud Translation APIを使用した要約の翻訳（オプション）
- **GitHub Actions対応**: 定期実行による自動化







## 📋 目次

- [セットアップ](#セットアップ)
- [設定ファイル](#設定ファイル)
- [GitHub Actionsでの運用](#github-actionsでの運用)

## 🛠️ セットアップ（推奨方法）

### 1. リポジトリのフォーク

1. GitHub上で「Fork」ボタンをクリック
2. 自分のアカウントにリポジトリが作成される


### 2. 設定ファイルの修正

その他の設定ファイルの詳細は[設定ファイル](#設定ファイル)セクションを参照してください。



## ⚙️ 設定ファイル

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
指定されたキーワードがタイトル・論文の概要に含まれているかをチェックします．



### 表示内容のカスタマイズ

`configs/config.yaml` の `display` セクションを調整：

```yaml
display:
  show_keywords: true      # キーワードを表示
  show_abstract: true      # 概要を表示
```


## お問い合わせ

問題や質問がある場合は、GitHub Issues でお気軽にお問い合わせください。