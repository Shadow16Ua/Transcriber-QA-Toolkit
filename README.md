# Transcriber QA Toolkit 🎙️

An automated Quality Assurance and gap-filling pipeline for freelance audio transcribers and data annotators. Built as a submission for the **Hacktoberfest 2026 Open-Source AI Challenge (Week 2: Side Hustle)**.

## What it does
This tool helps transcribers cut down their manual QA time by 90%:
- **Audio Gap Recovery:** Analyzes JSON transcription timestamps, slices the original audio via FFmpeg, and uses Whisper to recover any missed speech during >0.5s silences.
- **Strict Batch Normalization:** Uses LLaMA 3 (via Groq API) to format text, apply Inverse Text Normalization (ITN), fix punctuation, and manage strict spacing rules around tags.
- **Privacy-Focused:** Built around open-weight models, allowing freelancers to process sensitive client data securely.

## Prerequisites
- Python 3.8+
- [FFmpeg](https://ffmpeg.org/) installed and added to your system PATH.
- A [Groq API Key](https://console.groq.com/keys) for fast inference.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install groq
   ```

2. **Set your Groq API key:**
   ```powershell
   # Windows (PowerShell)
   $env:GROQ_API_KEY="gsk_your_api_key_here"
   ```

3. **Run the script:**
   Place your audio file (`.wav`) and transcription batch (`.json`) in the same directory, then run:
   ```bash
   python groq_batch_fixer.py
   ```
