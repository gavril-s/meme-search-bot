# Meme Search Bot

A Telegram bot that monitors a target group for memes, saves them with their descriptions, and provides full-text search functionality.

## Features

- Monitors a target Telegram group for images
- Saves image-description pairs to a PostgreSQL database
- Provides full-text search capabilities to find memes based on text queries
- Optimized for search performance with PostgreSQL's full-text search features

## Requirements

- Python 3.8+
- Docker and Docker Compose (for running PostgreSQL)
- Telegram Bot Token (from BotFather)

## Setup

### 1. Configure the bot

Edit the `config.json` file and fill in your details:

```json
{
  "bot_token": "YOUR_BOT_TOKEN",
  "target_group_username": "YOUR_TARGET_GROUP_USERNAME",
  "bot_username": "YOUR_BOT_USERNAME",
  "database": {
    "host": "db",
    "port": 5432,
    "user": "postgres",
    "password": "postgres",
    "database": "meme_search"
  }
}
```

### 2. Set up the Python environment

Run the setup script to create a virtual environment and install dependencies:

```bash
chmod +x setup.sh
./setup.sh
```

### 3. Run the bot

#### Using Docker Compose (recommended)

This will start both the PostgreSQL database and the bot:

```bash
docker-compose up -d
```

#### Running locally (development)

First, make sure you have PostgreSQL running (you can use Docker for this):

```bash
docker-compose up -d db
```

Then, activate the virtual environment and run the bot:

```bash
source venv/bin/activate
python bot.py
```

## How It Works

1. The bot monitors the specified Telegram group for images
2. When an image is posted, it's stored in memory
3. When the bot (with the username specified in config) replies to an image with a description, the image-description pair is saved to the database
4. Users can send text queries to the bot in private messages to search for memes
5. The bot uses PostgreSQL's full-text search to find the best matching memes and returns them

## Database Structure

The database uses PostgreSQL's full-text search capabilities:

- `pg_trgm` extension for similarity search
- TSVECTOR column for efficient text search
- GIN indexes for fast lookups
- Custom search function that combines exact matching and similarity ranking

## Troubleshooting

- Make sure your bot has access to the target group
- Ensure the bot has the necessary permissions to read messages in the group
- Check the logs for any errors: `docker-compose logs -f app`
