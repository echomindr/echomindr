"""
Echomindr MVP — Download & Metadata Generator
Usage: python echomindr_download.py <youtube_url>

Downloads audio from YouTube and generates the metadata JSON file.
Both files are saved in the ./episodes/ directory.

Requires: pip install yt-dlp

Example:
  python echomindr_download.py "https://www.youtube.com/watch?v=BhHfnXOgtIE"
  
This will create:
  ./episodes/airbnb-joe-gebbia/audio.mp3
  ./episodes/airbnb-joe-gebbia/meta.json
"""

import subprocess
import json
import sys
import os
import re


def slugify(text):
    """Convert text to a clean folder name."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')[:80]


def get_video_info(url):
    """Extract video metadata using yt-dlp without downloading."""
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-download",
        url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error getting video info: {result.stderr}")
        sys.exit(1)
    return json.loads(result.stdout)


def download_audio(url, output_path):
    """Download audio as MP3 using yt-dlp."""
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", output_path,
        url
    ]
    print(f"Downloading audio...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error downloading: {result.stderr}")
        sys.exit(1)
    print(f"Audio saved: {output_path}")


def guess_podcast_info(title, channel):
    """Try to extract podcast name, guest, and episode title from video metadata."""
    # Common patterns
    podcast_name = channel
    guest = ""
    episode_title = title

    # How I Built This pattern: "Guest Name: Company — How I Built This"
    hibt_match = re.match(r'(.+?)[\s]*[-—:|\|][\s]*How I Built This', title, re.IGNORECASE)
    if hibt_match:
        podcast_name = "How I Built This"
        episode_title = hibt_match.group(1).strip()

    # Lenny's Podcast pattern: "Topic | Guest Name (Company)"
    lenny_match = re.match(r'(.+?)\|(.+?)[\(\[]', title)
    if lenny_match:
        podcast_name = "Lenny's Podcast"
        episode_title = lenny_match.group(1).strip()
        guest = lenny_match.group(2).strip()

    # 20VC pattern: "20VC: Title with Guest Name"
    vc_match = re.match(r'20VC:\s*(.+)', title)
    if vc_match:
        podcast_name = "20 Minute VC"
        episode_title = vc_match.group(1).strip()

    # My First Million pattern
    if "my first million" in title.lower() or "my first million" in channel.lower():
        podcast_name = "My First Million"

    # Acquired pattern
    if "acquired" in channel.lower():
        podcast_name = "Acquired"

    # Y Combinator pattern
    if "y combinator" in channel.lower():
        podcast_name = "Y Combinator / Startup School"

    # Indie Hackers pattern
    if "indie hackers" in channel.lower():
        podcast_name = "Indie Hackers"

    return podcast_name, episode_title, guest


def main():
    if len(sys.argv) < 2:
        print("Usage: python echomindr_download.py <youtube_url>")
        print('Example: python echomindr_download.py "https://www.youtube.com/watch?v=BhHfnXOgtIE"')
        sys.exit(1)

    url = sys.argv[1]

    # Step 1: Get video metadata
    print(f"Fetching video info for: {url}")
    info = get_video_info(url)

    title = info.get("title", "Unknown")
    channel = info.get("channel", info.get("uploader", "Unknown"))
    upload_date = info.get("upload_date", "")  # YYYYMMDD format
    description = info.get("description", "")
    duration = info.get("duration", 0)

    # Format date
    if upload_date and len(upload_date) == 8:
        date_formatted = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
        year = upload_date[:4]
    else:
        date_formatted = "Unknown"
        year = "Unknown"

    # Step 2: Guess podcast info
    podcast_name, episode_title, guest = guess_podcast_info(title, channel)

    # Step 3: Create output directory
    slug = slugify(episode_title)
    episode_dir = os.path.join("episodes", slug)
    os.makedirs(episode_dir, exist_ok=True)

    # Step 4: Download audio
    audio_path = os.path.join(episode_dir, "audio.mp3")
    if os.path.exists(audio_path):
        print(f"Audio already exists: {audio_path}, skipping download.")
    else:
        download_audio(url, audio_path)

    # Step 5: Build metadata
    meta = {
        "podcast": podcast_name,
        "episode": episode_title,
        "guest": guest if guest else "TODO — fill in guest name and role",
        "date": date_formatted,
        "url": url,
        "duration_seconds": duration,
        "channel": channel,
        "original_title": title
    }

    # Step 6: Save metadata
    meta_path = os.path.join(episode_dir, "meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"Episode directory: {episode_dir}/")
    print(f"Audio:    {audio_path}")
    print(f"Metadata: {meta_path}")
    print(f"Duration: {duration // 60}m {duration % 60}s")
    print(f"{'='*60}")
    print(f"\nMetadata generated:")
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"\n⚠️  REVIEW meta.json — verify and complete:")
    print(f"   - 'guest' field (add name and role)")
    print(f"   - 'podcast' field (verify detection)")
    print(f"   - 'episode' field (clean up if needed)")
    print(f"\nNext steps:")
    print(f"   1. Review & fix meta.json")
    print(f"   2. Send audio.mp3 to Deepgram")
    print(f"   3. Save Deepgram output as {episode_dir}/deepgram.json")
    print(f"   4. Run: python echomindr_extract.py {episode_dir}/deepgram.json {episode_dir}/moments.json --meta {meta_path}")


if __name__ == "__main__":
    main()
