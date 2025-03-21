import json
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, CallbackContext,
    Filters, CallbackQueryHandler
)

from db import Database

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

TELEGRAM_TOKEN = config['telegram']['api_token']
TARGET_CHANNEL = config['telegram']['target_channel']
TARGET_GROUP = config['telegram']['target_group']
DESCRIPTION_BOT_USERNAME = config['telegram']['description_bot_username']

# Initialize database
db = Database()

# In-memory store for pending images (waiting for descriptions)
# Structure: {message_id: {'channel_id': channel_id, 'file_id': file_id, 'timestamp': timestamp}}
pending_images = {}

# Helper function to determine the source (channel or group) based on the channel_id
def get_source_by_id(channel_id: int) -> str:
    """Determine if the channel_id belongs to the target channel or group."""
    if channel_id == TARGET_CHANNEL:
        return "channel"
    elif channel_id == TARGET_GROUP:
        return "group"
    return "unknown"

def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    update.message.reply_text(
        'Hi! I can help you search for images from both the channel and the group. '
        'Just send me a text query, and I\'ll find the most relevant images.'
    )

def search_images(update: Update, context: CallbackContext) -> None:
    """Search for images based on the user's query."""
    query = update.message.text
    
    # Search for images in the database
    results = db.search_images_sync(query)
    
    if not results:
        update.message.reply_text(
            'No images found matching your query. Try a different search term.'
        )
        return
    
    # Get the best match
    best_match = results[0]
    
    # Create a keyboard with a button to view more results
    keyboard = [
        [InlineKeyboardButton("View more results", callback_data=f"more_{query}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the best match image
    update.message.reply_text(
        f"Best match (similarity: {best_match['similarity']:.2f}):\n"
        f"{best_match['description']}",
        reply_markup=reply_markup
    )
    
    # Send the image using file_id
    source = get_source_by_id(best_match['channel_id'])
    try:
        # Send the actual photo using file_id
        context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=best_match['file_id'],
            caption=f"From {source}"
        )
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        # Fallback to text message if sending photo fails
        update.message.reply_text(
            f"Image from message: {best_match['message_id']} in {source}"
        )

def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    query.answer()
    
    # Parse the callback data
    data = query.data
    
    if data.startswith("more_"):
        # Extract the search query
        search_query = data[5:]
        
        # Search for images in the database
        results = db.search_images_sync(search_query)
        
        if len(results) <= 1:
            query.edit_message_text(text="No more results available.")
            return
        
        # Create a message with all results
        message = "All matching images:\n\n"
        for i, result in enumerate(results):
            source = get_source_by_id(result['channel_id'])
            message += f"{i+1}. Similarity: {result['similarity']:.2f}\n"
            message += f"Description: {result['description']}\n"
            message += f"Message: {result['message_id']} in {source}\n\n"
        
        # Update the message
        query.edit_message_text(text=message)

def handle_channel_post(update: Update, context: CallbackContext) -> None:
    """Handle new posts in the target channel."""
    # Add detailed logging for debugging
    logger.info(f"Received channel post in chat: {update.channel_post.chat.id} ({update.channel_post.chat.username})")
    
    # Check if this is from our target channel - be more lenient in the check
    target_channel_username = TARGET_CHANNEL.lstrip('@').lower()
    chat_username = update.channel_post.chat.username.lower() if update.channel_post.chat.username else ""
    chat_title = update.channel_post.chat.title.lower() if hasattr(update.channel_post.chat, 'title') and update.channel_post.chat.title else ""
    
    # Check if the username or title matches the target channel
    if target_channel_username not in chat_username and target_channel_username not in chat_title:
        logger.info(f"Channel post not from target channel. Expected: {target_channel_username}, Got username: {chat_username}, title: {chat_title}")
        return
    
    # Log that we've confirmed this is from the target channel
    logger.info(f"Channel post is from target channel: {update.channel_post.chat.username}")
    
    # Check if the message has a photo
    if not update.channel_post.photo:
        logger.info(f"Channel post has no photo: {update.channel_post.message_id}")
        return
    
    # Log that we've confirmed the channel post has a photo
    logger.info(f"Channel post has a photo")
    
    message_id = update.channel_post.message_id
    channel_id = update.channel_post.chat_id
    
    # Get the largest photo (best quality)
    photo = update.channel_post.photo[-1]
    file_id = photo.file_id
    
    logger.info(f"New image posted in channel: {message_id}")
    
    # Store the image in the pending_images dictionary
    pending_images[message_id] = {
        'channel_id': channel_id,
        'file_id': file_id,
        'timestamp': time.time()
    }
    
    # Log the current pending images for debugging
    logger.info(f"Current pending images: {len(pending_images)}")
    
    # Schedule a cleanup job to remove old pending images
    context.job_queue.run_once(
        cleanup_pending_images,
        3600,  # 1 hour
        context=None
    )

def handle_group_message(update: Update, context: CallbackContext) -> None:
    """Handle messages in the target group."""
    # Add detailed logging for debugging
    logger.info(f"Received message in chat: {update.message.chat.id} ({update.message.chat.username if hasattr(update.message.chat, 'username') else 'no username'})")
    
    # Dump the entire message for debugging
    logger.info(f"Message details: {update.message.to_dict()}")
    
    # Skip private chats (direct messages to the bot)
    if update.message.chat.type == 'private':
        logger.info("Skipping private chat message")
        return
    
    # Check if this is from our target group - be extremely lenient in the check
    target_group_username = TARGET_GROUP.lstrip('@').lower()
    chat_username = update.message.chat.username.lower() if hasattr(update.message.chat, 'username') and update.message.chat.username else ""
    chat_title = update.message.chat.title.lower() if hasattr(update.message.chat, 'title') and update.message.chat.title else ""
    chat_id = str(update.message.chat.id).lower()
    
    # Check if the username, title, or ID matches or contains the target group
    if (target_group_username not in chat_username and 
        target_group_username not in chat_title and 
        target_group_username not in chat_id and
        'meme' not in chat_username and
        'meme' not in chat_title):
        logger.info(f"Message not from target group. Expected: {target_group_username}, Got username: {chat_username}, title: {chat_title}, id: {chat_id}")
        return
    
    # Log that we've confirmed this is from the target group
    logger.info(f"Message is from target group: {update.message.chat.username if hasattr(update.message.chat, 'username') else 'no username'}")
    
    # Special handling for messages that are replies to forwarded channel posts
    # These might be descriptions from the description bot
    if (update.message.reply_to_message and 
        hasattr(update.message.reply_to_message, 'forward_from_chat') and 
        update.message.reply_to_message.forward_from_chat):
        
        # Check if the replied-to message is a forward from our target channel
        target_channel_username = TARGET_CHANNEL.lstrip('@').lower()
        forward_chat_username = update.message.reply_to_message.forward_from_chat.username.lower() if hasattr(update.message.reply_to_message.forward_from_chat, 'username') and update.message.reply_to_message.forward_from_chat.username else ""
        
        if target_channel_username in forward_chat_username or 'meme' in forward_chat_username:
            logger.info(f"Message is a reply to a forward from our target channel: {forward_chat_username}")
            
            # This is likely a description from the description bot
            # Get the description from the message
            description = update.message.text
            logger.info(f"Description text from reply to forward: {description[:50]}...")
            
            # Skip saving if description is "Error happened"
            if description == "Error happened":
                logger.info(f"Skipping save for message with error description")
                return
            
            # Get the original message details from the forward
            original_message = update.message.reply_to_message
            message_id = original_message.forward_from_message_id if hasattr(original_message, 'forward_from_message_id') else original_message.message_id
            channel_id = original_message.forward_from_chat.id if hasattr(original_message, 'forward_from_chat') else original_message.chat.id
            
            # Get the largest photo (best quality)
            if original_message.photo:
                photo = original_message.photo[-1]
                file_id = photo.file_id
                
                logger.info(f"Processing description reply to forwarded channel post. Original message ID: {message_id}")
                
                # Save the image and description to the database
                db.save_image_sync(
                    message_id=message_id,
                    channel_id=channel_id,
                    file_id=file_id,
                    description=description
                )
                logger.info(f"Saved image from forwarded message {message_id} with description: {description[:50]}...")
                
                # Check if this file_id matches any pending images
                for pending_id, pending_data in list(pending_images.items()):
                    if pending_data['file_id'] == file_id:
                        logger.info(f"Found matching pending image for file_id: {file_id}")
                        
                        # Save the image and description to the database
                        db.save_image_sync(
                            message_id=pending_id,
                            channel_id=pending_data['channel_id'],
                            file_id=file_id,
                            description=description
                        )
                        logger.info(f"Saved description for pending image {pending_id}: {description[:50]}...")
                        
                        # Remove the image from the pending_images dictionary
                        del pending_images[pending_id]
                        break
                
                return
    
    # Check if the message is from the description bot - be extremely lenient in the check
    description_bot_username = DESCRIPTION_BOT_USERNAME.lstrip('@').lower()
    
    if update.message.from_user:
        # Allow messages from Telegram's official user (777000) for system forwards
        if update.message.from_user.id == 777000:
            return
        
        from_username = update.message.from_user.username.lower() if update.message.from_user.username else ""
        from_first_name = update.message.from_user.first_name.lower() if update.message.from_user.first_name else ""
        logger.info(f"Message from user: {from_username} ({from_first_name})")
        
        # Check if the username or first name contains the description bot username or 'gemini'
        if (description_bot_username not in from_username and
            'gemini' not in from_username and
            description_bot_username not in from_first_name and
            'gemini' not in from_first_name):
            logger.info(f"Message not from description bot. Expected: {description_bot_username}, Got username: {from_username}, first_name: {from_first_name}")
            return
    else:
        logger.info("Message has no from_user")
        return
    
    # Log that we've confirmed this is from the description bot
    logger.info(f"Message is from description bot: {update.message.from_user.username}")
    
    # Get the description from the bot's message
    description = update.message.text
    logger.info(f"Description text: {description[:50]}...")
    
    # Skip saving if description is "Error happened"
    if description == "Error happened":
        logger.info(f"Skipping save for message with error description")
        return
    
    # Check if this is a reply to another message
    if not update.message.reply_to_message:
        logger.info(f"Description bot message is not a reply: {update.message.message_id}")
        return
    
    # Log that we've confirmed this is a reply
    logger.info(f"Message is a reply to: {update.message.reply_to_message.message_id}")
    
    # Check if the replied-to message has a photo
    if not update.message.reply_to_message.photo:
        logger.info(f"Replied-to message has no photo: {update.message.reply_to_message.message_id}")
        return
    
    # Log that we've confirmed the replied-to message has a photo
    logger.info(f"Replied-to message has a photo")
    
    # Get the message details
    original_message = update.message.reply_to_message
    message_id = original_message.message_id
    group_id = original_message.chat_id
    
    # Get the largest photo (best quality)
    photo = original_message.photo[-1]
    file_id = photo.file_id
    
    logger.info(f"Processing description bot reply in group. Original message ID: {message_id}")
    
    # Save the image and description to the database
    db.save_image_sync(
        message_id=message_id,
        channel_id=group_id,  # Using channel_id field for group_id as well
        file_id=file_id,
        description=description
    )
    logger.info(f"Saved image from message {message_id} with description: {description[:50]}...")
    
    # Check if this file_id matches any pending images
    # This is a simple approach - in a production environment, you might want to use
    # a more sophisticated matching algorithm
    for pending_id, pending_data in list(pending_images.items()):
        if pending_data['file_id'] == file_id:
            logger.info(f"Found matching pending image for file_id: {file_id}")
            
            # Save the image and description to the database
            db.save_image_sync(
                message_id=pending_id,
                channel_id=pending_data['channel_id'],
                file_id=file_id,
                description=description
            )
            logger.info(f"Saved description for pending image {pending_id}: {description[:50]}...")
            
            # Remove the image from the pending_images dictionary
            del pending_images[pending_id]
            break

def cleanup_pending_images(context: CallbackContext) -> None:
    """Clean up old pending images."""
    current_time = time.time()
    old_images = []
    
    # Find images older than 24 hours
    for message_id, data in list(pending_images.items()):
        if current_time - data['timestamp'] > 86400:  # 24 hours in seconds
            old_images.append(message_id)
    
    # Remove old images
    for message_id in old_images:
        del pending_images[message_id]
    
    logger.info(f"Cleaned up {len(old_images)} old pending images. Remaining: {len(pending_images)}")

def main() -> None:
    """Start the bot."""
    # Wait for PostgreSQL to start up
    logger.info("Waiting for PostgreSQL to start up...")
    time.sleep(10)  # Give PostgreSQL time to initialize
    
    # Connect to the database
    logger.info("Connecting to database...")
    
    # Try to connect to the database with retries
    max_retries = 10
    retry_delay = 5  # seconds
    
    for attempt in range(max_retries):
        try:
            # Run the database connection
            db.connect_sync()
            logger.info("Successfully connected to the database")
            break
        except Exception as e:
            logger.error(f"Database connection attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("Failed to connect to the database after multiple attempts")
                raise
    
    # Create the Updater and pass it your bot's token
    updater = Updater(TELEGRAM_TOKEN)
    
    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher
    
    # Register message handlers with explicit priorities
    # Lower group number = higher priority
    
    # Register message handler for monitoring the target channel (highest priority)
    dispatcher.add_handler(MessageHandler(
        Filters.chat_type.channel & Filters.update.channel_posts,
        handle_channel_post
    ), group=0)
    
    # Register message handler for monitoring the target group (second highest priority)
    # Use a very inclusive filter to catch all possible group messages
    dispatcher.add_handler(MessageHandler(
        Filters.update.message,  # Catch all regular messages
        handle_group_message
    ), group=0)
    
    # Register command handlers (lower priority than group/channel handlers)
    dispatcher.add_handler(CommandHandler("start", start), group=1)
    
    # Register message handlers (lower priority than group/channel handlers)
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, search_images), group=1)
    
    # Register callback query handler
    dispatcher.add_handler(CallbackQueryHandler(button_callback))
    
    # Register a handler for edited messages in groups
    dispatcher.add_handler(MessageHandler(
        Filters.chat_type.groups & Filters.update.edited_message,
        lambda u, c: logger.info(f"Received edited message in group: {u.edited_message.message_id}")
    ), group=1)
    
    # Add a catch-all handler for debugging
    dispatcher.add_handler(MessageHandler(
        Filters.all,
        lambda u, c: logger.info(f"Received unhandled update: {u}")
    ), group=999)  # Lower priority
    
    # Start the Bot
    updater.start_polling()
    
    # Run the bot until you press Ctrl-C
    updater.idle()
    
    # Close the database connection
    db.close_sync()

if __name__ == '__main__':
    main()
