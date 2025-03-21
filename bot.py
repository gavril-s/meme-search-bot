import json
import logging
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=config['database']['host'],
        port=config['database']['port'],
        user=config['database']['user'],
        password=config['database']['password'],
        database=config['database']['database']
    )

# In-memory storage for pictures
# Structure: {message_id: {'file_id': file_id, 'chat_id': chat_id}}
picture_memory = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Hi! I am a meme search bot. Send me a text query and I will find the best matching meme for you.'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        'Send me a text query and I will find the best matching meme for you.'
    )

async def monitor_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Monitor the target group for pictures and descriptions."""
    # Check if the message is from the target group
    if update.effective_chat.username != config['target_group_username']:
        return
    
    # Check if the message contains a photo
    if update.message.photo:
        # Store the photo in memory
        file_id = update.message.photo[-1].file_id  # Get the largest photo
        picture_memory[update.message.message_id] = {
            'file_id': file_id,
            'chat_id': update.effective_chat.id
        }
        logger.info(f"Stored photo with message_id {update.message.message_id}")
    
    # Check if the message is a reply from the bot with a description
    elif (update.message.from_user.username == config['bot_username'] and 
          update.message.reply_to_message and 
          update.message.reply_to_message.message_id in picture_memory):
        
        # Get the picture from memory
        picture_data = picture_memory[update.message.reply_to_message.message_id]
        file_id = picture_data['file_id']
        description = update.message.text
        
        # Save to database
        try:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO memes (file_id, description) VALUES (%s, %s) ON CONFLICT (file_id) DO UPDATE SET description = %s",
                    (file_id, description, description)
                )
            conn.commit()
            conn.close()
            logger.info(f"Saved meme with description: {description[:50]}...")
            
            # Remove from memory to free up space
            del picture_memory[update.message.reply_to_message.message_id]
        except Exception as e:
            logger.error(f"Error saving to database: {e}")

async def search_meme(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search for memes based on user query."""
    query = update.message.text
    
    # Clean the query for full-text search
    # Replace special characters with spaces and convert to lowercase
    clean_query = re.sub(r'[^\w\s]', ' ', query.lower())
    # Convert spaces to '&' for tsquery
    ts_query = ' & '.join(clean_query.split())
    
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM search_memes(%s)", (ts_query,))
            results = cur.fetchall()
        conn.close()
        
        if results:
            # Send the top result
            best_match = results[0]
            await update.message.reply_photo(
                photo=best_match['file_id'],
                caption=f"Match: {best_match['description'][:200]}...",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Show more results", callback_data=f"more_{query}")]
                ]) if len(results) > 1 else None
            )
        else:
            await update.message.reply_text("No matching memes found.")
    except Exception as e:
        logger.error(f"Error searching database: {e}")
        await update.message.reply_text("An error occurred while searching. Please try again later.")

def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(config['bot_token']).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Monitor the target group for pictures and descriptions
    application.add_handler(MessageHandler(filters.ALL, monitor_group))
    
    # Handle direct messages to the bot for search
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, 
        search_meme
    ))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()

if __name__ == '__main__':
    main()
