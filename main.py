import os
import datetime
import openai
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from notion_client import Client
from dotenv import load_dotenv

# ローカル実行時に .env を読み込む（GitHub Actions では不要ですが無害です）
load_dotenv()

print("=== 🚀 main.pyが動き始めました ===")

# 環境変数読み込み
openai.api_key = os.getenv("OPENAI_API_KEY")
CHANNELS      = os.getenv("CHANNEL_IDS", "").split(",")
NOTION_TOKEN  = os.getenv("NOTION_TOKEN")
NOTION_DB_ID  = os.getenv("NOTION_DB_ID")
YT_API_KEY    = os.getenv("YT_API_KEY")

def summarize(text):
    """OpenAI で要約を取得"""
    print("▶ OpenAI要約開始 ...")
    res = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": f"次を日本語で3行に要約し、最後にキーワード5つ: {text}"
        }],
        temperature=0.3
    )
    summary = res.choices[0].message.content.strip()
    print("▶ 要約完了")
    return summary

def build_page(item, summary):
    """Notion ページ作成用の payload 組み立て"""
    vid  = item["id"]["videoId"]
    sn  = item["snippet"]
    url = f"https://youtu.be/{vid}"
    return {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Title":   {"title": [{"text": {"content": sn["title"]}}]},
            "Date":    {"date": {"start": sn["publishedAt"]}},
            "Channel": {"select": {"name": sn["channelTitle"]}},
            "URL":     {"url": url}
        },
        "children": [
            {
                "object":"block","type":"paragraph",
                "paragraph": {
                    "rich_text":[{"text":{"content": summary}}]
                }
            }
        ]
    }

def main():
    # 環境変数チェック
    print("▶ 環境変数チェック:")
    print("   OPENAI_API_KEY:", bool(openai.api_key))
    print("   NOTION_TOKEN:",   bool(NOTION_TOKEN))
    print("   NOTION_DB_ID:",   NOTION_DB_ID)
    print("   YT_API_KEY:",     bool(YT_API_KEY))
    print("   CHANNEL_IDS:",    CHANNELS)

    yt = build("youtube", "v3", developerKey=YT_API_KEY)
    after = (datetime.datetime.utcnow() - datetime.timedelta(days=1))\
            .isoformat("T") + "Z"
    notion = Client(auth=NOTION_TOKEN)

    for cid in CHANNELS:
        cid = cid.strip()
        if not cid:
            continue
        print(f"▶ チャンネルID {cid} を処理中 ...")
        res = yt.search().list(
            part="id,snippet",
            channelId=cid,
            publishedAfter=after,
            type="video",
            order="date"
        ).execute()
        items = res.get("items", [])
        print(f"▶ 新着動画件数: {len(items)} 件")

        for it in items:
            vid = it["id"]["videoId"]
            print("▶ 処理対象動画ID:", vid)
            # 字幕取得
            try:
                transcripts = YouTubeTranscriptApi.get_transcript(
                    vid, languages=['ja','en']
                )
                txt = " ".join([t["text"] for t in transcripts])[:3500]
                print("▶ 字幕取得テキスト長:", len(txt))
            except Exception as e:
                print("❌ 字幕取得失敗:", e)
                continue

            # 要約
            smry = summarize(txt)
            print("▶ 要約結果（先頭30文字）:", smry[:30])

            # Notion に投げる
            payload = build_page(it, smry)
            print("▶ Notion に送るデータ例:", payload)
            try:
                notion.pages.create(**payload)
                print("✅ Notion 送信 完了!")
            except Exception as e:
                print("❌ Notion ページ作成 エラー:", e)

if __name__ == "__main__":
    main()
