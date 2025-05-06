import os
import datetime
import pytz
import openai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from notion_client import Client

# 環境変数から各種キー・チャンネルIDを取得
openai.api_key = os.getenv("OPENAI_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DB_ID = os.getenv("NOTION_DB_ID")
YT_API_KEY = os.getenv("YT_API_KEY")
CHANNELS = os.getenv("CHANNEL_IDS", "").split(",")

# 要約用モデル・パラメータ
OPENAI_MODEL = "gpt-4o-mini"
SUMMARY_TOKENS_LIMIT = 3500  # 字幕から切り出す最大文字数

def summarize(text: str) -> str:
    """
    OpenAI に渡して日本語3行＋キーワード5つを返す。
    """
    prompt = (
        "次のYouTube字幕を日本語で3行以内に要約し、最後にキーワードを5つカンマ区切りで出力してください：\n"
        f"{text}"
    )
    res = openai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return res.choices[0].message.content.strip()

def main():
    # ── JST 前日 0:00 を計算して UTC に変換 ──
    jst = pytz.timezone("Asia/Tokyo")
    now_jst = datetime.datetime.now(jst)
    prev_midnight_jst = (now_jst - datetime.timedelta(days=1)) \
        .replace(hour=0, minute=0, second=0, microsecond=0)
    after = prev_midnight_jst.astimezone(pytz.UTC).isoformat().replace("+00:00", "Z")

    print(f"[DEBUG] Run at JST {now_jst.isoformat()} → fetching videos published after UTC {after}")

    # YouTube Data API クライアント
    yt = build("youtube", "v3", developerKey=YT_API_KEY)

    # Notion クライアント
    notion = Client(auth=NOTION_TOKEN)

    for cid in CHANNELS:
        # 新着動画取得
        res = yt.search().list(
            part="id,snippet",
            channelId=cid,
            publishedAfter=after,
            type="video",
            order="date",
            maxResults=10
        ).execute()

        items = res.get("items", [])
        print(f"[DEBUG] Channel {cid}: found {len(items)} items")
        for it in items:
            vid = it["id"]["videoId"]
            title = it["snippet"]["title"]
            published_at = it["snippet"]["publishedAt"]
            print(f"[DEBUG]  → videoId={vid}, title={title}, publishedAt={published_at}")

            # 字幕取得
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(
                    vid, languages=['ja', 'en']
                )
                text = " ".join(t["text"] for t in transcript_list)[:SUMMARY_TOKENS_LIMIT]
            except Exception as e:
                print(f"[WARN] transcript missing for {vid}: {e}")
                continue

            # 要約
            try:
                summary = summarize(text)
                print(f"[DEBUG] summary:\n{summary}")
            except Exception as e:
                print(f"[ERROR] summarization failed for {vid}: {e}")
                continue

            # Notion へ登録
            page = {
                "parent": {"database_id": NOTION_DB_ID},
                "properties": {
                    "Title":   {"title": [{"text": {"content": title}}]},
                    "Date":    {"date":  {"start": published_at}},
                    "Channel": {"select": {"name": it["snippet"]["channelTitle"]}},
                    "URL":     {"url":   f"https://youtu.be/{vid}"}},
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"text": {"content": summary}}]
                        }
                    }
                ]
            }
            try:
                notion.pages.create(**page)
                print(f"[INFO] Notion page created for {vid}")
            except Exception as e:
                print(f"[ERROR] failed to create Notion page for {vid}: {e}")

if __name__ == "__main__":
    main()

