import feedparser
import requests
import json
import os
from datetime import datetime, timezone, timedelta

RSS_FEEDS = [
    # IT・テクノロジー系
    {"url": "https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml",  "label": "ITmedia NEWS"},
    {"url": "https://rss.itmedia.co.jp/rss/2.0/business.xml",     "label": "ITmediaビジネス"},
    {"url": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",       "label": "ITmedia AI+"},
    {"url": "https://techcrunch.com/feed/",                        "label": "TechCrunch"},
    {"url": "https://feeds.feedburner.com/oreilly/radar",          "label": "O'Reilly"},
    {"url": "https://gigazine.net/news/rss_2.0/",                  "label": "Gigazine"},
    {"url": "https://zenn.dev/feed",                               "label": "Zenn"},
    # 政治・経済・ビジネス系（無料）
    {"url": "https://feeds.reuters.com/reuters/JPBusinessNews",    "label": "Reutersビジネス"},
    {"url": "https://feeds.reuters.com/reuters/JPTopNews",         "label": "Reutersトップ"},
    {"url": "https://www.bloomberg.co.jp/feeds/bbiz/sitemap.xml",  "label": "Bloomberg日本"},
    {"url": "https://toyokeizai.net/list/feed/rss",                "label": "東洋経済"},
]

FILTER_KEYWORDS = [
    # AI・テクノロジー
    "AI", "人工知能", "機械学習", "LLM", "生成AI", "ChatGPT", "DX", "デジタル",
    # 経済・金融（クライアント対話向け）
    "経済", "円安", "円高", "株価", "日経平均", "インフレ", "金利", "GDP", "景気",
    "物価", "賃上げ", "賃金", "雇用", "失業率",
    # ビジネス・経営
    "ビジネス", "経営", "M&A", "上場", "IPO", "スタートアップ", "投資",
    "売上", "利益", "業績", "決算",
    # 政治・社会（クライアント対話向け）
    "政治", "選挙", "政府", "首相", "内閣", "国会", "規制", "政策", "法律",
    "貿易", "関税", "米中", "日米", "外交",
    # IT・セキュリティ
    "Python", "セキュリティ", "クラウド", "サイバー", "データ",
]

HOURS_BACK = 24
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

def is_recent(entry, hours=HOURS_BACK):
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - pub < timedelta(hours=hours)
    return True

def matches_keywords(entry):
    if not FILTER_KEYWORDS:
        return True
    text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
    return any(kw.lower() in text for kw in FILTER_KEYWORDS)

def post_to_slack(articles):
    if not articles:
        print("投稿する記事がありませんでした。")
        return
    now_jst = datetime.now(timezone(timedelta(hours=9))).strftime("%Y/%m/%d %H:%M")
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": f"📰 ニュースまとめ ({now_jst} JST)"}}]
    by_label = {}
    for a in articles:
        by_label.setdefault(a["label"], []).append(a)
    for label, items in by_label.items():
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{label}*"}})
        for item in items[:5]:
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"• <{item['link']}|{item['title']}>"}})
    payload = {"blocks": blocks}
    resp = requests.post(SLACK_WEBHOOK_URL, data=json.dumps(payload), headers={"Content-Type": "application/json"})
    if resp.status_code == 200:
        print(f"✅ {len(articles)} 件の記事をSlackに投稿しました。")
    else:
        print(f"❌ Slack投稿エラー: {resp.status_code} {resp.text}")

def main():
    if not SLACK_WEBHOOK_URL:
        raise ValueError("SLACK_WEBHOOK_URL が設定されていません。")
    all_articles = []
    for feed_info in RSS_FEEDS:
        print(f"取得中: {feed_info['label']} ...")
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries:
                if is_recent(entry) and matches_keywords(entry):
                    all_articles.append({"label": feed_info["label"], "title": entry.get("title", "(タイトルなし)"), "link": entry.get("link", ""), "summary": entry.get("summary", "")})
        except Exception as e:
            print(f"  ⚠ 取得失敗: {e}")
    print(f"合計 {len(all_articles)} 件の記事が見つかりました。")
    post_to_slack(all_articles)

if __name__ == "__main__":
    main()
