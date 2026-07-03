import os, json, requests, feedparser, smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from gradio_client import Client

# ─── CONFIG ───────────────────────────────────
HF_TOKEN          = os.environ.get("HF_TOKEN", "")
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "")
HF_VOICE_URL      = "Vxrex/virex-voice"
HF_VIDEO_URL      = "Vxrex/virex-video"
PEXELS_API_KEY    = os.environ.get("PEXELS_API_KEY", "")
GMAIL_USER        = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASS    = os.environ.get("GMAIL_APP_PASSWORD", "")
EMAIL_TO          = os.environ.get("GMAIL_USER", "")  # sends to yourself
NICHE             = "AI & Tech"
VOICE             = "Guy (US Male, Energetic)"
OUTPUT_DIR        = "virex_outputs"
# ──────────────────────────────────────────────

RSS_FEEDS = [
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://venturebeat.com/feed/",
    "https://news.ycombinator.com/rss",
    "https://feeds.arstechnica.com/arstechnica/index",
]

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def fetch_headlines():
    headlines = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]:
                if entry.get("title"): headlines.append(entry.title)
        except Exception as e: log(f"Feed error: {e}")
    return list(set(headlines))

def call_groq(prompt, max_tokens=1500):
    res = requests.post(GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={"model": "llama-3.3-70b-versatile", "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]},
        timeout=30)
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]

def parse_json(raw):
    import re
    clean = raw.replace("```json","").replace("```","").strip()
    start, end = clean.find("["), clean.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("No JSON array found")
    json_str = clean[start:end+1]
    # Remove control characters that break JSON parsing
    json_str = re.sub(r'[\x00-\x1f\x7f](?!["\\/bfnrtu])', ' ', json_str)
    # Fix unescaped newlines inside strings
    json_str = re.sub(r'(?<!\\)\n', ' ', json_str)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Last resort: strip all non-printable characters
        json_str = ''.join(c for c in json_str if c.isprintable() or c in ' \t')
        return json.loads(json_str)

def score_trends(headlines):
    log("Scoring trends...")
    raw = call_groq(
        f"Score these topics 1-10 on: velocity, emotion, curiosity, controversy, novelty, "
        f"competition (1=crowded). total=sum.\n\nHeadlines:\n{chr(10).join(headlines)}\n\n"
        f"Return ONLY JSON:\n[{{\"title\":\"\",\"velocity\":0,\"emotion\":0,\"curiosity\":0,"
        f"\"controversy\":0,\"novelty\":0,\"competition\":0,\"total\":0,\"angle\":\"\"}}]\n"
        f"Top 3 only, sorted by total.")
    winner = parse_json(raw)[0]
    log(f"  Winner: {winner['title']} ({winner['total']}/60)")
    return winner

def generate_hook(topic, angle):
    log("Generating hook...")
    raw = call_groq(
        f"Topic: \"{topic}\" Angle: \"{angle}\"\n"
        f"Generate 5 viral hooks. Max 12 words. Never start with I.\n"
        f"Return ONLY JSON: [{{\"hook\":\"\",\"score\":0}}]\nSort by score.", 400)
    return parse_json(raw)[0]["hook"]

def write_script(hook, angle):
    log("Writing script...")
    raw = call_groq(
        f"Hook: \"{hook}\"\nAngle: \"{angle}\"\n"
        f"Write one 75-second script. Start with exact hook. Max 10 words per sentence. "
        f"10 sentences. End with: Follow VIREX for daily AI intel.\n"
        f"Return ONLY JSON: [{{\"script\":\"\"}}]", 600)
    return parse_json(raw)[0]["script"]

def generate_voice(script, out_path):
    import time, shutil
    log("Generating voiceover...")
    # Wake up sleeping HF Space
    space_url = f"https://{HF_VOICE_URL.replace('/', '-')}.hf.space"
    for i in range(3):
        try: requests.get(space_url, timeout=30); break
        except: time.sleep(10)
    time.sleep(8)
    for attempt in range(3):
        try:
            client = Client(HF_VOICE_URL, hf_token=HF_TOKEN, verbose=False)
            result = client.predict(script, VOICE, 0, 0, api_name="/predict")
            # Handle different return types across Gradio versions
            if isinstance(result, dict):
                file_path = result.get("path") or result.get("name")
            elif isinstance(result, tuple):
                file_path = result[0]
            else:
                file_path = str(result)
            if file_path and os.path.exists(file_path):
                shutil.copy(file_path, out_path)
                log("  Voiceover done ✓")
                return True
            else:
                log(f"  File not found at: {file_path}")
        except Exception as e:
            log(f"  Voice attempt {attempt+1} failed: {e}")
            time.sleep(15)
    return False

def generate_video(script, audio_path, out_path):
    import time, shutil
    log("Assembling video...")
    # Wake up sleeping HF Space
    space_url = f"https://{HF_VIDEO_URL.replace('/', '-')}.hf.space"
    for i in range(3):
        try: requests.get(space_url, timeout=30); break
        except: time.sleep(10)
    time.sleep(8)
    for attempt in range(3):
        try:
            client = Client(HF_VIDEO_URL, hf_token=HF_TOKEN, verbose=False)
            result = client.predict(script, audio_path, PEXELS_API_KEY, api_name="/predict")
            if isinstance(result, dict):
                file_path = result.get("path") or result.get("name")
            elif isinstance(result, tuple):
                file_path = result[0]
            else:
                file_path = str(result)
            if file_path and os.path.exists(file_path):
                shutil.copy(file_path, out_path)
                log("  Video done ✓")
                return True
            else:
                log(f"  File not found at: {file_path}")
        except Exception as e:
            log(f"  Video attempt {attempt+1} failed: {e}")
            time.sleep(15)
    return False

def upload_for_link(file_path):
    """Upload to file.io — free, auto-deletes after download, no signup."""
    try:
        with open(file_path, "rb") as f:
            r = requests.post("https://file.io", files={"file": f}, timeout=60)
        data = r.json()
        if data.get("success"): return data["link"]
    except Exception as e: log(f"  Upload error: {e}")
    return None

def send_email(subject, body_html, video_path=None, script_path=None):
    if not GMAIL_USER or not GMAIL_APP_PASS:
        log("  No email credentials — skipping")
        return

    log("Sending email...")
    msg = MIMEMultipart("mixed")
    msg["From"]    = GMAIL_USER
    msg["To"]      = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))

    # Attach video if under 20MB, else upload and link
    if video_path and os.path.exists(video_path):
        size_mb = os.path.getsize(video_path) / 1024 / 1024
        if size_mb < 20:
            log(f"  Attaching video ({size_mb:.1f}MB)...")
            with open(video_path, "rb") as f:
                part = MIMEBase("video", "mp4")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", 'attachment; filename="virex_video.mp4"')
                msg.attach(part)
        else:
            log(f"  Video too large ({size_mb:.1f}MB) — uploading for link...")
            link = upload_for_link(video_path)
            if link:
                msg.attach(MIMEText(
                    f"<p>Video too large to attach ({size_mb:.1f}MB). "
                    f"<a href='{link}'>Download here</a> (link expires after first download)</p>",
                    "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASS)
        server.sendmail(GMAIL_USER, EMAIL_TO, msg.as_string())
    log("  Email sent ✓")

def run():
    date_str = datetime.now().strftime("%Y-%m-%d")
    log(f"\n{'='*40}\nVIREX AUTOPILOT — {date_str}\n{'='*40}")

    headlines = fetch_headlines()
    if not headlines: log("No headlines."); return

    winner = score_trends(headlines)
    hook   = generate_hook(winner["title"], winner["angle"])
    script = write_script(hook, winner["angle"])

    folder = os.path.join(OUTPUT_DIR, date_str)
    os.makedirs(folder, exist_ok=True)

    script_path = os.path.join(folder, "script.txt")
    with open(script_path, "w") as f:
        f.write(f"VIREX — {date_str}\n{'='*40}\n"
                f"TOPIC: {winner['title']}\nSCORE: {winner['total']}/60\n"
                f"HOOK:  {hook}\n\nSCRIPT:\n{script}")

    audio_path = os.path.join(folder, "voiceover.mp3")
    voice_ok   = generate_voice(script, audio_path)

    video_path = os.path.join(folder, "video.mp4")
    video_ok   = generate_video(script, audio_path, video_path) if voice_ok else False

    # Build email
    email_body = f"""
    <div style="font-family:monospace;background:#04040A;color:#fff;padding:24px;border-radius:12px">
        <h2 style="color:#FF2D55">⚡ VIREX Daily Drop — {date_str}</h2>
        <p><strong>TOPIC:</strong> {winner['title']}</p>
        <p><strong>VIRALITY SCORE:</strong> {winner['total']}/60</p>
        <p><strong>ANGLE:</strong> {winner['angle']}</p>
        <p><strong>HOOK:</strong> <span style="color:#00E5FF">"{hook}"</span></p>
        <hr style="border-color:#1A1A30"/>
        <h3 style="color:#00FF94">SCRIPT</h3>
        <p style="line-height:1.8;color:#D0D0E8">{script.replace(chr(10),'<br>')}</p>
        <hr style="border-color:#1A1A30"/>
        <p style="color:#525270;font-size:12px">
            Voice: {'✓' if voice_ok else '✗'} &nbsp;|&nbsp;
            Video: {'✓ attached' if video_ok else '✗'}
        </p>
    </div>
    """

    send_email(
        subject=f"⚡ VIREX — {winner['title'][:50]} ({date_str})",
        body_html=email_body,
        video_path=video_path if video_ok else None,
        script_path=script_path)

    log(f"\n✓ PIPELINE COMPLETE\n"
        f"  Topic: {winner['title']}\n"
        f"  Score: {winner['total']}/60\n"
        f"  Voice: {'✓' if voice_ok else '✗'}\n"
        f"  Video: {'✓' if video_ok else '✗'}\n"
        f"  Email: {'✓' if GMAIL_USER else 'skipped'}")

if __name__ == "__main__":
    run()
