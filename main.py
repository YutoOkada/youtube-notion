print("=== 🚀 main.pyが動き始めました ===")

import os, datetime, openai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from notion_client import Client

openai.api_key = os.getenv("OPENAI_API_KEY")
CHANNELS = os.getenv("CHANNEL_IDS").split(",")

def summarize(text):
    res = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user",
                   "content":f"次を日本語で3行に要約し、最後にキーワード5つ: {text}"}],
        temperature=0.3)
    return res.choices[0].message.content.strip()

def main():
    yt = build("youtube", "v3", developerKey=os.getenv("YT_API_KEY"))
    after = (datetime.datetime.utcnow()-datetime.timedelta(days=1)).isoformat("T")+"Z"
    notion = Client(auth=os.getenv("NOTION_TOKEN"))
    for cid in CHANNELS:
        vids = yt.search().list(part="id,snippet", channelId=cid,
                                publishedAfter=after,
                                type="video", order="date").execute()
        for it in vids.get("items", []):
            vid = it["id"]["videoId"]
            try:
                txt = " ".join(t["text"] for t in
                               YouTubeTranscriptApi.get_transcript(vid,
                               languages=['ja','en']))[:3500]
            except Exception:
                continue  # 字幕なし
            smry = summarize(txt)
            notion.pages.create(
              parent={"database_id":os.getenv("NOTION_DB_ID")},
              properties={
                "Title":   {"title":[{"text":{"content":it['snippet']['title']}}]},
                "Date":    {"date":{"start":it['snippet']['publishedAt']}},
                "Channel": {"select":{"name":it['snippet']['channelTitle']}},
                "URL":     {"url":f"https://youtu.be/{vid}"} },
              children=[{"object":"block","type":"paragraph",
                         "paragraph":{"rich_text":[{"text":{"content":smry}}]}}])

if __name__ == "__main__":
    main()
