import json
import asyncpg
import asyncio
from typing import List, Dict, Any, Optional, Tuple

class Database:
    def __init__(self, config_path: str = 'config.json'):
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        self.db_config = config['database']
        self.pool = None
        self._conn = None  # For synchronous operations
    
    async def connect(self):
        """Connect to the PostgreSQL database"""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                host=self.db_config['host'],
                port=self.db_config['port'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database=self.db_config['database']
            )
        return self.pool
    
    def connect_sync(self):
        """Connect to the PostgreSQL database (synchronous version)"""
        if self.pool is None:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the async connect method in the event loop
            self.pool = loop.run_until_complete(self.connect())
            
            # Close the event loop
            loop.close()
        
        return self.pool
    
    async def close(self):
        """Close the database connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
    
    def close_sync(self):
        """Close the database connection pool (synchronous version)"""
        if self.pool:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the async close method in the event loop
            loop.run_until_complete(self.close())
            
            # Close the event loop
            loop.close()
    
    async def save_image(self, message_id: int, channel_id: int, file_id: str, description: str) -> bool:
        """Save an image and its description to the database"""
        pool = await self.connect()
        
        try:
            async with pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO meme_images (message_id, channel_id, file_id, description)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (message_id, channel_id) 
                    DO UPDATE SET file_id = $3, description = $4
                ''', message_id, channel_id, file_id, description)
                return True
        except Exception as e:
            print(f"Error saving image: {e}")
            return False
    
    def save_image_sync(self, message_id: int, channel_id: int, file_id: str, description: str) -> bool:
        """Save an image and its description to the database (synchronous version)"""
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run the async save_image method in the event loop
            result = loop.run_until_complete(
                self.save_image(message_id, channel_id, file_id, description)
            )
            return result
        except Exception as e:
            print(f"Error saving image (sync): {e}")
            return False
        finally:
            # Close the event loop
            loop.close()
    
    async def search_images(self, query: str) -> List[Dict[str, Any]]:
        """Search for images based on description similarity"""
        pool = await self.connect()
        
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch('''
                    SELECT * FROM search_memes($1)
                ''', query)
                
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error searching images: {e}")
            return []
    
    def search_images_sync(self, query: str) -> List[Dict[str, Any]]:
        """Search for images based on description similarity (synchronous version)"""
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run the async search_images method in the event loop
            results = loop.run_until_complete(self.search_images(query))
            return results
        except Exception as e:
            print(f"Error searching images (sync): {e}")
            return []
        finally:
            # Close the event loop
            loop.close()
    
    async def get_image_by_id(self, image_id: int) -> Optional[Dict[str, Any]]:
        """Get an image by its ID"""
        pool = await self.connect()
        
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow('''
                    SELECT * FROM meme_images WHERE id = $1
                ''', image_id)
                
                return dict(row) if row else None
        except Exception as e:
            print(f"Error getting image: {e}")
            return None
    
    def get_image_by_id_sync(self, image_id: int) -> Optional[Dict[str, Any]]:
        """Get an image by its ID (synchronous version)"""
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run the async get_image_by_id method in the event loop
            result = loop.run_until_complete(self.get_image_by_id(image_id))
            return result
        except Exception as e:
            print(f"Error getting image (sync): {e}")
            return None
        finally:
            # Close the event loop
            loop.close()
