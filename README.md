# DocNarratorAvatar

ドキュメントを読み込んで、アバターが要約を話す Web アプリです。

| 機能 | 詳細 |
|------|------|
| 📄 ドキュメント対応 | PowerPoint (.pptx), PDF, Word (.docx), テキスト (.txt) |
| 🔄 PPT 変換 | LibreOffice が利用可能な場合は PDF/PNG に変換 |
| 🤖 AI 要約 | Azure OpenAI (gpt-4.1) でナレータースクリプトと要点キャプションを生成 |
| 🎬 アバター動画 | Azure AI Speech Talking Avatar でアバターが読み上げる MP4 を生成 |
| 🌐 フロントエンド | シンプルな HTML/CSS/JavaScript |
| ⚙️ バックエンド | Python (FastAPI) REST API |

設計ドキュメント → [`docs/design.md`](docs/design.md)

---

## セットアップ

### 必要条件

- Python 3.11 以上
- Azure OpenAI リソース（gpt-4.1 デプロイ）
- Azure AI Speech リソース（Talking Avatar 対応リージョン）

### インストール

```bash
# リポジトリのルートで実行
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 環境変数の設定

```bash
cp .env.example .env
# .env を編集して各値を設定してください
```

| 変数名 | 説明 | 必須 |
|--------|------|------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI のエンドポイント URL | ✅ |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI の API キー | ✅ |
| `AZURE_OPENAI_API_VERSION` | API バージョン（デフォルト: `2024-02-01`） | — |
| `AZURE_OPENAI_DEPLOYMENT` | デプロイメント名（デフォルト: `gpt-4.1`） | — |
| `AZURE_SPEECH_KEY` | Azure AI Speech のサブスクリプションキー | ✅ |
| `AZURE_SPEECH_REGION` | リージョン（デフォルト: `eastus`） | — |
| `AVATAR_CHARACTER` | Photo Avatar モデル名（デフォルト: `Sakura`） | — |
| `AVATAR_STYLE` | アバタースタイル（省略可。Photo Avatar では空文字推奨） | — |
| `AVATAR_VOICE` | 音声名（デフォルト: `ja-JP-Nanami:DragonHDLatestNeural`） | — |

### 起動

```bash
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

ブラウザで <http://localhost:8000> を開いてください。

---

## 使い方

1. ブラウザでアプリを開く
2. ドキュメント（PPTX / PDF / DOCX / TXT）をドラッグ&ドロップまたはクリックして選択
3. **処理を開始する** ボタンをクリック
4. 処理完了後に **▶ 再生を開始する** ボタンが表示されます
5. ボタンをクリックするとアバター動画の再生とキャプション表示が始まります

> **Note**  `AZURE_SPEECH_KEY` が未設定の場合は動画生成をスキップし、
> 生成されたスクリプトと要点キャプションをテキストで表示します。

---

## ディレクトリ構成

```
DocNarratorAvatar/
├── app/
│   ├── main.py                 # FastAPI エントリーポイント
│   ├── services/
│   │   ├── document.py         # ドキュメント処理
│   │   ├── ai.py               # Azure OpenAI 連携
│   │   └── avatar.py           # Azure AI Speech Avatar 連携
│   └── static/
│       ├── index.html          # フロントエンド HTML
│       ├── style.css           # スタイルシート
│       └── app.js              # フロントエンド JavaScript
├── docs/
│   └── design.md               # 設計ドキュメント
├── requirements.txt
├── .env.example
└── README.md
```
