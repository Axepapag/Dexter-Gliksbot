-- Migration 003: Knowledge Graph Schema
-- SQLite + NetworkX hybrid for BSM intelligence
-- Designed collaboratively by Claude (Anthropic) and Comet Assistant (Perplexity)

-- ============================================================
-- ENTITIES TABLE: Typed nodes in knowledge graph
-- ============================================================
CREATE TABLE IF NOT EXISTS entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,                  -- EntityType: agent, mission, collaboration, observation, action
    name TEXT NOT NULL,                  -- Human-readable identifier
    properties JSON,                     -- Flexible schema per entity type
    embedding BLOB,                      -- sentence-transformers embedding (384-dim float32)
    first_seen REAL NOT NULL,           -- Unix timestamp
    last_seen REAL NOT NULL,            -- Updated on each observation
    
    -- Indexes for fast lookups
    UNIQUE(type, name)                  -- Prevent duplicates within type
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_type_name ON entities(type, name);
CREATE INDEX IF NOT EXISTS idx_entities_last_seen ON entities(last_seen DESC);


-- ============================================================
-- RELATIONS TABLE: Typed edges between entities
-- ============================================================
CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    src_entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,        -- RelationType: executed_by, collaborated_with, preceded_by, etc.
    dst_entity_id INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    
    -- Confidence tracking (Bayesian Beta distribution)
    confidence REAL DEFAULT 0.5,        -- Current confidence (0.0-1.0)
    observed_count INTEGER DEFAULT 1,   -- How many times observed
    
    -- Bayesian parameters (stored in metadata JSON for flexibility)
    metadata JSON,                      -- {alpha: int, beta: int, ...}
    
    created_at REAL NOT NULL,          -- First observation timestamp
    updated_at REAL,                   -- Last update timestamp
    
    -- Prevent duplicate relations (same src, type, dst)
    UNIQUE(src_entity_id, relation_type, dst_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_relations_src ON relations(src_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_dst ON relations(dst_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation_type);
CREATE INDEX IF NOT EXISTS idx_relations_src_type ON relations(src_entity_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_relations_confidence ON relations(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_relations_created ON relations(created_at DESC);


-- ============================================================
-- PATTERNS TABLE: Materialized recurring patterns
-- ============================================================
CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT NOT NULL,         -- 'action_sequence', 'collaboration_pattern', 'error_chain'
    pattern_data JSON NOT NULL,         -- Flexible: sequence of entity IDs, relation types, etc.
    
    -- Occurrence tracking
    occurrences INTEGER DEFAULT 1,      -- How many times pattern observed
    confidence REAL DEFAULT 0.0,        -- Bayesian confidence (alpha/(alpha+beta))
    
    -- Temporal tracking
    first_seen REAL NOT NULL,          -- First observation
    last_seen REAL NOT NULL,           -- Most recent observation
    
    -- Pattern metadata
    metadata JSON,                      -- avg_duration, success_rate, mitigation, alpha, beta, etc.
    
    -- Unique constraint on pattern content (prevent duplicates)
    UNIQUE(pattern_type, pattern_data)
);

CREATE INDEX IF NOT EXISTS idx_patterns_type ON patterns(pattern_type);
CREATE INDEX IF NOT EXISTS idx_patterns_confidence ON patterns(pattern_type, confidence DESC);
CREATE INDEX IF NOT EXISTS idx_patterns_occurrences ON patterns(occurrences DESC);
CREATE INDEX IF NOT EXISTS idx_patterns_last_seen ON patterns(last_seen DESC);


-- ============================================================
-- PATTERN_INSTANCES TABLE: Link patterns to specific occurrences
-- ============================================================
CREATE TABLE IF NOT EXISTS pattern_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_id INTEGER NOT NULL REFERENCES patterns(id) ON DELETE CASCADE,
    
    entity_ids JSON,                    -- Specific entities involved in this instance
    timestamp REAL NOT NULL,            -- When this instance occurred
    metadata JSON                       -- Instance-specific context (duration, outcome, etc.)
);

CREATE INDEX IF NOT EXISTS idx_pattern_instances_pattern ON pattern_instances(pattern_id);
CREATE INDEX IF NOT EXISTS idx_pattern_instances_timestamp ON pattern_instances(timestamp DESC);


-- ============================================================
-- GRAPH_SNAPSHOTS TABLE: Track KG evolution over time (Comet's suggestion)
-- ============================================================
CREATE TABLE IF NOT EXISTS graph_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time REAL NOT NULL,
    
    -- Graph metrics
    entity_count INTEGER NOT NULL,
    relation_count INTEGER NOT NULL,
    pattern_count INTEGER NOT NULL,
    
    -- Top entities by degree
    metadata JSON                       -- {top_agents: [...], graph_density: 0.12, ...}
);

CREATE INDEX IF NOT EXISTS idx_snapshots_time ON graph_snapshots(snapshot_time DESC);


-- ============================================================
-- VIEWS: Convenient read-only access patterns
-- ============================================================

-- View: Recent high-confidence relations
CREATE VIEW IF NOT EXISTS v_confident_relations AS
SELECT 
    r.id,
    e1.type || ':' || e1.name AS source,
    r.relation_type,
    e2.type || ':' || e2.name AS target,
    r.confidence,
    r.observed_count,
    r.updated_at
FROM relations r
JOIN entities e1 ON r.src_entity_id = e1.id
JOIN entities e2 ON r.dst_entity_id = e2.id
WHERE r.confidence >= 0.7
ORDER BY r.updated_at DESC;


-- View: Active patterns (seen recently)
CREATE VIEW IF NOT EXISTS v_active_patterns AS
SELECT 
    p.id,
    p.pattern_type,
    p.pattern_data,
    p.occurrences,
    p.confidence,
    p.last_seen,
    p.metadata
FROM patterns p
WHERE p.last_seen > (strftime('%s', 'now') - 86400)  -- Last 24 hours
ORDER BY p.confidence DESC, p.occurrences DESC;


-- View: Agent collaboration network
CREATE VIEW IF NOT EXISTS v_agent_collaborations AS
SELECT 
    e1.name AS agent1,
    e2.name AS agent2,
    r.confidence,
    r.observed_count,
    r.metadata
FROM relations r
JOIN entities e1 ON r.src_entity_id = e1.id
JOIN entities e2 ON r.dst_entity_id = e2.id
WHERE r.relation_type = 'collaborated_with'
  AND e1.type = 'agent'
  AND e2.type = 'agent'
ORDER BY r.confidence DESC;


-- ============================================================
-- INITIAL DATA: Create BSM entity
-- ============================================================
INSERT OR IGNORE INTO entities (type, name, properties, first_seen, last_seen)
VALUES (
    'agent',
    'bsm',
    json('{"role": "omniscient_observer", "capabilities": ["memory", "learning", "context_provision"]}'),
    strftime('%s', 'now'),
    strftime('%s', 'now')
);

-- ============================================================
-- SNAPSHOT: Record initial empty state
-- ============================================================
INSERT INTO graph_snapshots (snapshot_time, entity_count, relation_count, pattern_count, metadata)
VALUES (
    strftime('%s', 'now'),
    1,  -- BSM entity
    0,
    0,
    json('{"note": "Initial migration, graph empty"}')
);
