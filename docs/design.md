# DocNarratorAvatar – 開発設計書

## 1. 概要

ドキュメント（PowerPoint / PDF / Word / テキスト）を読み込み、
Azure OpenAI でナレータースクリプトとキャプションを生成し、
Azure AI Speech Talking Avatar がそのスクリプトを読み上げる動画を自動生成するWebアプリ。

---

## 2. 要件

| # | 要件 |
|---|------|
| R1 | PowerPoint ファイルは PDF または JPG に変換する |
| R2 | ドキュメントから **ナレータースクリプト**（要約）を Microsoft Foundry Model (Azure OpenAI) で生成する |
| R3 | ドキュメントから **キャプション**（要点箇条書き）を Azure OpenAI で生成する |
| R4 | スクリプトから Azure AI Speech Talking Avatar で**アバター動画**を生成する |
| R5 | フロントエンドはシンプルな HTML/CSS/JS で構成する |
| R6 | バックエンドは Python の REST API として稼働する |
| R7 | 処理完了後に「再生開始」ボタンを表示し、クリックで動画再生とキャプション表示を開始する |

---

## 3. システムアーキテクチャ

```
[ ブラウザ (HTML/CSS/JS) ]
        ↕  REST API (HTTP)
[ FastAPI バックエンド (Python) ]
        ↕
  ┌─────────────────────────────────┐
  │  DocumentProcessor              │  python-pptx / pdfplumber / python-docx
  │  AIService                      │  Azure OpenAI (gpt-4.1)
  │  AvatarService                  │  Azure AI Speech Talking Avatar
  └─────────────────────────────────┘
```

### 3.1 処理フロー

```
1. ユーザーがファイルをアップロード
2. バックエンドがジョブIDを返す
3. バックエンドがバックグラウンドで処理を開始
   a. ドキュメントテキスト抽出（PPTXの場合はPDF/JPGにも変換）
   b. Azure OpenAI → スクリプト + キャプション生成
   c. Azure AI Speech → アバター動画生成（バッチ合成 API）
4. フロントエンドが /api/status/{job_id} をポーリング
5. 完了後「再生開始」ボタンを表示
6. ユーザーが再生ボタンをクリック → 動画再生 + キャプション同期表示
```

---

## 4. REST API 仕様

| メソッド | パス | 説明 |
|----------|------|------|
| `POST` | `/api/process` | ファイルアップロード・処理開始。`job_id` を返す |
| `GET`  | `/api/status/{job_id}` | 処理状態・進捗を返す |
| `GET`  | `/api/result/{job_id}` | 完了後の動画URL・キャプション・スクリプトを返す |
| `GET`  | `/api/video/{job_id}` | 生成した MP4 動画ファイルを返す |
| `GET`  | `/` | フロントエンド HTML を返す |

### 4.1 POST /api/process

**Request**  
`multipart/form-data` — `file`: アップロードするドキュメント

**Response**
```json
{ "job_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" }
```

### 4.2 GET /api/status/{job_id}

**Response**
```json
{
  "status": "processing | completed | failed",
  "progress": 60,
  "step": "アバター動画を生成中...",
  "error": null
}
```

### 4.3 GET /api/result/{job_id}

**Response**
```json
{
  "video_url": "/api/video/{job_id}",
  "captions": ["要点1", "要点2", "要点3"],
  "script": "アバターが話す要約スクリプトのテキスト",
  "has_video": true
}
```

---

## 5. コンポーネント設計

### 5.1 DocumentProcessor (`app/services/document.py`)

| 形式 | 処理方法 |
|------|----------|
| `.pptx` / `.ppt` | python-pptx でテキスト抽出。LibreOffice が利用可能な場合は PNG/PDF にも変換 |
| `.pdf` | pdfplumber でテキスト抽出 |
| `.docx` / `.doc` | python-docx でテキスト抽出 |
| `.txt` | そのまま読み込み |

### 5.2 AIService (`app/services/ai.py`)

- Azure OpenAI (`openai` ライブラリ) を使用
- システムプロンプトで JSON レスポンス形式を指定
- 出力フィールド: `script`（スクリプト）、`captions`（キャプション配列）
- 長文ドキュメントはトークン制限のため先頭 8,000 文字に切り詰め

### 5.3 AvatarService (`app/services/avatar.py`)

- Azure AI Speech Talking Avatar バッチ合成 REST API を使用
- エンドポイント: `https://{region}.customvoice.api.speech.microsoft.com/api/texttospeech/3.1-preview1/batchsynthesis/talkingavatar`
- スクリプトを SSML に変換してジョブ投入
- 完了まで 10 秒間隔でポーリング（最大 600 秒）
- 完了後に動画 URL から MP4 をダウンロード

### 5.4 フロントエンド (`app/static/`)

**状態遷移**

```
UPLOAD → PROCESSING → READY → PLAYING
```

- `UPLOAD`: ドラッグ&ドロップまたはクリックでファイル選択
- `PROCESSING`: ステップ別プログレスバーをポーリング表示
- `READY`: 「再生開始」ボタン表示
- `PLAYING`: 動画再生 + キャプションオーバーレイ + 要点リスト

**キャプション同期**  
`video.timeupdate` イベントで現在再生位置を監視し、
`(currentTime / duration * captions.length)` で表示するキャプションを決定。

---

## 6. 環境変数

| 変数名 | 説明 | 必須 |
|--------|------|------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI のエンドポイント URL | ✅ |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI の API キー | ✅ |
| `AZURE_OPENAI_API_VERSION` | API バージョン（例: `2024-02-01`） | — |
| `AZURE_OPENAI_DEPLOYMENT` | デプロイメント名（例: `gpt-4.1`） | — |
| `AZURE_SPEECH_KEY` | Azure AI Speech のサブスクリプションキー | ✅ |
| `AZURE_SPEECH_REGION` | Azure AI Speech のリージョン（例: `eastus`） | — |
| `AVATAR_CHARACTER` | Photo Avatar モデル名（例: `Sakura`） | — |
| `AVATAR_STYLE` | アバタースタイル（省略可。Photo Avatar では空文字推奨） | — |
| `AVATAR_VOICE` | 音声名（例: `ja-JP-Nanami:DragonHDLatestNeural`） | — |

---

## 7. ディレクトリ構成

```
DocNarratorAvatar/
├── app/
│   ├── main.py                 # FastAPI エントリーポイント
│   ├── services/
│   │   ├── __init__.py
│   │   ├── document.py         # ドキュメント処理
│   │   ├── ai.py               # Azure OpenAI 連携
│   │   └── avatar.py           # Azure AI Speech Avatar 連携
│   └── static/
│       ├── index.html          # フロントエンド HTML
│       ├── style.css           # スタイルシート
│       └── app.js              # フロントエンド JavaScript
├── docs/
│   └── design.md               # 本設計書
├── uploads/                    # アップロードファイル一時保存（.gitignore）
├── outputs/                    # 生成動画一時保存（.gitignore）
├── requirements.txt
├── .env.example
└── README.md
```

---

## 8. 技術スタック

| 区分 | 技術 |
|------|------|
| バックエンド言語 | Python 3.11+ |
| Web フレームワーク | FastAPI |
| ASGI サーバー | Uvicorn |
| ドキュメント処理 | python-pptx, pdfplumber, python-docx |
| AI サービス | Azure OpenAI (gpt-4.1) |
| Avatar サービス | Azure AI Speech Talking Avatar |
| HTTP クライアント | httpx (async) |
| フロントエンド | Vanilla HTML / CSS / JavaScript |

---

## 9. 非機能要件

- バックグラウンド処理でアップロード直後に即レスポンスを返す
- アバター動画生成失敗時もスクリプト・キャプションは表示する
- Azure Speech 未設定時はスクリプト・キャプションのみ表示するフォールバック動作
