CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,
    question TEXT NOT NULL,
    answer TEXT,
    intent TEXT,
    topic TEXT,
    topic_guess TEXT,
    confidence REAL,
    escalated BOOLEAN DEFAULT 0,
    escalation_reason TEXT,
    policy_cited TEXT,
    guardrail_flags TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_overrides (
    id INTEGER PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    topic TEXT,
    question_pattern TEXT,
    answer TEXT,
    author TEXT,
    source_conversation_id INTEGER
);

CREATE TABLE IF NOT EXISTS triage_queue (
    id INTEGER PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    conversation_id INTEGER NOT NULL,
    parent_email TEXT,
    priority TEXT,
    status TEXT DEFAULT 'open',
    resolved_at TIMESTAMP,
    resolved_by TEXT,
    resolution_text TEXT,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE TABLE IF NOT EXISTS center_config (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    checksum TEXT NOT NULL UNIQUE,
    filename TEXT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    status TEXT NOT NULL,
    error_message TEXT,
    page_count INTEGER,
    chunk_count INTEGER,
    topics TEXT,
    summary TEXT,
    superseded_by INTEGER,
    FOREIGN KEY (superseded_by) REFERENCES documents(id)
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    heading_path TEXT,
    topic TEXT,
    page_start INTEGER,
    page_end INTEGER,
    content TEXT NOT NULL,
    embedding BLOB,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON document_chunks(document_id) WHERE is_active = 1;
CREATE INDEX IF NOT EXISTS idx_chunks_topic ON document_chunks(topic) WHERE is_active = 1;
