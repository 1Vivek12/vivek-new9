"""Tests for Subtitle Generation (SRT / WebVTT Formatting and Monotonic Timestamps)."""


from app.services.media.subtitles import generate_srt, generate_vtt


def test_srt_generation_formatting():
    """Verify SRT format compliance: sequence indices, comma milliseconds, empty line separators."""
    segments = [
        {"start": 1.25, "end": 3.8, "text": "Good evening, welcome to News 9."},
        {"start": 4.0, "end": 6.5, "text": "Top story today: Gorakhpur infrastructure expansion."},
    ]

    srt_output = generate_srt(segments)
    lines = srt_output.strip().split("\n")

    # Entry 1
    assert lines[0] == "1"
    assert lines[1] == "00:00:01,250 --> 00:00:03,800"
    assert lines[2] == "Good evening, welcome to News 9."
    assert lines[3] == ""

    # Entry 2
    assert lines[4] == "2"
    assert lines[5] == "00:00:04,000 --> 00:00:06,500"
    assert lines[6] == "Top story today: Gorakhpur infrastructure expansion."


def test_vtt_generation_formatting():
    """Verify WebVTT format compliance: WEBVTT header, dot milliseconds, cues."""
    segments = [
        {"start": 0.0, "end": 2.123, "text": "Breaking news bulletin."},
        {"start": 2.5, "end": 5.0, "text": "District updates from the field."},
    ]

    vtt_output = generate_vtt(segments)
    assert vtt_output.startswith("WEBVTT\n\n")

    assert "00:00:00.000 --> 00:00:02.123" in vtt_output
    assert "Breaking news bulletin." in vtt_output
    assert "00:00:02.500 --> 00:00:05.000" in vtt_output


def test_empty_segments_returns_empty_or_header():
    """Verify handling when segments list is empty."""
    assert generate_srt([]) == ""
    assert generate_vtt([]).startswith("WEBVTT")


def test_timestamp_monotonicity():
    """Ensure hours, minutes, seconds roll over accurately."""
    # 3661.05 seconds = 1 hour, 1 minute, 1 second, 50 ms
    segments = [
        {"start": 3661.05, "end": 3665.5, "text": "One hour in."},
    ]
    srt = generate_srt(segments)
    assert "01:01:01,050 --> 01:01:05,500" in srt
    vtt = generate_vtt(segments)
    assert "01:01:01.050 --> 01:01:05.500" in vtt
