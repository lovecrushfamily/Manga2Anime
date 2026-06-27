from __future__ import annotations

import re


_NAMED_STYLE_HINT = re.compile(
    r"\b(ghibli|jujutsu|demon slayer|naruto|one piece|mappa|ufotable|makoto shinkai)\b",
    re.IGNORECASE,
)


def build_style_directive(style_prompt: str) -> str:
    """Keep user intent while steering generation toward broad visual traits."""
    prompt = " ".join(style_prompt.strip().split())
    if _NAMED_STYLE_HINT.search(prompt):
        return (
            f"User style direction: {prompt}. Translate any named studio, franchise, or anime "
            "reference into broad cinematic traits instead of copying it exactly. Keep the output "
            "fanmade, original, black-and-white, manga/anime line art, high-contrast ink, no color."
        )
    return (
        f"User style direction: {prompt}. Keep the output fanmade, original, black-and-white, "
        "manga/anime line art, high-contrast ink, no color."
    )

