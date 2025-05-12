import os
from datetime import datetime, timezone, timedelta

from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
import openai
from notion_client import Client as NotionClient

# ── 環境変数 ──
YOUTUBE_API_KEY    = os.getenv("YOUTUBE_API_KEY")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
NOTION_API_KEY     = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
CHANNEL_ID         = os.getenv("CHANNEL_ID")  # GitHub Secrets に設定済み

# ── クライアント初期化 ──
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
openai.api_key = OPENAI_API_KEY
notion = NotionClient(auth=NOTION_API_KEY)

def get_latest_video_id(channel_id: str) -> str:
    """指定チャンネルの最新動画IDを取得"""
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
    """YouTube の文字起こしを取得してテキストに結合"""
    segments = YouTubeTranscriptApi.get_transcript(
        video_id,
        languages=["ja", "en"]
    )
    return "\n".join(seg["text"] for seg in segments)

def summarize(text: str, title: str) -> str:
    """ChatGPT に要約をお願いする"""
    prompt = (
        f"以下の文字起こしを日本語で簡潔に要約してください。\n"
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
    """Notion データベースに「本日の学びニュース」として追記"""
    # JST（UTC+9）で現在時刻を生成
    now = datetime.now(timezone(timedelta(hours=9)))
    notion.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
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
    # 1. 最新動画ID取得
    vid = get_latest_video_id(CHANNEL_ID)
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
    print(f"✅



