#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
arXiv 新着論文通知ボット

特徴:
- 指定されたarXivカテゴリから新着論文を自動取得
- キーワードフィルタリングによる関連論文の抽出
- スコアリングシステム（タイトル×2 + 要約×1）
- 重複通知の防止（既読管理）
- Slackへの自動通知
- 翻訳機能（Google Cloud Translation API）

使用方法:
  python src/main.py --config configs/config.yaml
"""

import os
import re
import json
import zoneinfo
import datetime as dt
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import argparse
import requests
import yaml

# ==============================
# 設定 & 既読ファイルのロード
# ==============================
def load_config_and_state():
    """設定ファイルと既読状態を読み込み"""
    parser = argparse.ArgumentParser(description="arXiv新着論文通知ボット")
    parser.add_argument(
        "--config",
        type=str,
        default=os.environ.get("CONFIG_PATH", "configs/config.yaml"),
        help="設定ファイルのパス",
    )
    args = parser.parse_args()

    cfg_path = Path(args.config)
    base_dir = Path(__file__).resolve().parent.parent

    # メイン設定ファイル読み込み
    config = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    
    # 外部設定ファイルの読み込み
    # カテゴリ設定
    categories_file = config.get("categories_file", "configs/categories.yaml")
    categories_path = base_dir / categories_file
    if categories_path.exists():
        categories_config = yaml.safe_load(categories_path.read_text(encoding="utf-8"))
        config["categories"] = categories_config.get("categories", ["cs.CV"])
    else:
        print(f"[WARN] Categories file not found: {categories_path}")
        config["categories"] = ["cs.CV"]
    
    # キーワード設定
    keywords_file = config.get("keywords_file", "configs/keywords.yaml")
    keywords_path = base_dir / keywords_file
    if keywords_path.exists():
        keywords_config = yaml.safe_load(keywords_path.read_text(encoding="utf-8"))
        config["keywords"] = keywords_config.get("keywords", [])
    else:
        print(f"[WARN] Keywords file not found: {keywords_path}")
        config["keywords"] = []

    # 既読管理ファイルの設定
    state_file = config.get("state_file", "seen.json")
    seen_path = base_dir / "data" / state_file
    seen_path.parent.mkdir(parents=True, exist_ok=True)
    if not seen_path.exists():
        seen_path.write_text("[]", encoding="utf-8")

    # タイムゾーン・現在時刻
    tz = zoneinfo.ZoneInfo(config.get("timezone", "Asia/Tokyo"))
    now_local = dt.datetime.now(tz)

    # 既読IDセット
    try:
        seen = set(json.loads(seen_path.read_text(encoding="utf-8")))
    except Exception:
        seen = set()
        seen_path.write_text("[]", encoding="utf-8")

    return config, base_dir, cfg_path, seen_path, seen, tz, now_local


# グローバル設定（一度だけロード）
CONFIG, BASE_DIR, CFG_PATH, SEEN_PATH, SEEN, TZ, NOW_LOCAL = load_config_and_state()


# ==============================
# arXiv 取得 (Atom API)
# ==============================
ARXIV_ATOM = "http://export.arxiv.org/api/query"

def fetch_arxiv(categories: List[str], max_results: int = 200) -> List[Dict[str, Any]]:
    """指定されたカテゴリからarXiv論文を取得"""
    cat_query = " OR ".join([f"cat:{c}" for c in categories])
    params = {
        "search_query": cat_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    
    try:
        r = requests.get(ARXIV_ATOM, params=params, timeout=30)
        r.raise_for_status()
        root = ET.fromstring(r.text)
        ns = {"ns": "http://www.w3.org/2005/Atom"}

        items: List[Dict[str, Any]] = []
        for entry in root.findall("ns:entry", ns):
            title = (entry.find("ns:title", ns).text or "").strip()
            summary = (entry.find("ns:summary", ns).text or "").strip()
            link = (entry.find("ns:id", ns).text or "").strip()
            published = (entry.find("ns:published", ns).text or "").strip()
            updated = (entry.find("ns:updated", ns).text or "").strip()
            arxiv_id = link.rsplit("/", 1)[-1]
            
            items.append({
                "id": arxiv_id,
                "title": title.replace("\n", " "),
                "summary": summary.replace("\n", " "),
                "link": link,
                "published": published,
                "updated": updated,
            })
        
        print(f"[INFO] Fetched {len(items)} papers from arXiv")
        return items
        
    except Exception as e:
        print(f"[ERROR] Failed to fetch from arXiv: {e}")
        return []


# ==============================
# フィルタ & スコアリング
# ==============================
def within_search_hours(iso8601_str: str, hours_back: int) -> bool:
    """指定時間以内に公開された論文かどうかを判定"""
    try:
        t = dt.datetime.fromisoformat(iso8601_str.replace("Z", "+00:00"))
        now_utc = dt.datetime.now(dt.timezone.utc)
        return (now_utc - t).total_seconds() <= hours_back * 3600
    except Exception:
        return False

def parse_iso8601(s: str) -> dt.datetime:
    """ISO8601文字列をdatetimeオブジェクトに変換"""
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

def compile_kw_patterns(kw_list: List[str]) -> List[re.Pattern]:
    """キーワードリストから正規表現パターンを作成"""
    if not kw_list:
        return []
    
    patterns: List[re.Pattern] = []
    for kw in kw_list:
        if "|" in kw:
            patterns.append(re.compile(kw, re.IGNORECASE))
        else:
            patterns.append(re.compile(re.escape(kw), re.IGNORECASE))
    return patterns

def compute_match_score(title: str, summary: str, patterns: List[re.Pattern]) -> Tuple[int, List[str]]:
    """一致スコアとマッチしたキーワードを計算"""
    if not patterns:
        return 0, []
    
    score_title = 0
    score_summary = 0
    matched_keywords = set()
    
    for pattern in patterns:
        title_matches = pattern.findall(title)
        summary_matches = pattern.findall(summary)
        
        if title_matches:
            score_title += len(title_matches)
            matched_keywords.add(pattern.pattern)
        if summary_matches:
            score_summary += len(summary_matches)
            matched_keywords.add(pattern.pattern)
    
    return score_title * 2 + score_summary * 1, list(matched_keywords)

def select_by_relevance(
    items: List[Dict[str, Any]],
    kw_patterns: List[re.Pattern],
    max_posts: int,
) -> List[Tuple[Dict[str, Any], List[str]]]:
    """関連性に基づいて論文を選択"""
    candidates: List[Tuple[int, dt.datetime, Dict[str, Any], List[str]]] = []
    
    # 検索時間の設定を取得
    hours_back = CONFIG.get("search", {}).get("hours_back", 24)
    
    for item in items:
        if item["id"] in SEEN:
            continue
        if not within_search_hours(item["published"], hours_back):
            continue

        if kw_patterns:
            score, matched_kw = compute_match_score(item["title"], item["summary"], kw_patterns)
            if score <= 0:
                continue
        else:
            score = 0
            matched_kw = []

        pub_dt = parse_iso8601(item["published"])
        candidates.append((score, pub_dt, item, matched_kw))

    if not candidates:
        return []

    # スコア降順 → 公開日時降順
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    
    # デバッグ情報を出力
    print(f"[DEBUG] select_by_relevance: {len(candidates)} candidates found")
    print(f"[DEBUG] select_by_relevance: max_posts = {max_posts}")
    print(f"[DEBUG] select_by_relevance: returning {min(len(candidates), max_posts)} papers")
    
    return [(item, matched_kw) for _, _, item, matched_kw in candidates[:max_posts]]


# ==============================
# 翻訳機能
# ==============================
def maybe_translate(text: str) -> str:
    """テキストを翻訳（Google Cloud Translation API使用）"""
    tr_cfg = CONFIG.get("translate", {})
    if not tr_cfg.get("enabled", False):
        return text
    
    try:
        from google.cloud import translate_v2 as translate
        client = translate.Client()
        res = client.translate(text, target_language=tr_cfg.get("target_language", "ja"))
        return res["translatedText"]
    except Exception as e:
        print(f"[WARN] Translation failed: {e}")
        return text


# ==============================
# Slack 通知
# ==============================
def post_to_slack_webhook(blocks: List[Dict[str, Any]]) -> None:
    """Slack Webhookにメッセージを送信"""
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        raise RuntimeError("SLACK_WEBHOOK_URL is not set")
    
    payload = {
        "username": CONFIG.get("slack", {}).get("username", "arXiv Bot"),
        "blocks": blocks,
    }
    
    # アイコン設定
    slack_config = CONFIG.get("slack", {})
    if slack_config.get("icon_url"):
        payload["icon_url"] = slack_config["icon_url"]
    elif slack_config.get("icon_emoji"):
        payload["icon_emoji"] = slack_config["icon_emoji"]
    else:
        payload["icon_emoji"] = ":newspaper:"
    
    # デバッグ情報
    payload_size = len(json.dumps(payload))
    print(f"[DEBUG] Payload size: {payload_size} characters")
    
    if payload_size > 50000:
        print(f"[WARN] Payload size ({payload_size}) exceeds Slack's 50KB limit")
    
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        print(f"[INFO] Successfully posted to Slack (status: {r.status_code})")
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] Slack HTTP error: {e}")
        print(f"[ERROR] Response status: {r.status_code}")
        print(f"[ERROR] Response body: {r.text}")
        
        if "invalid_blocks" in r.text:
            print(f"[ERROR] Invalid blocks error detected. Checking block structure...")
            for i, block in enumerate(payload["blocks"]):
                print(f"[ERROR] Block {i}: {json.dumps(block, ensure_ascii=False)}")
        
        raise
    except Exception as e:
        print(f"[ERROR] Unexpected error posting to Slack: {e}")
        raise

def clean_text_for_slack(text: str) -> str:
    """Slack用にテキストをクリーンアップ"""
    # 制御文字を除去（改行とタブは保持）
    cleaned = "".join(char for char in text if ord(char) >= 32 or char in "\n\t")
    # 問題のある文字を除去
    cleaned = cleaned.replace("\x7F", "").replace("\x80", "").replace("\x81", "")
    return cleaned

def make_slack_blocks(entries: List[Tuple[Dict[str, Any], List[str]]], total_count: int = None, displayed_count: int = None) -> List[Dict[str, Any]]:
    """Slackブロックを作成"""
    try:
        blocks: List[Dict[str, Any]] = []
        
        # 日付の安全な処理
        try:
            date_str = NOW_LOCAL.strftime('%Y-%m-%d')
        except Exception:
            date_str = "今日"
        
        # ヘッダーテキストの作成（総件数情報を含む）
        if total_count and displayed_count and total_count > displayed_count:
            header_text = f"arXiv で公開された新着論文 ({date_str}) - 全{total_count}件中{displayed_count}件表示"
        else:
            header_text = f"arXiv で公開された新着論文 ({date_str})"
        
        header = {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": header_text,
                "emoji": True,
            },
        }
        blocks.append(header)

        # 表示設定を取得
        display_config = CONFIG.get("display", {})
        show_keywords = display_config.get("show_keywords", True)
        show_abstract = display_config.get("show_abstract", False)
        
        # 翻訳設定を取得
        translate_config = CONFIG.get("translate", {})
        translate_enabled = translate_config.get("enabled", False)
        show_translated = translate_config.get("show_translated", False)
        hide_original_when_translated = translate_config.get("hide_original_when_translated", False)

        for item, matched_keywords in entries:
            title = item["title"]
            url = item["link"]
            summary = item["summary"]
            
            # タイトルの安全な処理
            safe_title = clean_text_for_slack(title)
            if len(safe_title) > 2800:
                safe_title = safe_title[:2800] + "..."
            
            # タイトルとURLの組み合わせ
            title_text = f"*<{url}|{safe_title}>*"
            if len(title_text) > 3000:
                title_text = f"*{safe_title}*\n<{url}|論文を読む>"
            
            title_text = clean_text_for_slack(title_text)
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": title_text}})
            
            # キーワード表示
            if show_keywords and matched_keywords:
                try:
                    clean_keywords = [kw.replace('\\', '') for kw in matched_keywords]
                    keywords_text = "*キーワード:* " + ", ".join(clean_keywords)
                    
                    if len(keywords_text) > 3000:
                        keywords_text = keywords_text[:2800] + "..."
                    
                    keywords_text = clean_text_for_slack(keywords_text)
                    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": keywords_text}})
                except Exception as e:
                    print(f"[WARN] Error processing keywords for {item['id']}: {e}")
                    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*キーワード:* エラーが発生しました"}})
            
            # 概要表示（翻訳表示時は英語のabstractを非表示にする）
            if show_abstract and not (translate_enabled and show_translated and hide_original_when_translated):
                abstract_text = summary[:2800] + "..." if len(summary) > 2800 else summary
                safe_abstract = clean_text_for_slack(abstract_text)
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Abstract:* {safe_abstract}"}})
            
            # 翻訳表示
            if translate_enabled and show_translated:
                try:
                    translated_summary = maybe_translate(summary)
                    translated_text = translated_summary[:2800] + "..." if len(translated_summary) > 2800 else translated_summary
                    safe_translated = clean_text_for_slack(translated_text)
                    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Abstract(翻訳):* {safe_translated}"}})
                except Exception as e:
                    print(f"[WARN] Translation failed for {item['id']}: {e}")
            
            # メタ情報
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"`{item['id']}`  •  published: {item['published']}",
                    }
                ],
            })
            
            blocks.append({"type": "divider"})
        
        # ブロックの妥当性チェック
        valid_blocks = []
        for i, block in enumerate(blocks):
            try:
                if "type" not in block:
                    print(f"[WARN] Block {i} missing 'type' field: {block}")
                    continue
                
                valid_types = ["header", "section", "context", "divider"]
                if block["type"] not in valid_types:
                    print(f"[WARN] Block {i} has invalid type '{block['type']}': {block}")
                    continue
                
                if block["type"] in ["section", "context"] and "text" in block:
                    text_block = block["text"]
                    if "text" not in text_block or not text_block["text"]:
                        print(f"[WARN] Block {i} has empty text: {block}")
                        continue
                    
                    if len(text_block["text"]) > 3000:
                        print(f"[WARN] Block {i} text too long, truncating: {len(text_block['text'])} chars")
                        text_block["text"] = text_block["text"][:2800] + "..."
                
                if block["type"] == "header" and "text" in block:
                    header_text = block["text"]
                    if "text" not in header_text or not header_text["text"]:
                        print(f"[WARN] Block {i} header has empty text: {block}")
                        continue
                
                valid_blocks.append(block)
                
            except Exception as e:
                print(f"[WARN] Error validating block {i}: {e}, block: {block}")
                continue
        
        return valid_blocks
        
    except Exception as e:
        print(f"[ERROR] Error creating Slack blocks: {e}")
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*arXiv 新着論文通知*\nエラーが発生しました: {str(e)}"
                }
            }
        ]

def make_no_papers_message() -> List[Dict[str, Any]]:
    """論文が見つからない場合のメッセージを作成"""
    blocks: List[Dict[str, Any]] = []
    
    # 日付の安全な処理
    try:
        date_str = NOW_LOCAL.strftime('%Y-%m-%d')
    except Exception:
        date_str = "今日"
    
    header = {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"arXiv で公開された新着論文 ({date_str})",
            "emoji": True,
        },
    }
    blocks.append(header)
    
    # 論文が見つからない旨のメッセージ
    message_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "📭 *新着論文は見つかりませんでした*"
        }
    }
    blocks.append(message_block)
    
    # 設定情報を表示
    cats = CONFIG.get("categories", ["cs.CV"])
    keywords = CONFIG.get("keywords", [])
    hours_back = CONFIG.get("search", {}).get("hours_back", 24)
    
    config_info = f"*設定情報:*\n• カテゴリ: {', '.join(cats)}\n• キーワード: {', '.join(keywords) if keywords else 'なし'}\n• 検索時間: 過去{hours_back}時間"
    
    config_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": config_info
        }
    }
    blocks.append(config_block)
    
    blocks.append({"type": "divider"})
    
    return blocks


# ==============================
# メイン処理
# ==============================
def main() -> None:
    """メイン処理"""
    try:
        # 設定の取得
        categories = CONFIG.get("categories", ["cs.CV"])
        kw_patterns = compile_kw_patterns(CONFIG.get("keywords", []))
        max_posts = int(CONFIG.get("max_posts", 20))

        print(f"[INFO] Fetching papers from arXiv categories: {categories}")
        items = fetch_arxiv(categories, max_results=200)

        if not items:
            print("[ERROR] No papers fetched from arXiv")
            return

        # 関連論文の選択（max_postsの制限を適用）
        selected = select_by_relevance(items, kw_patterns, max_posts=max_posts)
        
        if not selected:
            print("[INFO] No new papers matched criteria")
            blocks = make_no_papers_message()
            post_to_slack_webhook(blocks)
            print("[INFO] Posted 'no papers found' message to Slack")
            return

        # 論文が見つかった場合
        # 総件数を計算（max_postsを超える場合の表示用）
        hours_back = CONFIG.get("search", {}).get("hours_back", 24)
        all_matched = [item for item in items if item["id"] not in SEEN and within_search_hours(item["published"], hours_back)]
        total_matched = len(all_matched)
        
        # 実際に表示される件数（max_postsで制限された件数）
        displayed_count = len(selected)
        
        # デバッグ情報を出力
        print(f"[DEBUG] Total matched papers: {total_matched}")
        print(f"[DEBUG] Papers selected for display: {displayed_count}")
        print(f"[DEBUG] Max posts setting: {max_posts}")
        
        blocks = make_slack_blocks(selected, total_count=total_matched, displayed_count=displayed_count)
        post_to_slack_webhook(blocks)

        # 既読IDを保存
        for item, _ in selected:
            SEEN.add(item["id"])
        SEEN_PATH.write_text(json.dumps(sorted(SEEN)), encoding="utf-8")
        
        print(f"[INFO] Posted {len(selected)} papers to Slack")
        
    except Exception as e:
        print(f"[ERROR] Main process failed: {e}")
        raise


if __name__ == "__main__":
    main()
