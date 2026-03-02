"""Azure OpenAI service: generate narrator script and captions from document text."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import List, Tuple

from openai import AzureOpenAI

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
あなたはドキュメント要約の専門家です。
与えられたドキュメントの内容を分析し、以下の2つを生成してください。

1. **スクリプト**: アバターが読み上げる要約文章（自然な話し言葉で、2〜3分程度）
2. **キャプション**: 要点を示す短いフレーズのリスト（5〜10項目）

必ず以下の JSON 形式のみで回答してください（余分なテキストは不要です）:
{
  "script": "アバターが話す要約スクリプトのテキスト",
  "captions": [
    "要点1",
    "要点2",
    "要点3"
  ]
}

スクリプトは聴衆に語りかけるような自然な話し言葉で書いてください。
キャプションは簡潔な箇条書き形式にしてください。
ドキュメントの言語に合わせて、同じ言語で回答してください。\
"""

# Maximum document characters to send (avoids exceeding token limits)
_MAX_DOC_CHARS = 8_000


class AIService:
    """Generates narration script and captions using Azure OpenAI."""

    def __init__(self) -> None:
        self._client = AzureOpenAI(
            api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        )
        self._deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    async def generate_script_and_captions(
        self, document_text: str
    ) -> Tuple[str, List[str]]:
        """Return *(script, captions)* generated from *document_text*."""

        if len(document_text) > _MAX_DOC_CHARS:
            document_text = document_text[:_MAX_DOC_CHARS] + "\n\n...(以下省略)"

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.chat.completions.create(
                model=self._deployment,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "以下のドキュメントを要約してください:\n\n"
                            + document_text
                        ),
                    },
                ],
                temperature=0.7,
                response_format={"type": "json_object"},
            ),
        )

        raw = response.choices[0].message.content or "{}"
        result = json.loads(raw)

        script: str = result.get("script", "")
        captions: List[str] = result.get("captions", [])

        if not script:
            raise ValueError("AI がスクリプトを生成できませんでした")

        return script, captions
