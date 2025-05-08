# SimpleLearn - AI Learning Assistant

SimpleLearn is a Telegram bot that helps students and researchers by summarizing various types of content using AI. It can process text, documents, videos, and audio files to create concise summaries.

## Features

- 📚 Summarize long lectures into concise points
- 📝 Extract key points from textbooks
- 📃 Break down complex articles
- 🎥 Process video lectures
- 🎤 Transcribe and summarize audio recordings
- 🔗 Summarize web articles and research papers
- 💬 Condense long texts

## Supported Content Types

- 📄 Documents (PDF, DOCX, DOC, TXT)
- 🎥 Videos (MP4)
- 🎤 Audio files (MP3, WAV)
- 🔗 Web links
- 💬 Text messages

## Installation

1. Clone the repository:
```bash
git clone https://github.com/MrSimple07/simplelearn_summarizer.git
cd simplelearn_summarizer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your API keys:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ELEVENLABS_API_KEY=your_elevenlabs_api_key
```

4. Run the bot:
```bash
python main.py
```

## Requirements

- Python 3.8+
- Telegram Bot Token
- ElevenLabs API Key (for audio/video processing)

## Dependencies

- python-telegram-bot
- moviepy
- langchain-google-genai
- docx2txt
- PyPDF2
- beautifulsoup4
- aiohttp
- python-dotenv
- selenium
- scrapy
- webdriver-manager
- psutil

## Usage

1. Start a chat with the bot on Telegram
2. Select your preferred language
3. Send any of the supported content types
4. Receive an AI-generated summary

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 