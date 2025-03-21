# Telegram Meme Search Bot

A Telegram bot that provides full-text search for images in a specific channel or group based on their descriptions.

## Overview

This bot monitors a specified Telegram channel and group for posts containing images. 

For the channel, when an image is posted, the bot waits for a description to be added.

For the group, when a specific description bot replies to a message containing an image, the bot saves the image from the original message and the description from the bot's reply to a PostgreSQL database.

Users can then search for images by sending text queries to the bot, which performs a full-text search to find the most relevant images from both the channel and the group.

## Features

- Monitors a specific Telegram channel for new image posts
- Monitors a specific Telegram group for messages from a description bot
- Saves images and their descriptions to a PostgreSQL database
- Provides full-text search functionality using PostgreSQL's trigram similarity
- Returns the most relevant images based on the search query
- Allows users to view more search results
- Shows the source (channel or group) of each image in search results

## Requirements

- Python 3.8+
- PostgreSQL 17+
- Docker and Docker Compose

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/meme-search-bot.git
   cd meme-search-bot
   ```

2. Configure the bot:
   - Edit `config.json` to set your Telegram bot token, target channel, target group, and description bot username

3. Build and run the Docker containers:
   ```
   docker-compose up -d
   ```

4. The bot should now be running and monitoring the specified channel and group.

## Local Development

If you want to develop the bot locally without Docker:

1. Create a virtual environment:
   ```
   ./setup.sh
   ```

2. Activate the virtual environment:
   ```
   source venv/bin/activate
   ```

3. Make sure PostgreSQL is running and accessible.

4. Run the bot:
   ```
   python bot.py
   ```

## Database Schema

The bot uses a PostgreSQL database with the following schema:

- `meme_images` table:
  - `id`: Serial primary key
  - `message_id`: Telegram message ID
  - `channel_id`: Telegram channel or group ID (used for both)
  - `file_id`: Telegram file ID for the image
  - `description`: Text description of the image
  - `created_at`: Timestamp when the record was created

## How It Works

1. The bot uses python-telegram-bot to monitor both the target channel and group:
   - For the channel: When a new image is posted, the bot checks for a description (placeholder implementation).
   - For the group: When the description bot replies to a message containing an image, the bot extracts the image from the original message and the description from the bot's reply.
2. The bot saves the image and description to the database.
3. When a user sends a text query to the bot, it performs a full-text search using PostgreSQL's trigram similarity.
4. The bot returns the most relevant image(s) based on the search query, indicating whether each image is from the channel or the group.

## License

MIT
