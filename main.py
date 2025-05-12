import os
from datetime import datetime
from zoneinfo import ZoneInfo

from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
import openai
from notion_client import Client as NotionClient

# ── 環境変数 ──
CHANNEL_IDS     = os.getenv("CHANNEL_IDS", "")            # カンマ区切りで複数指定可
NOTION_DB_ID    = os.getenv("NOTION_DB_ID")
NOTION_TOKEN    = os.getenv("NOTION_TOKEN")
OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY")
TZ              = os.getenv("TZ", "UTC")                  # ex: "Asia/Tokyo"
YT_API_KEY      = os.getenv("YT_API_KEY")

# ── クライアント初期化 ──
channel_ids = [cid.strip() for cid in CHANNEL_IDS.split(",") if cid.strip()]
youtube     = build("youtube", "v3", developerKey=YT_API_KEY)
openai.api_key = OPENAI_API_KEY
notion      = NotionClient(auth=NOTION_TOKEN)

def get_latest_video_id(channel_id: str) -> str:
    res = youtube.channels().list(
        part="contentDetails",
        id=channel_id
    ).execute()
    uploads_id = res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    playlist = youtube.playlistItems().list(
        playlistId=uploads_id,
        part="snippet",
        maxResults=1
    ).execute()
    return playlist["items"][0]["snippet"]["resourceId"]["videoId"]

def fetch_transcript(video_id: str) -> str:
    segments = YouTubeTranscriptApi.get_transcript(
        video_id,
        languages=["ja", "en"]
    )
    return "\n".join(seg["text"] for seg in segments)

def summarize(text: str, title: str) -> str:
    prompt = (
        f"あなたは要約のプロです。以下のYoutube動画の文字起こしを完璧に学べるように要約してください。\n"
        f"タイトル: {title}\n\n"
        f"{text}"
    )
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500
    )
    return resp.choices[0].message.content.strip()

def add_to_notion(title: str, summary: str, video_url: str):
    now = datetime.now(ZoneInfo(TZ))
    notion.pages.create(
        parent={"database_id": NOTION_DB_ID},
        properties={
            "Date":      {"date": {"start": now.isoformat()}},
            "Title":     {"title": [{"text": {"content": title}}]},
            "Video URL": {"url": video_url}
        },
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": summary}}]
                }
            }
        ]
    )

def main():
    if not channel_ids:
        print("❌ CHANNEL_IDS が設定されていません")
        return

    for channel_id in channel_ids:
        # 1. 最新動画ID取得
        vid = get_latest_video_id(channel_id)
        # 2. 動画タイトル取得
        video_info = youtube.videos().list(
            part="snippet",
            id=vid
        ).execute()
        title = video_info["items"][0]["snippet"]["title"]
        # 3. URL 作成
        url = f"https://youtu.be/{vid}"
        # 4. 文字起こし取得
        transcript = fetch_transcript(vid)
        # 5. 要約生成
        summary = summarize(transcript, title)
        # 6. Notion に追加
        add_to_notion(title, summary, url)
        print(f"✅ Added to Notion: {title}")

if __name__ == "__main__":
    main()





