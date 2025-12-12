-- docker exec -it error-flow-agent-db-1 psql -U user -d errorflow





-- Create the `errors` table if it does not already exist
CREATE TABLE IF NOT EXISTS errors (
    id SERIAL PRIMARY KEY,
    service VARCHAR(50) NOT NULL,
    error_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    env VARCHAR(20) DEFAULT 'prod',
    path TEXT,
    trace_id VARCHAR(64)
);

-- Create the `error_groups` table if it does not already exist
CREATE TABLE IF NOT EXISTS error_groups (
    id SERIAL PRIMARY KEY,
    cluster_key VARCHAR(100) UNIQUE NOT NULL,  -- e.g. "user-api:NullPointer"
    service VARCHAR(50) NOT NULL,
    error_type VARCHAR(50) NOT NULL,
    title VARCHAR(200),
    summary TEXT,
    status VARCHAR(20) DEFAULT 'OPEN',         -- OPEN | QUIET | RESOLVED
    count INTEGER DEFAULT 0,
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW(),
    severity VARCHAR(20) DEFAULT 'unknown',
    ai_summary TEXT,
    ai_next_steps TEXT,
    resolution_reason TEXT,
    resolved_at TIMESTAMP
);







-- -- Drop and recreate the `errors` table
-- DROP TABLE IF EXISTS errors;

-- CREATE TABLE errors (
--     id SERIAL PRIMARY KEY,
--     service VARCHAR(50) NOT NULL,
--     error_type VARCHAR(50) NOT NULL,
--     message TEXT NOT NULL,
--     timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
--     env VARCHAR(20) DEFAULT 'prod',
--     path TEXT,
--     trace_id VARCHAR(64)
-- );

-- -- Drop and recreate the `error_groups` table
-- DROP TABLE IF EXISTS error_groups;

-- CREATE TABLE error_groups (
--     id SERIAL PRIMARY KEY,
--     cluster_key VARCHAR(100) UNIQUE NOT NULL,  -- e.g. "user-api:NullPointer"
--     service VARCHAR(50) NOT NULL,
--     error_type VARCHAR(50) NOT NULL,
--     title VARCHAR(200),
--     summary TEXT,
--     status VARCHAR(20) DEFAULT 'OPEN',         -- OPEN | QUIET | RESOLVED
--     count INTEGER DEFAULT 0,
--     first_seen TIMESTAMP DEFAULT NOW(),
--     last_seen TIMESTAMP DEFAULT NOW(),
--     severity VARCHAR(20) DEFAULT 'unknown',
--     ai_summary TEXT,
--     ai_next_steps TEXT,
--     resolution_reason TEXT,
--     resolved_at TIMESTAMP
-- );