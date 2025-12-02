# Telegram LLM Bot

A simple Telegram bot that asks for user input and sends the prompt to Yandex GPT API, returning the response when the "Ask LLM" button is pressed.

## Features

- Asks user for input (question)
- Sends the question directly to Yandex GPT API
- Returns the GPT response in JSON format: {"request": "user question", "response": "LLM answer"}
- Returns the response immediately

## Setup

1. Create a Telegram bot using BotFather (https://t.me/BotFather) and obtain your bot token
2. Get Yandex Cloud credentials:
   - Create a Yandex Cloud account
   - Create an API key
   - Get your folder ID
3. Create the credential files:
   - Add your Telegram bot token to `.secrets/bot-token.env`:
     ```
     TELEGRAM_BOT_TOKEN=your_actual_bot_token_here
     ```
   - Add your Yandex API credentials to `.secrets/yandex-api-key.env`:
     ```
     YANDEX_API_KEY=your_yandex_api_key_here
     YANDEX_FOLDER_ID=your_yandex_folder_id_here
     ```
4. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run the bot:
   ```bash
   python bot.py
   ```

## Usage

1. Start a conversation with your bot
2. Send any text message (question)
3. The bot will immediately return the response from Yandex GPT

## How It Works

The bot uses the python-telegram-bot library to:
1. Listen for incoming messages
2. Send the question directly to Yandex GPT API with instructions to respond in JSON format
3. Return the JSON-formatted GPT response to the user immediately

## Security

- All credentials are stored in separate files in the `.secrets` directory which should NOT be committed to version control
- The `.secrets` directory is excluded from version control
