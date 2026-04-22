# Audify.AI

> Advanced AI-powered audio processing and translation platform

Audify.AI is a full-stack application that intelligently processes audio files by separating instrumental stems, transcribing speech, translating content, and synthesizing it back with voices. Perfect for creating multilingual versions of podcasts, music videos, and other audio content.

Our next steps are to make the translated voice sing and be harmonized with the instrumentals.

## Features

- **Audio Stem Separation**: Automatically separate audio into vocals, drums, bass, and other instruments using Demucs
- **Speech Transcription**: Convert audio to text using OpenAI's Whisper with word-level accuracy
- **Content Translation**: Translate transcribed text to multiple languages using Google's Generative AI
- **Text-to-Speech Synthesis**: Generate natural-sounding audio in various languages using Google Cloud Text-to-Speech
- **Full Pipeline**: End-to-end processing from upload to downloadable multilingual versions
- **Real-time Job Tracking**: Monitor processing progress via the intuitive React interface

## Tech Stack

### Backend

- **Framework**: FastAPI (Python)
- **Audio Processing**: Demucs, Librosa, Pydub, Pretty MIDI
- **Speech-to-Text**: Faster Whisper
- **Translation**: Google Generative AI
- **Text-to-Speech**: Google Cloud Text-to-Speech API
- **Deployment**: Docker, Uvicorn

### Frontend

- **Framework**: React 19
- **Build Tool**: React Scripts
- **Testing**: Jest, React Testing Library

## Prerequisites

- **Python 3.8+** (for backend)
- **Node.js 16+** (for frontend)
- **FFmpeg** (required for audio processing)
- **Google Cloud API credentials** (for Gemini and Text-to-Speech)
- **OpenAI or equivalent** for Whisper access

## Local Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Audify.AI
```

### 2. Backend Setup

#### Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

#### Configure Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=<path-to-your-credentials.json>

# API Keys
GEMINI_API_KEY=<your-gemini-api-key>

# Other configurations as needed
```

#### Install FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows (using conda)
conda install ffmpeg
```

#### Run the Backend Server

```bash
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`
API documentation: `http://localhost:8000/docs`

### 3. Frontend Setup

```bash
cd frontend
npm install
npm start
```

The application will open at `http://localhost:3000`

## 📖 How It Works

1. **Upload Audio**: User uploads an audio file through the web interface
2. **Stem Separation**: Audio is separated into individual stems (vocals, drums, bass, etc.)
3. **Transcription**: Speech is transcribed to text with segment and word-level timing
4. **Translation**: Transcribed text is translated to the target language
5. **Synthesis**: Translated text is converted back to speech using natural-sounding voices
6. **Reconstruction**: Original instrumental stems are combined with new translated speech
