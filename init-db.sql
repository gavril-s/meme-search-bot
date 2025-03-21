-- Enable the necessary extensions for full-text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create the memes table
CREATE TABLE IF NOT EXISTS memes (
    id SERIAL PRIMARY KEY,
    file_id VARCHAR(255) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ts_description TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', description)) STORED
);

-- Create indexes for full-text search
CREATE INDEX IF NOT EXISTS idx_memes_ts_description ON memes USING GIN (ts_description);
CREATE INDEX IF NOT EXISTS idx_memes_description_trgm ON memes USING GIN (description gin_trgm_ops);

-- Function to search memes by description
CREATE OR REPLACE FUNCTION search_memes(search_query TEXT)
RETURNS TABLE (
    id INTEGER,
    file_id VARCHAR(255),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE,
    rank FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.file_id,
        m.description,
        m.created_at,
        ts_rank(m.ts_description, to_tsquery('english', search_query)) +
        similarity(m.description, search_query) AS rank
    FROM
        memes m
    WHERE
        m.ts_description @@ to_tsquery('english', search_query) OR
        m.description % search_query
    ORDER BY
        rank DESC
    LIMIT 10;
END;
$$ LANGUAGE plpgsql;
