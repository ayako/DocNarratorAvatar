"""Azure AI Speech Talking Avatar service (batch synthesis REST API)."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from xml.sax.saxutils import escape as xml_escape

import httpx

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 10   # seconds between status checks
_MAX_WAIT = 600       # maximum total wait time in seconds


class AvatarService:
    """Generates avatar video via Azure AI Speech Talking Avatar batch API."""

    def __init__(self) -> None:
        self._speech_key: str = os.environ.get("AZURE_SPEECH_KEY", "")
        self._region: str = os.environ.get("AZURE_SPEECH_REGION", "eastus")
        self._api_version: str = os.environ.get(
            "AZURE_SPEECH_AVATAR_API_VERSION", "2024-08-01"
        )
        self._character: str = os.environ.get("AVATAR_CHARACTER", "Sakura")
        self._style: str = os.environ.get("AVATAR_STYLE", "")
        self._voice: str = os.environ.get(
            "AVATAR_VOICE", "ja-JP-Nanami:DragonHDLatestNeural"
        )

    @property
    def _base_url(self) -> str:
        return (
            f"https://{self._region}.api.cognitive.microsoft.com"
            "/avatar/batchsyntheses"
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def generate_video(self, script: str, output_path: str) -> bool:
        """Synthesise an avatar video and save it to *output_path*.

        Returns ``True`` on success, ``False`` if credentials are not configured
        (allows the app to run in a degraded mode without Azure Speech).
        """
        if not self._speech_key:
            logger.warning(
                "AZURE_SPEECH_KEY が設定されていないため動画生成をスキップします"
            )
            return False

        synthesis_id = await self._create_job(script)
        video_url = await self._poll_until_done(synthesis_id)

        if not video_url:
            raise RuntimeError("アバター合成が完了しましたが動画 URL が取得できませんでした")

        await self._download(video_url, output_path)
        logger.info("動画を保存しました: %s", output_path)
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _create_job(self, script: str) -> str:
        """Submit a batch synthesis job and return its *synthesis_id*."""
        synthesis_id = uuid.uuid4().hex
        url = f"{self._base_url}/{synthesis_id}?api-version={self._api_version}"
        ssml = self._build_ssml(script)

        avatar_config = {
            "talkingAvatarCharacter": self._character,
            "videoFormat": "Mp4",
            "videoCodec": "h264",
            "subtitleType": "soft_embedded",
            "backgroundColor": "#FFFFFFFF",
        }

        if self._style:
            avatar_config["talkingAvatarStyle"] = self._style

        payload = {
            "inputKind": "SSML",
            "inputs": [{"content": ssml}],
            "avatarConfig": avatar_config,
            "properties": {
                "timeToLiveInHours": 24,
            },
        }

        headers = {
            "Ocp-Apim-Subscription-Key": self._speech_key,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.put(url, json=payload, headers=headers)
            resp.raise_for_status()

        logger.info("アバター合成ジョブを作成しました: %s", synthesis_id)
        return synthesis_id

    async def _poll_until_done(self, synthesis_id: str) -> str:
        """Poll the synthesis job until it succeeds or fails.

        Returns the output video URL on success.
        """
        url = f"{self._base_url}/{synthesis_id}?api-version={self._api_version}"
        headers = {"Ocp-Apim-Subscription-Key": self._speech_key}
        elapsed = 0

        while elapsed < _MAX_WAIT:
            await asyncio.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            status: str = data.get("status", "")
            logger.info(
                "アバター合成ステータス: %s (経過 %d 秒)", status, elapsed
            )

            if status == "Succeeded":
                return data.get("outputs", {}).get("result", "")

            if status in ("Failed", "Canceled"):
                error = data.get("properties", {}).get("error", {})
                raise RuntimeError(f"アバター合成が失敗しました: {error}")

        raise TimeoutError(
            f"アバター合成が {_MAX_WAIT} 秒以内に完了しませんでした"
        )

    @staticmethod
    async def _download(url: str, dest: str) -> None:
        """Stream-download *url* to *dest*."""
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with open(dest, "wb") as fh:
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        fh.write(chunk)

    def _build_ssml(self, script: str) -> str:
        """Wrap *script* in SSML markup for the configured voice."""
        lang = self._detect_lang()
        safe_script = xml_escape(script)
        return (
            f'<speak version="1.0" '
            f'xmlns="http://www.w3.org/2001/10/synthesis" '
            f'xml:lang="{lang}">\n'
            f'  <voice name="{self._voice}">\n'
            f"    {safe_script}\n"
            f"  </voice>\n"
            f"</speak>"
        )

    def _detect_lang(self) -> str:
        """Derive an xml:lang value from the configured voice name."""
        parts = self._voice.split("-")
        if len(parts) >= 2:
            return f"{parts[0]}-{parts[1]}"
        return "ja-JP"
