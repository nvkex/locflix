from app.media_meta import (
    format_bitrate,
    format_duration,
    format_frame_rate,
    format_size,
    quality_from_height,
)


def test_quality_from_height():
    assert quality_from_height(2160) == "2160p"
    assert quality_from_height(1080) == "1080p"
    assert quality_from_height(1078) == "1080p"
    assert quality_from_height(720) == "720p"
    assert quality_from_height(480) == "480p"
    assert quality_from_height(360) == "360p"
    assert quality_from_height(None) is None


def test_format_helpers():
    assert format_duration(6560) == "1h 49m"
    assert format_duration(95) == "1m 35s"
    assert format_size(1613051757) == "1.50 GB"
    assert format_bitrate(1_967_085) == "2.0 Mbps"
    assert format_frame_rate("24000/1001") == "23.976 fps"
    assert format_frame_rate("24/1") == "24 fps"
