import feedparser
import requests
import json
import os
import re
from datetime import datetime, timezone, timedelta

# IT・テクノロジー系フィード → #itニュース チャンネル
IT_FEEDS = [
    {"url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",  "label": "ITmedia NEWS"},
    {"url": "https://rss.itmedia.co.jp/rss/2.0/business.xml",     "label": "ITmediaビジネス"},
    {"url": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",       "label": "ITmedia AI+"},
    {"url": "https://techcrunch.com/feed/",                        "label": "TechCrunch"},
    {"url": "https://feeds.feedburner.com/oreilly/radar",          "label": "O'Reilly"},
    {"url": "https://gigazine.net/news/rss_2.0/",                  "label": "Gigazine"},
    {"url": "https://zenn.dev/feed",                               "label": "Zenn"},
]

# 政治・経済・ビジネス系フィード → #政治経済ニュース チャンネル
BIZECO_FEEDS = [
    {"url": "https://feeds.reuters.com/reuters/JPTopNews",              "label": "Reutersトップ"},
    {"url": "https://feeds.reuters.com/reuters/JPBusinessNews",         "label": "Reutersビジネス"},
    {"url": "https://www.bloomberg.co.jp/feeds/bbiz/sitemap.xml",       "label": "Bloomberg日本"},
    {"url": "https://toyokeizai.net/list/feed/rss",                     "label": "東洋経済"},
    {"url": "https://www.asahi.com/rss/politics.rdf",                   "label": "朝日新聞・政治"},
    {"url": "https://mainichi.jp/rss/etc/mainichi-flash.rss",           "label": "毎日新聞"},
    {"url": "https://www3.nhk.or.jp/rss/news/cat6.xml",                 "label": "NHK政治（無料）"},
]

IT_KEYWORDS = [
    "AI", "人工知能", "機械学習", "LLM", "生成AI", "ChatGPT", "DX", "デジタル",
    "Python", "セキュリティ", "クラウド", "サイバー", "データ", "ソフトウェア",
    "スタートアップ", "テクノロジー", "アプリ", "システム",
]

BIZECO_KEYWORDS = [
    "経済", "円安", "株価", "インフレ", "金利", "GDP", "景気", "物価", "賃上げ",
    "ビジネス", "M&A", "上場", "IPO", "投資", "決算",
    "政治", "選挙", "首相", "国会", "規制", "貿易", "関税", "米中", "日米", "外交",
    "内閣", "自民党", "野党", "法案", "予算", "衆議院", "参議院", "大臣",
]

HOURS_BACK = 24

SLACK_WEBHOOK_URL_IT     = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL_BIZECO = os.environ.get("SLACK_WEBHOOK_URL_BIZECO", "")


def clean_html(text):
    """HTMLタグを除去してプレーンテキストに変換"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#[0-9]+;', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def make_summary(entry, max_chars=120):
    """RSSエントリから要約文を生成（最大max_chars文字）"""
    # summary / description / content の順で取得
    raw = ""
    if entry.get("summary"):
        raw = entry["summary"]
    elif entry.get("description"):
        raw = entry["description"]
    elif entry.get("content"):
        raw = entry["content"][0].get("value", "")
    
    text = clean_html(raw)
    
    # 空または短すぎる場合はスキップ
    if len(text) < 10:
        return ""
    
    # max_chars文字で切り詰め、末尾に「…」
    if len(text) > max_chars:
        text = text[:max_chars] + "…"
    
    return text


def is_recent(entry, hours=HOURS_BACK):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - pub < timedelta(hours=hours)
    return True


def matches_keywords(entry, keywords):
    if not keywords:
        return True
    text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
    return any(kw.lower() in text for kw in keywords)


def post_to_slack(articles, webhook_url, channel_label):
    if not articles:
        print(f"[{channel_label}] 投稿する記事がありませんでした。")
        return

    now_jst = datetime.now(timezone(timedelta(hours=9))).strftime("%Y/%m/%d %H:%M")
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": f"📰 {channel_label} ニュース ({now_jst} JST)"}}]
    by_label = {}
    for a in articles:
        by_label.setdefault(a["label"], []).append(a)

    for label, items in by_label.items():
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*【{label}】*"}})
        for item in items:
            title = item["title"]
            url   = item["url"]
            summary = item.get("summary_text", "")
            
            # タイトルリンク
            article_text = f"• <{url}|{title}>"
            
            # 要約がある場合は改行して追加
            if summary:
                article_text += f"\n　_{summary}_"
            
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": article_text}})

    # Slackは1メッセージ最大50ブロック制限
    BLOCK_LIMIT = 49
    for i in range(0, len(blocks), BLOCK_LIMIT):
        chunk = blocks[i:i + BLOCK_LIMIT]
        payload = {"blocks": chunk}
        resp = requests.post(webhook_url, data=json.dumps(payload),
                             headers={"Content-Type": "application/json"})
        if resp.status_code != 200:
            print(f"[{channel_label}] Slack APIエラー: {resp.status_code} {resp.text}")
        else:
            print(f"[{channel_label}] {len([b for b in chunk if b['type']=='section' and '•' in b.get('text',{}).get('text','')])} 件投稿")


def fetch_articles(feeds, keywords):
    articles = []
    for feed_info in feeds:
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries:
                if not is_recent(entry):
                    continue
                if not matches_keywords(entry, keywords):
                    continue
                summary_text = make_summary(entry)
                articles.append({
                    "title": entry.get("title", "(タイトルなし)"),
                    "url":   entry.get("link", ""),
                    "label": feed_info["label"],
                    "summary_text": summary_text,
                })
        except Exception as e:
            print(f"フィード取得エラー ({feed_info['label']}): {e}")
    return articles


def main():
    # ITニュースを #itニュース に投稿
    it_articles = fetch_articles(IT_FEEDS, IT_KEYWORDS)
    print(f"IT記事数: {len(it_articles)}")
    if SLACK_WEBHOOK_URL_IT:
        post_to_slack(it_articles, SLACK_WEBHOOK_URL_IT, "ITニュース")
    else:
        print("SLACK_WEBHOOK_URL が未設定です。")

    # 政治経済ニュースを #政治経済ニュース に投稿
    bizeco_articles = fetch_articles(BIZECO_FEEDS, BIZECO_KEYWORDS)
    print(f"政治経済記事数: {len(bizeco_articles)}")
    if SLACK_WEBHOOK_URL_BIZECO:
        post_to_slack(bizeco_articles, SLACK_WEBHOOK_URL_BIZECO, "政治経済ニュース")
    else:
        print("SLACK_WEBHOOK_URL_BIZECO が未設定です。")


if __name__ == "__main__":
    main()
