"""
mcpos/ops/comments.py — YouTube comment monitoring and auto-reply

Patrols recent comments across channels, classifies them, and generates
replies using Claude API.

Usage:
    import asyncio
    from mcpos.ops.comments import patrol_all_channels
    asyncio.run(patrol_all_channels(channels_root, ["kat", "sg"], since_hours=24))
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from ..core.logging import log_info, log_warning, log_error


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class CommentThread:
    thread_id: str
    video_id: str
    author: str
    text: str
    published_at: datetime
    like_count: int = 0
    reply_count: int = 0


@dataclass
class ReplyResult:
    thread_id: str
    reply_text: str
    success: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

def classify_comment(text: str) -> str:
    """
    Rule-based comment classifier.

    Returns: "question" | "positive" | "negative" | "spam" | "ignore"
    """
    lower = text.lower()

    spam_patterns = [
        "subscribe to my", "check out my channel", "follow me",
        "sub for sub", "click here", "free gift",
    ]
    if any(p in lower for p in spam_patterns) or lower.count("http") > 0:
        return "spam"

    question_patterns = ["?", "what ", "where ", "when ", "how ", "why ", "which ", "who "]
    if any(p in lower for p in question_patterns):
        return "question"

    positive_patterns = [
        "love", "amazing", "beautiful", "great", "wonderful", "perfect",
        "thank", "best", "❤", "🙏", "😍", "awesome", "incredible", "peaceful",
    ]
    if any(p in lower for p in positive_patterns):
        return "positive"

    negative_patterns = [
        "hate", "bad", "worst", "terrible", "awful", "boring", "dislike",
        "annoying", "delete", "trash",
    ]
    if any(p in lower for p in negative_patterns):
        return "negative"

    # Too short to be meaningful
    if len(text.strip()) < 5:
        return "ignore"

    return "ignore"


# ---------------------------------------------------------------------------
# Reply generator
# ---------------------------------------------------------------------------

def generate_reply(comment: CommentThread, channel_id: str) -> Optional[str]:
    """Generate a reply using Claude API. Returns None if unavailable."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        config_file = Path(__file__).parent.parent.parent / "config" / "anthropic_api_key.txt"
        if config_file.exists():
            api_key = config_file.read_text(encoding="utf-8").strip() or None

    if not api_key:
        return None

    channel_names = {
        "kat": "Kat Records Studio",
        "rbr": "Run Baby Run",
        "sg": "Sleep in Grace",
    }
    channel_name = channel_names.get(channel_id, channel_id)

    prompt = (
        f"You are a friendly YouTube channel manager for {channel_name}.\n\n"
        f'A viewer left this comment: "{comment.text}"\n\n'
        f"Write a warm, genuine reply (1–2 sentences). Be authentic, not corporate. "
        f"Do NOT use excessive emojis. Keep it human and brief.\n"
        f"Reply ONLY with the reply text, no quotes or labels."
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception as e:
        log_warning(f"[comments] Claude API error: {e}")
        return None


def default_reply(comment_type: str, channel_id: str) -> str:
    """Template-based fallback replies."""
    replies: dict[str, str] = {
        "positive": "Thank you so much! Your kind words mean a lot to us. 🙏",
        "question": "Thanks for your question! We'll look into this and get back to you soon.",
        "negative": "Thank you for the honest feedback — we always want to do better.",
    }
    return replies.get(comment_type, "Thank you for watching and for your comment! 🎵")


# ---------------------------------------------------------------------------
# Patrol logic
# ---------------------------------------------------------------------------

async def patrol_channel(
    channel_id: str,
    service,
    since_hours: int = 24,
    max_replies: int = 10,
    dry_run: bool = False,
) -> list[ReplyResult]:
    """
    Patrol a channel's recent comments and reply to actionable ones.

    Args:
        channel_id: Channel identifier (for logging and tone).
        service: Authenticated YouTube API v3 Resource.
        since_hours: Only process comments newer than this.
        max_replies: Cap on replies per patrol run (quota protection).
        dry_run: Generate but don't post replies.

    Returns:
        List of ReplyResult for each comment acted on.
    """
    if service is None:
        log_warning(f"[comments] No YouTube service for '{channel_id}', skipping")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    results: list[ReplyResult] = []
    reply_count = 0

    try:
        # Discover channel's uploads playlist
        ch_resp = service.channels().list(part="contentDetails", mine=True).execute()
        if not ch_resp.get("items"):
            log_warning(f"[comments] No channel found for '{channel_id}'")
            return []

        uploads_id = (
            ch_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        )

        # Get recent videos
        pl_resp = service.playlistItems().list(
            part="snippet", playlistId=uploads_id, maxResults=10
        ).execute()

        video_ids = [
            item["snippet"]["resourceId"]["videoId"]
            for item in pl_resp.get("items", [])
        ]

        for video_id in video_ids:
            if reply_count >= max_replies:
                break

            try:
                threads_resp = service.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    order="time",
                    maxResults=25,
                ).execute()

                for item in threads_resp.get("items", []):
                    if reply_count >= max_replies:
                        break

                    snippet = item["snippet"]["topLevelComment"]["snippet"]
                    published = datetime.fromisoformat(
                        snippet["publishedAt"].replace("Z", "+00:00")
                    )
                    if published < cutoff:
                        continue
                    if item["snippet"].get("totalReplyCount", 0) > 0:
                        continue  # already has a reply

                    comment = CommentThread(
                        thread_id=item["id"],
                        video_id=video_id,
                        author=snippet.get("authorDisplayName", ""),
                        text=snippet.get("textDisplay", ""),
                        published_at=published,
                        like_count=snippet.get("likeCount", 0),
                    )

                    comment_type = classify_comment(comment.text)
                    if comment_type in ("spam", "ignore"):
                        continue

                    reply_text = (
                        generate_reply(comment, channel_id)
                        or default_reply(comment_type, channel_id)
                    )

                    if not dry_run:
                        try:
                            service.comments().insert(
                                part="snippet",
                                body={
                                    "snippet": {
                                        "parentId": comment.thread_id,
                                        "textOriginal": reply_text,
                                    }
                                },
                            ).execute()
                            reply_count += 1
                            log_info(f"[comments] Replied to {comment.thread_id} (video={video_id})")
                        except Exception as e:
                            log_error(f"[comments] Failed to post reply: {e}")
                            results.append(ReplyResult(comment.thread_id, reply_text, False, str(e)))
                            continue
                    else:
                        log_info(f"[comments] DRY RUN reply to {comment.thread_id}: {reply_text[:60]}...")

                    results.append(ReplyResult(comment.thread_id, reply_text, True))

            except Exception as e:
                log_warning(f"[comments] Error fetching comments for video {video_id}: {e}")

    except Exception as e:
        log_error(f"[comments] patrol_channel failed for '{channel_id}': {e}")

    log_info(f"[comments] '{channel_id}': {len(results)} comments handled")
    return results


async def patrol_all_channels(
    channels_root: Path,
    channel_ids: list[str],
    since_hours: int = 24,
    dry_run: bool = False,
) -> dict[str, list[ReplyResult]]:
    """Patrol comments across all given channels."""
    from ..upload.oauth import ChannelOAuth

    all_results: dict[str, list[ReplyResult]] = {}

    for channel_id in channel_ids:
        log_info(f"[comments] Patrolling '{channel_id}'...")
        oauth = ChannelOAuth(channel_id, channels_root)
        if not oauth.is_configured():
            log_warning(f"[comments] '{channel_id}' OAuth not configured, skipping")
            all_results[channel_id] = []
            continue

        service = oauth.get_service()
        results = await patrol_channel(
            channel_id, service,
            since_hours=since_hours,
            dry_run=dry_run,
        )
        all_results[channel_id] = results

    return all_results
