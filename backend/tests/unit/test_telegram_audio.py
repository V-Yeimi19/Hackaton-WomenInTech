"""Descarga acotada y transcripción sin conexiones reales ni credenciales."""

from contextlib import contextmanager

import httpx
import pytest

from app.integrations import audio_gateway as audio
from app.integrations import telegram_gateway as telegram


@pytest.fixture(autouse=True)
def audio_config(monkeypatch):
    monkeypatch.setattr(audio.settings, "enable_llm", True)
    monkeypatch.setattr(audio.settings, "enable_telegram_audio", True)
    monkeypatch.setattr(audio.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(audio.settings, "groq_model", "test-chat-model")
    monkeypatch.setattr(audio.settings, "telegram_bot_token", "test-token")


def response(data, status=200):
    return httpx.Response(status, json=data, request=httpx.Request("POST", "https://test.invalid"))


def test_transcription_uploads_to_groq_and_keeps_spanish(monkeypatch):
    seen = []

    def post(url, **kwargs):
        seen.append((url, kwargs))
        return response({"text": "  ¿Cómo van mis ventas?  ", "duration": 5.2})

    monkeypatch.setattr(audio.httpx, "post", post)
    assert audio.transcribe(b"test-ogg", "audio.ogg") == "¿Cómo van mis ventas?"
    url, request = seen[0]
    assert url.endswith("/audio/transcriptions")
    assert request["files"]["file"] == ("audio.ogg", b"test-ogg", "application/octet-stream")
    assert request["data"]["language"] == "es"
    assert request["data"]["response_format"] == "verbose_json"
    assert request["data"]["model"] == audio.settings.groq_transcription_model


@pytest.mark.parametrize(
    "data",
    [
        {"text": "   "},
        {"text": None},
        {"text": "x" * 4001},
        {"text": "Hola", "duration": 181},
    ],
)
def test_unusable_transcripts_are_rejected(monkeypatch, data):
    monkeypatch.setattr(audio.httpx, "post", lambda *a, **k: response(data))
    with pytest.raises(audio.AudioError):
        audio.transcribe(b"audio", "audio.ogg")


def test_transcription_failure_never_exposes_provider_error(monkeypatch, caplog):
    def post(*args, **kwargs):
        raise httpx.ReadTimeout("private-token-and-audio-content")

    monkeypatch.setattr(audio.httpx, "post", post)
    with pytest.raises(audio.AudioError, match="No pude transcribir") as error:
        audio.transcribe(b"audio", "audio.ogg")
    assert "private-token" not in str(error.value) + caplog.text


def test_disabled_audio_does_not_contact_groq(monkeypatch):
    monkeypatch.setattr(audio.settings, "enable_telegram_audio", False)
    monkeypatch.setattr(audio.httpx, "post", lambda *a, **k: pytest.fail("Unexpected network call"))
    with pytest.raises(audio.AudioError, match="Escríbeme"):
        audio.transcribe(b"audio", "audio.ogg")


def mock_download(monkeypatch, *, path="voice/file.oga", size=5, body=b"audio", headers=None):
    seen = []
    monkeypatch.setattr(
        telegram.httpx,
        "get",
        lambda *a, **k: response(
            {
                "ok": True,
                "result": {"file_path": path, "file_size": size},
            }
        ),
    )

    @contextmanager
    def stream(method, url, **kwargs):
        seen.append((url, kwargs))
        with httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    stream=httpx.ByteStream(body),
                    headers=headers or {},
                )
            )
        ) as client:
            with client.stream(method, url) as result:
                yield result

    monkeypatch.setattr(telegram.httpx, "stream", stream)
    return seen


def test_telegram_voice_is_downloaded_as_ogg(monkeypatch):
    seen = mock_download(monkeypatch)
    assert telegram.download_audio("file-id") == (b"audio", "audio.ogg")
    assert seen[0][0].endswith("/voice/file.oga")
    assert seen[0][1]["follow_redirects"] is False


@pytest.mark.parametrize(
    "path", ["../file.ogg", "https://other.invalid/file.ogg", "/voice/file.ogg", "file.exe"]
)
def test_invalid_file_paths_and_formats_are_rejected_before_download(monkeypatch, path):
    seen = mock_download(monkeypatch, path=path)
    with pytest.raises(audio.AudioError):
        telegram.download_audio("file-id")
    assert not seen


def test_get_file_size_is_checked_before_download(monkeypatch):
    seen = mock_download(monkeypatch, size=telegram.settings.telegram_audio_max_bytes + 1)
    with pytest.raises(audio.AudioError, match="pesado"):
        telegram.download_audio("file-id")
    assert not seen


@pytest.mark.parametrize("headers", [{}, {"content-length": "100"}])
def test_stream_limit_is_enforced_even_if_telegram_metadata_understates_size(monkeypatch, headers):
    monkeypatch.setattr(telegram.settings, "telegram_audio_max_bytes", 4)
    mock_download(monkeypatch, size=1, body=b"12345", headers=headers)
    with pytest.raises(audio.AudioError, match="pesado"):
        telegram.download_audio("file-id")


def test_empty_download_is_rejected(monkeypatch):
    mock_download(monkeypatch, size=0, body=b"")
    with pytest.raises(audio.AudioError, match="descargar"):
        telegram.download_audio("file-id")
