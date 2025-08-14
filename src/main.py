#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
arXiv 新着を取得して、キーワード一致スコアの高い順に上位 N 件だけ Slack へ通知する Bot。

特徴:
- configs/*.yaml などの設定ファイルを --config で切替可能
- 既読管理 (data/seen_*.json) により重複通知を防止
- 一致スコア = タイトル一致×2 + 要約一致×1（出現回数分だけ加点）
- 24時間以内に公開 (published) された論文のみ通知
- 同点は公開日時の新しいものを優先

使い方(例):
  python src/main.py --config configs/cv.yaml
  # GitHub Actions では SLACK_WEBHOOK_URL を Secrets で渡してください
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=str,
        default=os.environ.get("CONFIG_PATH", "configs/config.yaml"),
        help="Path to config YAML",
    )
    args = parser.parse_args()

    cfg_path = Path(args.config)
    base_dir = Path(__file__).resolve().parent.parent  # repo root 想定

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

    # state_file（既読管理ファイル名）決定
    state_file = config.get("state_file")
    if not state_file:
        slug = cfg_path.stem  # 例: cv.yaml -> "cv"
        state_file = f"seen_{slug}.json"

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


# ここで一度だけロードして、以降は上書きしない
CONFIG, BASE_DIR, CFG_PATH, SEEN_PATH, SEEN, TZ, NOW_LOCAL = load_config_and_state()


# ==============================
# arXiv 取得 (Atom API)
# ==============================
ARXIV_ATOM = "http://export.arxiv.org/api/query"

def fetch_arxiv(categories: List[str], max_results: int = 200) -> List[Dict[str, Any]]:
    """カテゴリを OR でまとめて arXiv から取得。published/updated はUTC ISO8601文字列。"""
    cat_query = " OR ".join([f"cat:{c}" for c in categories])
    params = {
        "search_query": cat_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
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
        arxiv_id = link.rsplit("/", 1)[-1]  # 例: http://arxiv.org/abs/2508.01234 → 2508.01234
        items.append(
            {
                "id": arxiv_id,
                "title": title.replace("\n", " "),
                "summary": summary.replace("\n", " "),
                "link": link,
                "published": published,
                "updated": updated,
            }
        )
    return items


# ==============================
# フィルタ & スコアリング
# ==============================
def within_last_24h(iso8601_str: str) -> bool:
    """UTCのISO8601文字列が過去24時間以内か判定。"""
    t = dt.datetime.fromisoformat(iso8601_str.replace("Z", "+00:00"))
    now_utc = dt.datetime.now(dt.timezone.utc)
    return (now_utc - t).total_seconds() <= 24 * 3600

def parse_iso8601(s: str) -> dt.datetime:
    """UTCのISO8601文字列をaware datetimeへ。"""
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

def compile_kw_patterns(kw_list: List[str]) -> List[re.Pattern]:
    """
    設定のキーワード配列から正規表現パターンのリストを作成。
    - '|' を含む要素はそのまま正規表現として扱う
    - 含まない要素はエスケープして部分一致に使う
    """
    if not kw_list:
        return []
    pats: List[re.Pattern] = []
    for kw in kw_list:
        if "|" in kw:
            pats.append(re.compile(kw, re.IGNORECASE))
        else:
            pats.append(re.compile(re.escape(kw), re.IGNORECASE))
    return pats

def compute_match_score(title: str, summary: str, patterns: List[re.Pattern]) -> Tuple[int, List[str]]:
    """
    一致スコアとマッチしたキーワードを計算。
    - タイトル一致: 出現回数 × 2
    - 要約一致    : 出現回数 × 1
    """
    if not patterns:
        return 0, []
    score_t = 0
    score_s = 0
    matched_keywords = set()
    
    for pat in patterns:
        title_matches = pat.findall(title)
        summary_matches = pat.findall(summary)
        
        if title_matches:
            score_t += len(title_matches)
            matched_keywords.add(pat.pattern)
        if summary_matches:
            score_s += len(summary_matches)
            matched_keywords.add(pat.pattern)
    
    return score_t * 2 + score_s * 1, list(matched_keywords)

def select_by_relevance(
    items: List[Dict[str, Any]],
    kw_patterns: List[re.Pattern],
    max_posts: int,
) -> List[Tuple[Dict[str, Any], List[str]]]:
    """
    24h以内 & 未読を対象に、スコア降順・同点は新しい順で並べ、上位 max_posts を返す。
    キーワード未設定時は日付の新しい順で切る。
    """
    candidates: List[Tuple[int, dt.datetime, Dict[str, Any], List[str]]] = []
    for it in items:
        if it["id"] in SEEN:
            continue
        if not within_last_24h(it["published"]):
            continue

        if kw_patterns:
            score, matched_kw = compute_match_score(it["title"], it["summary"], kw_patterns)
            if score <= 0:
                continue
        else:
            score = 0  # キーワードなし運用の場合
            matched_kw = []

        pub_dt = parse_iso8601(it["published"])
        candidates.append((score, pub_dt, it, matched_kw))

    if not candidates:
        return []

    # スコア降順 → 公開日時降順
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [(it, matched_kw) for _, _, it, matched_kw in candidates[:max_posts]]


# ==============================
# 翻訳（任意, GCP）
# ==============================
def maybe_translate(text: str) -> str:
    tr_cfg = CONFIG.get("translate", {})
    if not tr_cfg.get("enabled", False):
        return text
    try:
        from google.cloud import translate_v2 as translate  # type: ignore
        client = translate.Client()
        res = client.translate(text, target_language=tr_cfg.get("target_language", "ja"))
        return res["translatedText"]
    except Exception as e:
        print(f"[WARN] translate failed: {e}")
        return text  # 失敗時は原文のまま返す


# ==============================
# Slack 通知
# ==============================
def post_to_slack_webhook(blocks: List[Dict[str, Any]]) -> None:
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        raise RuntimeError("SLACK_WEBHOOK_URL is not set")
    
    payload = {
        "username": CONFIG.get("slack", {}).get("username", "arXiv Bot"),
        "blocks": blocks,
    }
    
    # icon_urlが設定されている場合はそれを使用、なければicon_emojiを使用
    slack_config = CONFIG.get("slack", {})
    if slack_config.get("icon_url"):
        payload["icon_url"] = slack_config["icon_url"]
    else:
        payload["icon_emoji"] = slack_config.get("icon_emoji", ":newspaper:")
    
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()

def make_slack_blocks(entries: List[Tuple[Dict[str, Any], List[str]]]) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    header = {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"arXiv で公開された新着論文 ({NOW_LOCAL.strftime('%Y-%m-%d')})",
            "emoji": True,
        },
    }
    blocks.append(header)

    # 表示設定を取得
    display_config = CONFIG.get("display", {})
    show_keywords = display_config.get("show_keywords", True)
    show_abstract = display_config.get("show_abstract", False)
    show_translate = display_config.get("show_translate", False)

    for it, matched_keywords in entries:
        title = it["title"]
        url = it["link"]
        summary = it["summary"]
        
        # 基本情報（タイトルとURL）
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*<{url}|{title}>*"}})
        
        # キーワード表示
        if show_keywords and matched_keywords:
            clean_keywords = [kw.replace('\\', '') for kw in matched_keywords]
            keywords_text = "*キーワード:* " + ", ".join(clean_keywords)
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"{keywords_text}"}})
        
        # 概要表示
        if show_abstract:
            # 概要が長すぎる場合は切り詰める
            abstract_text = summary[:500] + "..." if len(summary) > 500 else summary
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*概要:* {abstract_text}"}})
        
        # 翻訳表示
        if show_translate and CONFIG.get("translate", {}).get("enabled", False):
            try:
                translated_summary = maybe_translate(summary)
                translated_text = translated_summary[:500] + "..." if len(translated_summary) > 500 else translated_summary
                blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*翻訳:* {translated_text}"}})
            except Exception as e:
                print(f"[WARN] Translation failed for {it['id']}: {e}")
        
        # メタ情報（IDと公開日時）
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"`{it['id']}`  •  published: {it['published']}",
                }
            ],
        })
        
        blocks.append({"type": "divider"})
    
    return blocks


# ==============================
# メイン
# ==============================
def main() -> None:
    cats: List[str] = CONFIG.get("categories", ["cs.CV"])
    kw_patterns = compile_kw_patterns(CONFIG.get("keywords", []))
    max_posts = int(CONFIG.get("max_posts", 20))

    print(f"[INFO] fetch from arXiv categories={cats}")
    items = fetch_arxiv(cats, max_results=200)

    selected = select_by_relevance(items, kw_patterns, max_posts=max_posts)
    if not selected:
        print("[INFO] no new items matched")
        return

    blocks = make_slack_blocks(selected)
    post_to_slack_webhook(blocks)

    # 既読IDを保存
    for it, _ in selected:
        SEEN.add(it["id"])
    SEEN_PATH.write_text(json.dumps(sorted(SEEN)), encoding="utf-8")
    print(f"[INFO] posted {len(selected)} items to Slack")


if __name__ == "__main__":
    main()
