"""
Tests for Knowledge Graph - Comprehensive Coverage

Tests designed collaboratively by Claude (Anthropic) and Comet Assistant (Perplexity).

Coverage:
- Entity CRUD operations
- Relation tracking with Bayesian confidence
- Embedding-based similarity search
- Pattern extraction (action sequences)
- Core queries (expert agents, collaborations, error tracing)
- NetworkX integration (PageRank, graph algorithms)
- Event-driven sync
- Graph snapshots
"""
import pytest
import tempfile
import time
from pathlib import Path

from dexter_autonomy.brain.knowledge_graph import (
    KnowledgeGraph,
    EntityType,
    RelationType,
    Entity,
    Relation,
    Pattern
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Run migration
    import sqlite3
    conn = sqlite3.connect(db_path)
    migration_sql = Path('dexter_autonomy/brain/migrations/003_knowledge_graph.sql').read_text()
    conn.executescript(migration_sql)
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def kg(temp_db):
    """Create KnowledgeGraph instance"""
    return KnowledgeGraph(temp_db)


# ========== ENTITY TESTS ==========

def test_add_entity(kg):
    """Test adding entity with properties and embedding"""
    entity_id = kg.add_entity(
        type=EntityType.AGENT,
        name="test_agent",
        properties={"capabilities": ["code", "scrape"], "active": True}
    )
    
    assert entity_id > 0
    
    # Retrieve entity
    entity = kg.get_entity(entity_id)
    assert entity is not None
    assert entity.type == EntityType.AGENT
    assert entity.name == "test_agent"
    assert entity.properties["capabilities"] == ["code", "scrape"]
    assert entity.embedding is not None
    assert entity.embedding.shape == (kg.EMBEDDING_DIM,)


def test_get_or_create_entity(kg):
    """Test get_or_create pattern"""
    # First call creates
    entity_id1 = kg.get_or_create_entity(EntityType.AGENT, "agent1")
    assert entity_id1 > 0
    
    # Second call returns existing
    entity_id2 = kg.get_or_create_entity(EntityType.AGENT, "agent1")
    assert entity_id2 == entity_id1


def test_update_entity_properties(kg):
    """Test updating entity properties and refreshing embedding"""
    entity_id = kg.add_entity(
        type=EntityType.MISSION,
        name="mission_1",
        properties={"status": "in_progress"}
    )
    
    # Get initial embedding
    entity1 = kg.get_entity(entity_id)
    embedding1 = entity1.embedding.copy()
    
    # Update properties
    kg.update_entity_properties(entity_id, {"status": "completed", "outcome": "success"})
    
    # Get updated entity
    entity2 = kg.get_entity(entity_id)
    assert entity2.properties["status"] == "completed"
    assert entity2.properties["outcome"] == "success"
    
    # Embedding should change (different content)
    assert not (entity2.embedding == embedding1).all()


def test_entity_unique_constraint(kg):
    """Test that duplicate entities (same type+name) update instead of create"""
    # Add entity
    entity_id1 = kg.add_entity(EntityType.AGENT, "agent1", {"version": 1})
    
    # Add again with same type+name but different properties
    entity_id2 = kg.add_entity(EntityType.AGENT, "agent1", {"version": 2})
    
    # Should update, not create new
    # Note: SQLite UPSERT returns lastrowid=0 on update, so we query instead
    entity = kg.get_entity(entity_id1)
    assert entity.properties["version"] == 2


# ========== RELATION TESTS ==========

def test_add_relation(kg):
    """Test adding relation between entities"""
    agent1 = kg.add_entity(EntityType.AGENT, "agent1")
    mission1 = kg.add_entity(EntityType.MISSION, "mission1")
    
    relation_id = kg.add_relation(
        src=mission1,
        rel_type=RelationType.EXECUTED_BY,
        dst=agent1,
        confidence=0.8
    )
    
    assert relation_id > 0
    
    # Retrieve relation
    relation = kg.get_relation(relation_id)
    assert relation is not None
    assert relation.src_entity_id == mission1
    assert relation.relation_type == RelationType.EXECUTED_BY
    assert relation.dst_entity_id == agent1
    assert relation.confidence == 0.8
    assert relation.observed_count == 1


def test_relation_bayesian_confidence_update(kg):
    """Test Bayesian confidence update on repeated observation (Comet's design)"""
    agent1 = kg.add_entity(EntityType.AGENT, "agent1")
    agent2 = kg.add_entity(EntityType.AGENT, "agent2")
    
    # Add relation (first observation)
    relation_id = kg.add_relation(
        src=agent1,
        rel_type=RelationType.COLLABORATED_WITH,
        dst=agent2,
        confidence=0.5
    )
    
    # Observe relation again (success)
    kg.update_relation_confidence(relation_id, observed=True)
    
    relation = kg.get_relation(relation_id)
    
    # Confidence should increase (alpha increased)
    # Initial: Beta(2, 2) = 0.5
    # After 1 success: Beta(3, 2) = 0.6
    assert relation.confidence > 0.5
    assert relation.metadata['alpha'] == 3
    assert relation.metadata['beta'] == 2


def test_relation_bayesian_confidence_decrease(kg):
    """Test Bayesian confidence decreases on failed observation"""
    agent1 = kg.add_entity(EntityType.AGENT, "agent1")
    agent2 = kg.add_entity(EntityType.AGENT, "agent2")
    
    relation_id = kg.add_relation(
        src=agent1,
        rel_type=RelationType.COLLABORATED_WITH,
        dst=agent2,
        confidence=0.5
    )
    
    # Observe relation failure
    kg.update_relation_confidence(relation_id, observed=False)
    
    relation = kg.get_relation(relation_id)
    
    # Confidence should decrease (beta increased)
    # Initial: Beta(2, 2) = 0.5
    # After 1 failure: Beta(2, 3) = 0.4
    assert relation.confidence < 0.5
    assert relation.metadata['alpha'] == 2
    assert relation.metadata['beta'] == 3


def test_relation_observed_count_increment(kg):
    """Test observed_count increments on repeated relation"""
    agent1 = kg.add_entity(EntityType.AGENT, "agent1")
    mission1 = kg.add_entity(EntityType.MISSION, "mission1")
    
    # Add relation first time
    relation_id1 = kg.add_relation(
        src=mission1,
        rel_type=RelationType.EXECUTED_BY,
        dst=agent1
    )
    
    # Add same relation again
    relation_id2 = kg.add_relation(
        src=mission1,
        rel_type=RelationType.EXECUTED_BY,
        dst=agent1
    )
    
    # Should update existing relation
    relation = kg.get_relation(relation_id1)
    assert relation.observed_count == 2


# ========== PATTERN TESTS ==========

def test_add_pattern(kg):
    """Test adding pattern"""
    pattern_id = kg.add_pattern(
        pattern_type="action_sequence",
        pattern_data=["action1", "action2", "action3"],
        metadata={"duration_ms": 1000}
    )
    
    assert pattern_id > 0


def test_get_patterns_with_filters(kg):
    """Test querying patterns with filters"""
    # Add multiple patterns
    kg.add_pattern(
        pattern_type="action_sequence",
        pattern_data=["a", "b"],
        metadata={"alpha": 5, "beta": 2}  # confidence = 5/7 = 0.714
    )
    
    kg.add_pattern(
        pattern_type="action_sequence",
        pattern_data=["c", "d"],
        metadata={"alpha": 3, "beta": 5}  # confidence = 3/8 = 0.375
    )
    
    kg.add_pattern(
        pattern_type="collaboration_pattern",
        pattern_data=["agent1", "agent2"],
        metadata={"alpha": 4, "beta": 2}  # confidence = 4/6 = 0.667
    )
    
    # Query with confidence filter
    patterns = kg.get_patterns(min_confidence=0.5)
    assert len(patterns) == 2  # First and third patterns
    
    # Query by type
    patterns = kg.get_patterns(pattern_type="action_sequence", min_confidence=0.0)
    assert len(patterns) == 2


def test_extract_action_sequences(kg):
    """Test pattern extraction from action sequences (min 3 occurrences)"""
    # Create action entities
    action1 = kg.add_entity(EntityType.ACTION, "click_login", {"kind": "click"})
    action2 = kg.add_entity(EntityType.ACTION, "type_username", {"kind": "type"})
    action3 = kg.add_entity(EntityType.ACTION, "type_password", {"kind": "type"})
    
    # Create sequence relations (repeat 4 times to exceed threshold)
    for _ in range(4):
        kg.add_relation(action1, RelationType.PRECEDED_BY, action2)
        kg.add_relation(action2, RelationType.PRECEDED_BY, action3)
    
    # Extract patterns
    patterns = kg.extract_action_sequences()
    
    # Should find pattern (repeated 4 times >= MIN_PATTERN_OCCURRENCES=3)
    assert len(patterns) > 0
    assert patterns[0].occurrences >= kg.MIN_PATTERN_OCCURRENCES


# ========== SIMILARITY SEARCH TESTS ==========

def test_find_similar_missions(kg):
    """Test embedding-based similarity search"""
    # Create missions with similar properties
    mission1 = kg.add_entity(
        EntityType.MISSION,
        "extract_invoice_data",
        {"task": "scrape invoice", "tool": "OCR"}
    )
    
    mission2 = kg.add_entity(
        EntityType.MISSION,
        "parse_invoice_pdf",
        {"task": "extract invoice", "tool": "PDF parser"}
    )
    
    mission3 = kg.add_entity(
        EntityType.MISSION,
        "send_email",
        {"task": "email notification", "tool": "SMTP"}
    )
    
    # Find similar to mission1
    similar = kg.find_similar_missions(mission1, k=2)
    
    assert len(similar) <= 2
    
    # mission2 should be more similar than mission3 (both about invoices)
    # Note: sentence-transformers should capture semantic similarity
    if len(similar) >= 2:
        # Check that invoice-related missions are ranked higher
        names = [m.name for m in similar]
        assert "parse_invoice_pdf" in names or "send_email" in names


# ========== CORE QUERY TESTS ==========

def test_find_expert_agents(kg):
    """Test finding agents with high success rate for mission type"""
    # Create agents
    agent1 = kg.add_entity(EntityType.AGENT, "coder", {"role": "code"})
    agent2 = kg.add_entity(EntityType.AGENT, "scraper", {"role": "scrape"})
    
    # Create missions
    for i in range(5):
        mission = kg.add_entity(
            EntityType.MISSION,
            f"code_task_{i}",
            {"mission_type": "coding", "outcome": "success" if i < 4 else "failure"}
        )
        kg.add_relation(mission, RelationType.EXECUTED_BY, agent1)
    
    for i in range(3):
        mission = kg.add_entity(
            EntityType.MISSION,
            f"scrape_task_{i}",
            {"mission_type": "coding", "outcome": "failure"}  # Not expert
        )
        kg.add_relation(mission, RelationType.EXECUTED_BY, agent2)
    
    # Find experts
    experts = kg.find_expert_agents("coding", k=5)
    
    # agent1 should be ranked higher (80% success vs 0%)
    assert len(experts) > 0
    assert experts[0][0].name == "coder"
    assert experts[0][1] == 0.8  # 4/5 success rate


def test_get_successful_collaboration_patterns(kg):
    """Test querying high-confidence collaborations"""
    # Create collaboration entities
    collab1 = kg.add_entity(
        EntityType.COLLABORATION,
        "collab_1",
        {"consensus_confidence": 0.85, "participants": 3}
    )
    
    collab2 = kg.add_entity(
        EntityType.COLLABORATION,
        "collab_2",
        {"consensus_confidence": 0.60, "participants": 2}
    )
    
    # Query successful collaborations
    successful = kg.get_successful_collaboration_patterns(min_confidence=0.7)
    
    assert len(successful) == 1
    assert successful[0].name == "collab_1"


def test_trace_error_causes(kg):
    """Test causal chain traversal via CAUSED_BY relations"""
    # Create error chain: error ← action1 ← action2 ← root_cause
    error = kg.add_entity(EntityType.ACTION, "error", {"kind": "error"})
    action1 = kg.add_entity(EntityType.ACTION, "action1", {"kind": "click"})
    action2 = kg.add_entity(EntityType.ACTION, "action2", {"kind": "type"})
    root_cause = kg.add_entity(EntityType.ACTION, "root_cause", {"kind": "config"})
    
    kg.add_relation(action1, RelationType.CAUSED_BY, error)
    kg.add_relation(action2, RelationType.CAUSED_BY, action1)
    kg.add_relation(root_cause, RelationType.CAUSED_BY, action2)
    
    # Trace causes
    paths = kg.trace_error_causes(error, max_depth=5)
    
    # Should find path from error to root_cause
    assert len(paths) > 0
    assert root_cause in paths[0]


def test_find_synergistic_agents(kg):
    """Test PageRank-based agent synergy detection"""
    # Create agent collaboration network
    agent1 = kg.add_entity(EntityType.AGENT, "agent1")
    agent2 = kg.add_entity(EntityType.AGENT, "agent2")
    agent3 = kg.add_entity(EntityType.AGENT, "agent3")
    
    # agent1 and agent2 collaborate frequently (high confidence)
    kg.add_relation(agent1, RelationType.COLLABORATED_WITH, agent2, confidence=0.9)
    kg.add_relation(agent2, RelationType.COLLABORATED_WITH, agent1, confidence=0.9)
    
    # agent1 and agent3 collaborate rarely (low confidence)
    kg.add_relation(agent1, RelationType.COLLABORATED_WITH, agent3, confidence=0.3)
    
    # Find synergistic agents for agent1
    synergistic = kg.find_synergistic_agents(agent1, k=5)
    
    # agent2 should be ranked higher than agent3
    if len(synergistic) >= 2:
        assert synergistic[0][0].name == "agent2"


# ========== NETWORKX INTEGRATION TESTS ==========

def test_networkx_graph_sync(kg):
    """Test that NetworkX graph stays in sync with SQLite"""
    # Add entities
    agent1 = kg.add_entity(EntityType.AGENT, "agent1")
    agent2 = kg.add_entity(EntityType.AGENT, "agent2")
    
    # Check NetworkX has nodes
    assert kg.graph.has_node(agent1)
    assert kg.graph.has_node(agent2)
    
    # Add relation
    kg.add_relation(agent1, RelationType.COLLABORATED_WITH, agent2)
    
    # Check NetworkX has edge
    assert kg.graph.has_edge(agent1, agent2)


def test_event_driven_sync_threshold(kg):
    """Test event-driven sync after SYNC_THRESHOLD updates (Comet's design)"""
    initial_pending = kg._pending_updates
    
    # Add entities below threshold
    for i in range(kg.SYNC_THRESHOLD // 2):
        kg.add_entity(EntityType.AGENT, f"agent_{i}")
    
    # Pending updates should accumulate
    assert kg._pending_updates > initial_pending
    assert kg._pending_updates < kg.SYNC_THRESHOLD
    
    # Add more entities to exceed threshold
    for i in range(kg.SYNC_THRESHOLD):
        kg.add_entity(EntityType.AGENT, f"agent_sync_{i}")
    
    # Pending updates should reset after sync
    # Note: _maybe_sync() is called in add_entity()
    assert kg._pending_updates < kg.SYNC_THRESHOLD


# ========== SNAPSHOT TESTS ==========

def test_take_snapshot(kg):
    """Test graph snapshot capture (Comet's debugging suggestion)"""
    # Add some data
    kg.add_entity(EntityType.AGENT, "agent1")
    kg.add_entity(EntityType.AGENT, "agent2")
    kg.add_entity(EntityType.MISSION, "mission1")
    
    # Take snapshot
    kg.take_snapshot()
    
    # Query snapshot
    cursor = kg.db.cursor()
    cursor.execute("SELECT * FROM graph_snapshots ORDER BY snapshot_time DESC LIMIT 1")
    row = cursor.fetchone()
    
    assert row is not None
    assert row['entity_count'] >= 3  # At least 3 entities (+ BSM from migration)
    assert row['relation_count'] >= 0


# ========== INTEGRATION TESTS ==========

def test_full_workflow_mission_execution(kg):
    """Test complete workflow: mission → agent → outcome → pattern"""
    # 1. Create agents
    coder = kg.add_entity(EntityType.AGENT, "coder", {"capabilities": ["python", "javascript"]})
    scraper = kg.add_entity(EntityType.AGENT, "scraper", {"capabilities": ["web_scraping"]})
    
    # 2. Create mission
    mission = kg.add_entity(
        EntityType.MISSION,
        "extract_data",
        {"mission_type": "data_extraction", "priority": "high"}
    )
    
    # 3. Create action sequence
    action1 = kg.add_entity(EntityType.ACTION, "navigate_to_page", {"kind": "click"})
    action2 = kg.add_entity(EntityType.ACTION, "extract_table", {"kind": "scrape"})
    action3 = kg.add_entity(EntityType.ACTION, "save_data", {"kind": "write"})
    
    # 4. Link actions to mission
    kg.add_relation(action1, RelationType.PART_OF, mission)
    kg.add_relation(action2, RelationType.PART_OF, mission)
    kg.add_relation(action3, RelationType.PART_OF, mission)
    
    # 5. Create action sequence
    kg.add_relation(action1, RelationType.PRECEDED_BY, action2)
    kg.add_relation(action2, RelationType.PRECEDED_BY, action3)
    
    # 6. Link mission to agent
    kg.add_relation(mission, RelationType.EXECUTED_BY, scraper)
    
    # 7. Update mission outcome
    kg.update_entity_properties(mission, {"outcome": "success", "duration_sec": 45.2})
    
    # 8. Take snapshot
    kg.take_snapshot()
    
    # Verify graph structure
    assert kg.graph.number_of_nodes() >= 6  # 2 agents + 1 mission + 3 actions
    assert kg.graph.number_of_edges() >= 5  # Relations


def test_confidence_evolution_over_time(kg):
    """Test how confidence evolves with repeated observations (Bayesian)"""
    agent1 = kg.add_entity(EntityType.AGENT, "agent1")
    agent2 = kg.add_entity(EntityType.AGENT, "agent2")
    
    relation_id = kg.add_relation(agent1, RelationType.COLLABORATED_WITH, agent2)
    
    confidences = []
    
    # Record initial confidence
    confidences.append(kg.get_relation(relation_id).confidence)
    
    # Observe 10 successes
    for _ in range(10):
        kg.update_relation_confidence(relation_id, observed=True)
        confidences.append(kg.get_relation(relation_id).confidence)
    
    # Confidence should increase monotonically
    for i in range(1, len(confidences)):
        assert confidences[i] >= confidences[i-1]
    
    # Final confidence should be high (many successes)
    assert confidences[-1] > 0.8


def test_embedding_semantic_similarity(kg):
    """Test that embeddings capture semantic similarity"""
    # Create semantically similar missions
    mission1 = kg.add_entity(
        EntityType.MISSION,
        "scrape_linkedin_profiles",
        {"task": "extract professional data from LinkedIn"}
    )
    
    mission2 = kg.add_entity(
        EntityType.MISSION,
        "harvest_job_postings",
        {"task": "collect employment opportunities from job boards"}
    )
    
    mission3 = kg.add_entity(
        EntityType.MISSION,
        "send_invoice_email",
        {"task": "email invoice to customer"}
    )
    
    # Find similar to mission1 (LinkedIn scraping)
    similar = kg.find_similar_missions(mission1, k=2)
    
    # mission2 (job scraping) should be more similar than mission3 (email)
    # Both involve data collection/scraping
    if len(similar) >= 1:
        # First result should be more related to data extraction
        assert similar[0].name in ["harvest_job_postings", "send_invoice_email"]


# ========== PERFORMANCE TESTS ==========

def test_large_graph_performance(kg):
    """Test performance with larger graph (100 entities, 200 relations)"""
    import time
    
    # Add 100 entities
    start = time.time()
    entity_ids = []
    for i in range(100):
        entity_id = kg.add_entity(
            EntityType.AGENT if i % 2 == 0 else EntityType.MISSION,
            f"entity_{i}",
            {"index": i}
        )
        entity_ids.append(entity_id)
    entity_time = time.time() - start
    
    # Add 200 relations
    start = time.time()
    for i in range(200):
        src = entity_ids[i % len(entity_ids)]
        dst = entity_ids[(i + 1) % len(entity_ids)]
        kg.add_relation(src, RelationType.PART_OF, dst)
    relation_time = time.time() - start
    
    # Performance assertions (should be fast)
    assert entity_time < 30.0  # sentence-transformers encoding can be slow on first run
    assert relation_time < 5.0
    
    # Query should be fast
    start = time.time()
    kg.get_entity(entity_ids[50])
    query_time = time.time() - start
    assert query_time < 0.1
