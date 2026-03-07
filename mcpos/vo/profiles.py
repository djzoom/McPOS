"""Reusable VO channel profiles."""

from __future__ import annotations

from .models import VOChannelProfile


_PROFILES = {
    "sg_prayer": VOChannelProfile(
        profile_id="sg_prayer",
        channel_name="Sleep in Grace",
        language="en",
        intro_template=(
            "Welcome to Sleep in Grace. Tonight's session is {title}. "
            "Let your breathing slow, let the room grow quiet, and rest in God's peace as the music begins."
        ),
        outro_template=(
            "As this session comes to a close, may peace stay with you through the night. "
            "Rest deeply, stay held in grace, and return whenever you need a quiet place to pray and sleep."
        ),
        full_template=(
            "Welcome to Sleep in Grace. Tonight's session is {title}. {description_excerpt} "
            "Receive this time as a gentle invitation to breathe, pray, and rest. "
            "As the music closes, may peace stay with you through the night."
        ),
        tone_profile="prayerful, reflective, gentle, reassuring",
        pacing_profile="slow breaths, spacious pauses, soft endings",
    ),
    "chl_meditation": VOChannelProfile(
        profile_id="chl_meditation",
        channel_name="CHL",
        language="en",
        intro_template=(
            "Welcome. This meditation session opens with {title}. "
            "Settle your breath, release the day, and let the sound field become a place of healing rest."
        ),
        outro_template=(
            "The meditation is ending now. Carry this stillness with you, return to your breath, and let calm move with you into the next quiet hour."
        ),
        full_template=(
            "Welcome to this meditation session. {title}. {description_excerpt} "
            "Breathe slowly, soften the body, and let this listening space restore you from within."
        ),
        tone_profile="meditative, healing, spacious",
        pacing_profile="slow, airy, minimal words",
    ),
    "generic_dj": VOChannelProfile(
        profile_id="generic_dj",
        channel_name="McPOS",
        language="en",
        intro_template=(
            "Welcome. This mix begins with {title}. Settle in, stay with the mood, and let the set carry you from the first note."
        ),
        outro_template=(
            "This set is ending now. Thanks for listening, stay with the mood, and come back for the next session."
        ),
        full_template=(
            "Welcome to this session. {title}. {description_excerpt} Stay present, stay with the flow, and enjoy the full journey."
        ),
        tone_profile="warm, present, lightly hosted",
        pacing_profile="measured, concise",
    ),
}


def get_channel_profile(profile_id: str) -> VOChannelProfile:
    return _PROFILES.get(profile_id, _PROFILES["generic_dj"])
