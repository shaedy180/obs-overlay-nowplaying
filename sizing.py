"""OBS Browser Source size calculation backed by the settings schema."""

from __future__ import annotations

from typing import Any

from settings_schema import SCHEMA, migrate_settings


METRICS = SCHEMA["layoutMetrics"]


def required_obs_size(raw: Any) -> tuple[int, int]:
    settings = migrate_settings(raw)
    line_height = METRICS["textLineHeight"]
    text_height = settings["titleSize"] * line_height
    if settings["showArtist"]:
        text_height += METRICS["artistGap"] + settings["artistSize"] * line_height
    content_height = max(
        settings["artSize"] if settings["showAlbumArt"] else 0,
        text_height,
        METRICS["equalizerHeight"] if settings["showEqualizer"] else 0,
    )
    width = settings["overlayWidth"] + METRICS["outerMargin"] * 2
    height = (
        content_height
        + METRICS["outerMargin"] * 2
        + METRICS["overlayVerticalPadding"]
        + settings["borderWidth"] * 2
    )
    return round(width), round(height)
