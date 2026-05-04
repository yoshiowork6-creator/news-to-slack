import feedparser
import requests
import json
import os
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
    {"url": "https://feeds.reuters.com/reuters/JPBusinessNews",    "label": "Reutersビジネス"},
    {"url": "https://feeds.reuters.com/reuters/JPTopNews",         "label": "Reutersトップ"},
    {"url": "https://www.bloomberg.co.jp/feeds/bbiz/sitemap.xml",  "label": "Bloomberg日本"},
    {"url": "https://toyokeizai.net/list/feed/rss",                "label": "東洋経済"},
]

# IT系キーワード
IT_KEYWORDS = [
    "AI", "人工知能", "機械学習", "LLM", "生成AI", "ChatGPT", "DX", "デジタル",
    "Python", "セキュリティ", "クラウド", "サイバー", "データ", "ソフトウェア",
    "スタートアップ", "テクノロジー", "アプリ", "システム",
]

# 政治経済系キーワード
BIZECO_KEYWORDS = [
    "経済", "円安", "円高", "株価", "日経平均", "インフレ", "金利", "GDP", "景気",
    "物価", "賃上げ", "賃金", "雇用", "失業率",
    "ビジネス", "経営", "M&A", "上場", "IPO", "投資", "売上", "利益", "業績", "決算",
    "政治", "選挙", "政府", "首相", "内閣", "国会", "規制", "政策", "法律",
    "貿易", "関税", "米中", "日米", "外交",
]

HOURS_BACK = 24
SLACK_WEBHOOK_URL_IT     = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL_BIZECO = os.environ.get("SLACK_WEBHOOK_URL_BIZECO", "")

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
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": f"📰 {channel_label} ({now_jst} JST)"}}]
    by_label = {}
    for a in articles:
        by_label.setdefault(a["label"], []).append(a)
    for label, items in by_label.items():
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{label}*"}})
        for item in items[:5]:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"• <{item['link']}|{item['title']}>"}})
    payload = {"blocks": blocks}
    resp = requests.post(webhook_url, data=json.dumps(payload), headers={"Content-Type": "application/json"})
    if resp.status_code == 200:
        print(f"[{channel_label}] ✅ {len(articles)} 件の記事をSlackに投稿しました。")
    else:
        print(f"[{channel_label}] ❌ Slack投稿エラー: {resp.status_code} {resp.text}")

def fetch_articles(feeds, keywords):
    articles = []
    for feed_info in feeds:
        print(f"取得中: {feed_info['label']} ...")
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries:
                if is_recent(entry) and matches_keywords(entry, keywords):
                    articles.append({
                        "label": feed_info["label"],
                        "title": entry.get("title", "(タイトルなし)"),
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", ""),
                    })
        except Exception as e:
            print(f"  ⚠ 取得失敗: {e}")
    return articles

def main():
    if not SLACK_WEBHOOK_URL_IT:
        raise ValueError("SLACK_WEBHOOK_URL が設定されていません。")
    if not SLACK_WEBHOOK_URL_BIZECO:
        raise ValueError("SLACK_WEBHOOK_URL_BIZECO が設定されていません。")

    # ITニュース
    print("=== IT・テクノロジー系ニュース取得 ===")
    it_articles = fetch_articles(IT_FEEDS, IT_KEYWORDS)
    print(f"IT系: {len(it_articles)} 件")
    post_to_slack(it_articles, SLACK_WEBHOOK_URL_IT, "ITニュースまとめ")

    # 政治経済ニュース
    print("=== 政治・経済系ニュース取得 ===")
    bizeco_articles = fetch_articles(BIZECO_FEEDS, BIZECO_KEYWORDS)
    print(f"政治経済系: {len(bizeco_articles)} 件")
    post_to_slack(bizeco_articles, SLACK_WEBHOOK_URL_BIZECO, "政治経済ニュースまとめ")

if __name__ == "__main__":
    main()
