-- Create extension for full-text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create table for storing images and their descriptions
CREATE TABLE IF NOT EXISTS meme_images (
    id SERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL,
    channel_id BIGINT NOT NULL,
    file_id TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(message_id, channel_id)
);

-- Create indexes for full-text search
CREATE INDEX IF NOT EXISTS idx_meme_images_description_gin ON meme_images USING gin(description gin_trgm_ops);

-- Create function to search for images based on description
CREATE OR REPLACE FUNCTION search_memes(search_query TEXT)
RETURNS TABLE (
    id INTEGER,
    message_id BIGINT,
    channel_id BIGINT,
    file_id TEXT,
    description TEXT,
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.message_id,
        m.channel_id,
        m.file_id,
        m.description,
        similarity(m.description, search_query) AS similarity
    FROM
        meme_images m
    WHERE
        m.description % search_query
    ORDER BY
        similarity DESC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql;
