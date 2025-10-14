"""
Knowledge Graph for Dexter-Gliksbot BSM Intelligence

SQLite + NetworkX hybrid architecture:
- SQLite: Persistent storage (entities, relations, patterns)
- NetworkX: In-memory graph for algorithms (PageRank, shortest path, community detection)
- sentence-transformers: Semantic embeddings for similarity search

Architecture designed collaboratively by Claude (Anthropic) and Comet Assistant (Perplexity).

Key Features:
- Bayesian confidence updates (Beta distribution)
- Event-driven sync (SQLite ↔ NetworkX after 100 updates)
- Pattern extraction (min 3 occurrences)
- Semantic similarity via all-MiniLM-L6-v2
- 10 core queries for BSM context-aware intelligence
"""
from __future__ import annotations

import atexit
import json
import sqlite3
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import numpy as np
from sentence_transformers import SentenceTransformer


class EntityType(str, Enum):
    """Types of entities in knowledge graph"""
    AGENT = "agent"                 # General agents, Dexter, BSM
    MISSION = "mission"             # User-assigned tasks
    COLLABORATION = "collaboration" # CollaborationManager sessions
    OBSERVATION = "observation"     # BSM-captured context snapshots
    ACTION = "action"               # Executed intents (click, type, OCR)


class RelationType(str, Enum):
    """Types of relations between entities"""
    # Agent relations
    EXECUTED_BY = "executed_by"               # Mission → Agent
    COLLABORATED_WITH = "collaborated_with"   # Agent ↔ Agent
    PROPOSED_BY = "proposed_by"               # Proposal → Agent
    
    # Temporal relations
    PRECEDED_BY = "preceded_by"               # Action → Action (sequence)
    CAUSED_BY = "caused_by"                   # Error → Action
    RESOLVED_BY = "resolved_by"               # Issue → Solution
    
    # Context relations
    OBSERVED_IN = "observed_in"               # Action → Observation
    PART_OF = "part_of"                       # Action → Mission
    SIMILAR_TO = "similar_to"                 # Mission ↔ Mission


@dataclass
class Entity:
    """Entity node in knowledge graph"""
    id: int
    type: EntityType
    name: str
    properties: Dict[str, Any]
    embedding: Optional[np.ndarray]
    first_seen: float
    last_seen: float


@dataclass
class Relation:
    """Relation edge in knowledge graph"""
    id: int
    src_entity_id: int
    relation_type: RelationType
    dst_entity_id: int
    confidence: float
    observed_count: int
    metadata: Dict[str, Any]
    created_at: float
    updated_at: Optional[float]


@dataclass
class Pattern:
    """Recurring pattern in knowledge graph"""
    id: int
    pattern_type: str
    pattern_data: Any
    occurrences: int
    confidence: float
    first_seen: float
    last_seen: float
    metadata: Dict[str, Any]


class KnowledgeGraph:
    """
    Hybrid SQLite + NetworkX knowledge graph for BSM intelligence.
    
    Storage:
    - SQLite: Persistent entities, relations, patterns
    - NetworkX: In-memory graph for algorithms
    
    Sync Strategy:
    - Event-driven: Sync after 100 updates
    - Shutdown hook: Force sync on exit
    """
    
    # Constants
    SYNC_THRESHOLD = 100        # Sync after N updates
    MIN_PATTERN_OCCURRENCES = 3 # Minimum to consider pattern
    EMBEDDING_DIM = 384         # all-MiniLM-L6-v2 dimension
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row  # Dict-like access
        
        # NetworkX in-memory graph (MultiDiGraph allows multiple edges)
        self.graph = nx.MultiDiGraph()
        
        # sentence-transformers for embeddings
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Sync tracking
        self._pending_updates = 0
        
        # Register shutdown hook (Comet's suggestion)
        atexit.register(self._force_sync)
        
        # Load graph from database
        self._sync_from_db()
    
    # ========== ENTITY CRUD ==========
    
    def add_entity(
        self,
        type: EntityType,
        name: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Add entity to knowledge graph with semantic embedding.
        
        Returns:
            entity_id
        """
        properties = properties or {}
        now = time.time()
        
        # Create semantic representation
        text = f"{type.value} {name} {json.dumps(properties)}"
        embedding = self.encoder.encode(text)
        embedding_bytes = embedding.tobytes()
        
        cursor = self.db.cursor()
        
        # Insert or update (UPSERT pattern)
        cursor.execute("""
            INSERT INTO entities (type, name, properties, embedding, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(type, name) DO UPDATE SET
                properties = excluded.properties,
                embedding = excluded.embedding,
                last_seen = excluded.last_seen
        """, (type.value, name, json.dumps(properties), embedding_bytes, now, now))
        
        entity_id = cursor.lastrowid
        self.db.commit()
        
        # Update NetworkX graph
        self.graph.add_node(entity_id, type=type.value, name=name, **properties)
        
        self._pending_updates += 1
        self._maybe_sync()
        
        return entity_id
    
    def get_entity(self, entity_id: int) -> Optional[Entity]:
        """Retrieve entity by ID"""
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return Entity(
            id=row['id'],
            type=EntityType(row['type']),
            name=row['name'],
            properties=json.loads(row['properties']) if row['properties'] else {},
            embedding=np.frombuffer(row['embedding'], dtype=np.float32) if row['embedding'] else None,
            first_seen=row['first_seen'],
            last_seen=row['last_seen']
        )
    
    def get_or_create_entity(self, type: EntityType, name: str, properties: Optional[Dict] = None) -> int:
        """Get existing entity or create new one"""
        cursor = self.db.cursor()
        cursor.execute("SELECT id FROM entities WHERE type = ? AND name = ?", (type.value, name))
        row = cursor.fetchone()
        
        if row:
            return row['id']
        else:
            return self.add_entity(type, name, properties)
    
    def update_entity_properties(self, entity_id: int, properties: Dict[str, Any]):
        """Update entity properties and refresh embedding"""
        entity = self.get_entity(entity_id)
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")
        
        # Merge properties
        merged_props = {**entity.properties, **properties}
        
        # Re-compute embedding
        text = f"{entity.type.value} {entity.name} {json.dumps(merged_props)}"
        embedding = self.encoder.encode(text)
        embedding_bytes = embedding.tobytes()
        
        cursor = self.db.cursor()
        cursor.execute("""
            UPDATE entities 
            SET properties = ?, embedding = ?, last_seen = ?
            WHERE id = ?
        """, (json.dumps(merged_props), embedding_bytes, time.time(), entity_id))
        self.db.commit()
        
        # Update NetworkX
        self.graph.nodes[entity_id].update(merged_props)
        
        self._pending_updates += 1
        self._maybe_sync()
    
    # ========== RELATION CRUD ==========
    
    def add_relation(
        self,
        src: int,
        rel_type: RelationType,
        dst: int,
        confidence: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Add relation between entities.
        
        If relation exists, increments observed_count and updates confidence.
        """
        metadata = metadata or {}
        now = time.time()
        
        # Initialize Bayesian parameters if not present
        if 'alpha' not in metadata:
            metadata['alpha'] = 2  # Prior: Beta(2, 2) = moderate uncertainty
        if 'beta' not in metadata:
            metadata['beta'] = 2
        
        cursor = self.db.cursor()
        
        # Check if relation exists
        cursor.execute("""
            SELECT id, observed_count, metadata FROM relations
            WHERE src_entity_id = ? AND relation_type = ? AND dst_entity_id = ?
        """, (src, rel_type.value, dst))
        
        row = cursor.fetchone()
        
        if row:
            # Relation exists - update observed_count
            relation_id = row['id']
            observed_count = row['observed_count'] + 1
            
            # Update Bayesian confidence (Comet's design)
            existing_meta = json.loads(row['metadata']) if row['metadata'] else {}
            alpha = existing_meta.get('alpha', 2) + 1  # Successful observation
            beta = existing_meta.get('beta', 2)
            new_confidence = alpha / (alpha + beta)
            
            updated_metadata = {**existing_meta, 'alpha': alpha, 'beta': beta}
            
            cursor.execute("""
                UPDATE relations
                SET confidence = ?, observed_count = ?, metadata = ?, updated_at = ?
                WHERE id = ?
            """, (new_confidence, observed_count, json.dumps(updated_metadata), now, relation_id))
        else:
            # New relation
            cursor.execute("""
                INSERT INTO relations (src_entity_id, relation_type, dst_entity_id, confidence, observed_count, metadata, created_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (src, rel_type.value, dst, confidence, json.dumps(metadata), now))
            relation_id = cursor.lastrowid
        
        self.db.commit()
        
        # Update NetworkX graph
        self.graph.add_edge(src, dst, key=rel_type.value, confidence=confidence, **metadata)
        
        self._pending_updates += 1
        self._maybe_sync()
        
        return relation_id
    
    def get_relation(self, relation_id: int) -> Optional[Relation]:
        """Retrieve relation by ID"""
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM relations WHERE id = ?", (relation_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return Relation(
            id=row['id'],
            src_entity_id=row['src_entity_id'],
            relation_type=RelationType(row['relation_type']),
            dst_entity_id=row['dst_entity_id'],
            confidence=row['confidence'],
            observed_count=row['observed_count'],
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
    
    def update_relation_confidence(self, relation_id: int, observed: bool):
        """
        Update relation confidence using Bayesian Beta distribution (Comet's design).
        
        Args:
            relation_id: Relation to update
            observed: True if relation observed successfully, False if not
        """
        relation = self.get_relation(relation_id)
        if not relation:
            raise ValueError(f"Relation {relation_id} not found")
        
        # Get Bayesian parameters
        alpha = relation.metadata.get('alpha', 2)
        beta = relation.metadata.get('beta', 2)
        
        # Update based on observation
        if observed:
            alpha += 1
        else:
            beta += 1
        
        # Calculate new confidence
        confidence = alpha / (alpha + beta)
        
        # Update database
        updated_metadata = {**relation.metadata, 'alpha': alpha, 'beta': beta}
        
        cursor = self.db.cursor()
        cursor.execute("""
            UPDATE relations
            SET confidence = ?, metadata = ?, updated_at = ?
            WHERE id = ?
        """, (confidence, json.dumps(updated_metadata), time.time(), relation_id))
        self.db.commit()
        
        # Update NetworkX
        if self.graph.has_edge(relation.src_entity_id, relation.dst_entity_id, key=relation.relation_type.value):
            self.graph[relation.src_entity_id][relation.dst_entity_id][relation.relation_type.value]['confidence'] = confidence
        
        self._pending_updates += 1
        self._maybe_sync()
    
    # ========== PATTERN MANAGEMENT ==========
    
    def add_pattern(
        self,
        pattern_type: str,
        pattern_data: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Add or update pattern"""
        metadata = metadata or {}
        now = time.time()
        
        # Initialize Bayesian parameters
        if 'alpha' not in metadata:
            metadata['alpha'] = 2
        if 'beta' not in metadata:
            metadata['beta'] = 2
        
        confidence = metadata['alpha'] / (metadata['alpha'] + metadata['beta'])
        
        cursor = self.db.cursor()
        
        # Serialize pattern_data
        pattern_json = json.dumps(pattern_data)
        
        # Upsert pattern
        cursor.execute("""
            INSERT INTO patterns (pattern_type, pattern_data, occurrences, confidence, first_seen, last_seen, metadata)
            VALUES (?, ?, 1, ?, ?, ?, ?)
            ON CONFLICT(pattern_type, pattern_data) DO UPDATE SET
                occurrences = occurrences + 1,
                last_seen = excluded.last_seen
        """, (pattern_type, pattern_json, confidence, now, now, json.dumps(metadata)))
        
        pattern_id = cursor.lastrowid
        self.db.commit()
        
        return pattern_id
    
    def get_patterns(
        self,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.0,
        min_occurrences: int = 1
    ) -> List[Pattern]:
        """Query patterns with filters"""
        cursor = self.db.cursor()
        
        query = """
            SELECT * FROM patterns
            WHERE confidence >= ? AND occurrences >= ?
        """
        params = [min_confidence, min_occurrences]
        
        if pattern_type:
            query += " AND pattern_type = ?"
            params.append(pattern_type)
        
        query += " ORDER BY confidence DESC, occurrences DESC"
        
        cursor.execute(query, params)
        
        patterns = []
        for row in cursor.fetchall():
            patterns.append(Pattern(
                id=row['id'],
                pattern_type=row['pattern_type'],
                pattern_data=json.loads(row['pattern_data']),
                occurrences=row['occurrences'],
                confidence=row['confidence'],
                first_seen=row['first_seen'],
                last_seen=row['last_seen'],
                metadata=json.loads(row['metadata']) if row['metadata'] else {}
            ))
        
        return patterns
    
    # ========== CORE QUERIES (BSM Intelligence) ==========
    
    def find_similar_missions(self, mission_id: int, k: int = 5) -> List[Entity]:
        """
        Query 1: Find missions similar to current mission via embedding similarity.
        
        Uses cosine similarity on sentence-transformers embeddings.
        """
        mission = self.get_entity(mission_id)
        if not mission or mission.type != EntityType.MISSION:
            return []
        
        if mission.embedding is None:
            return []
        
        query_embedding = mission.embedding
        
        # Load all mission embeddings
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT id, embedding FROM entities
            WHERE type = 'mission' AND id != ? AND embedding IS NOT NULL
        """, (mission_id,))
        
        similarities = []
        for row in cursor.fetchall():
            emb = np.frombuffer(row['embedding'], dtype=np.float32)
            
            # Cosine similarity
            sim = np.dot(query_embedding, emb) / (np.linalg.norm(query_embedding) * np.linalg.norm(emb))
            similarities.append((row['id'], sim))
        
        # Top-k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [self.get_entity(id) for id, _ in similarities[:k]]
    
    def find_expert_agents(self, mission_type: str, k: int = 5) -> List[Tuple[Entity, float]]:
        """
        Query 2: Find agents with high success rate for mission type.
        
        Returns: List of (agent_entity, success_rate) sorted by success rate
        """
        cursor = self.db.cursor()
        
        # Query missions of this type
        cursor.execute("""
            SELECT e.id, e.properties
            FROM entities e
            WHERE e.type = 'mission'
              AND json_extract(e.properties, '$.mission_type') = ?
        """, (mission_type,))
        
        mission_ids = [row['id'] for row in cursor.fetchall()]
        
        if not mission_ids:
            return []
        
        # Find agents who executed these missions
        # Note: relation is mission EXECUTED_BY agent, so mission is src, agent is dst
        placeholders = ','.join('?' * len(mission_ids))
        cursor.execute(f"""
            SELECT 
                r.dst_entity_id AS agent_id,
                COUNT(*) AS total_missions,
                SUM(CASE WHEN json_extract(m.properties, '$.outcome') = 'success' THEN 1 ELSE 0 END) AS successful_missions
            FROM relations r
            JOIN entities m ON r.src_entity_id = m.id
            WHERE r.relation_type = 'executed_by'
              AND r.src_entity_id IN ({placeholders})
            GROUP BY r.dst_entity_id
            HAVING total_missions >= 3
            ORDER BY (CAST(successful_missions AS REAL) / total_missions) DESC
            LIMIT ?
        """, (*mission_ids, k))
        
        results = []
        for row in cursor.fetchall():
            agent = self.get_entity(row['agent_id'])
            success_rate = row['successful_missions'] / row['total_missions']
            results.append((agent, success_rate))
        
        return results
    
    def get_successful_collaboration_patterns(self, min_confidence: float = 0.7) -> List[Entity]:
        """Query 3: Collaborations that reached high-confidence consensus"""
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT id FROM entities
            WHERE type = 'collaboration'
              AND json_extract(properties, '$.consensus_confidence') >= ?
            ORDER BY json_extract(properties, '$.consensus_confidence') DESC
        """, (min_confidence,))
        
        return [self.get_entity(row['id']) for row in cursor.fetchall()]
    
    def trace_error_causes(self, error_id: int, max_depth: int = 5) -> List[List[int]]:
        """
        Query 4: Walk CAUSED_BY edges to find root cause.
        
        Returns: List of paths (entity ID chains) from error to root causes
        
        Note: CAUSED_BY relation means "cause CAUSED_BY effect", so to trace from
        effect (error) to cause, we follow the edges in the dst->src direction.
        """
        if not self.graph.has_node(error_id):
            return []
        
        # Find all paths from error following CAUSED_BY edges
        paths = []
        
        def dfs(node, path, depth):
            if depth >= max_depth:
                paths.append(path[:])
                return
            
            # Find edges where this node is the dst (effect)
            # We want to find src (cause) where edge is cause->CAUSED_BY->effect
            has_causes = False
            
            # Check all predecessors (nodes with edges pointing to current node)
            for pred in self.graph.predecessors(node):
                # Check edges from pred to node
                if self.graph.has_edge(pred, node):
                    for key, edge_data in self.graph[pred][node].items():
                        if key == RelationType.CAUSED_BY.value:
                            has_causes = True
                            dfs(pred, path + [pred], depth + 1)
            
            # Leaf node (root cause)
            if not has_causes:
                paths.append(path[:])
        
        dfs(error_id, [error_id], 0)
        return paths
    
    def find_synergistic_agents(self, agent_id: int, k: int = 5) -> List[Tuple[Entity, float]]:
        """
        Query 5: Agents that collaborate well together using PageRank.
        
        Returns: List of (agent_entity, synergy_score)
        """
        if not self.graph.has_node(agent_id):
            return []
        
        # Build collaboration subgraph (agents only)
        collab_graph = nx.Graph()
        for src, dst, data in self.graph.edges(data=True):
            if data.get('key') == RelationType.COLLABORATED_WITH.value:
                src_entity = self.get_entity(src)
                dst_entity = self.get_entity(dst)
                if src_entity and dst_entity and src_entity.type == EntityType.AGENT and dst_entity.type == EntityType.AGENT:
                    weight = data.get('confidence', 0.5)
                    collab_graph.add_edge(src, dst, weight=weight)
        
        if not collab_graph.has_node(agent_id):
            return []
        
        # Run PageRank with personalization (biased toward agent_id)
        try:
            pagerank = nx.pagerank(collab_graph, personalization={agent_id: 1.0}, weight='weight')
        except:
            return []
        
        # Sort by PageRank score (exclude self)
        scores = [(node, score) for node, score in pagerank.items() if node != agent_id]
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return [(self.get_entity(node), score) for node, score in scores[:k]]
    
    # ========== PATTERN EXTRACTION ==========
    
    def extract_action_sequences(self) -> List[Pattern]:
        """
        Query 7: Extract common action sequences (for automation patterns).
        
        Finds sequences connected by PRECEDED_BY relations with min occurrences.
        
        Note: PRECEDED_BY means "A PRECEDED_BY B" = "B happened before A", so
        edge A->B means B is the predecessor.
        """
        cursor = self.db.cursor()
        
        # Get all PRECEDED_BY relations with observed counts
        cursor.execute("""
            SELECT src_entity_id, dst_entity_id, observed_count
            FROM relations
            WHERE relation_type = 'preceded_by'
            ORDER BY created_at
        """)
        
        rows = cursor.fetchall()
        
        if not rows:
            return []
        
        # Build sequences using observed_count as pattern frequency
        # For action sequences, we'll use bigrams (pairs) as patterns
        bigrams = []
        for row in rows:
            # dst preceded src (dst happened first)
            bigram = (row['dst_entity_id'], row['src_entity_id'])
            count = row['observed_count']
            # Add bigram 'count' times to simulate observations
            for _ in range(count):
                bigrams.append(bigram)
        
        if not bigrams:
            return []
        
        # Count occurrences
        pattern_counts = Counter(bigrams)
        
        # Filter by threshold and create patterns
        patterns = []
        for seq, count in pattern_counts.items():
            if count >= self.MIN_PATTERN_OCCURRENCES:
                # Store pattern
                pattern_id = self.add_pattern(
                    pattern_type='action_sequence',
                    pattern_data=list(seq),
                    metadata={'count': count, 'alpha': count + 2, 'beta': 2}
                )
                
                pattern = Pattern(
                    id=pattern_id,
                    pattern_type='action_sequence',
                    pattern_data=list(seq),
                    occurrences=count,
                    confidence=count / len(bigrams) if bigrams else 0.0,
                    first_seen=time.time(),
                    last_seen=time.time(),
                    metadata={'count': count}
                )
                patterns.append(pattern)
        
        return patterns
    
    # ========== SYNC & LIFECYCLE ==========
    
    def _maybe_sync(self):
        """Check if sync threshold reached and sync if needed (Comet's event-driven design)"""
        if self._pending_updates >= self.SYNC_THRESHOLD:
            self._sync_networkx_to_sqlite()
            self._pending_updates = 0
    
    def _sync_from_db(self):
        """Load graph from SQLite into NetworkX (on startup)"""
        cursor = self.db.cursor()
        
        # Load nodes
        cursor.execute("SELECT id, type, name, properties FROM entities")
        for row in cursor.fetchall():
            props = json.loads(row['properties']) if row['properties'] else {}
            self.graph.add_node(row['id'], type=row['type'], name=row['name'], **props)
        
        # Load edges
        cursor.execute("SELECT src_entity_id, dst_entity_id, relation_type, confidence, metadata FROM relations")
        for row in cursor.fetchall():
            meta = json.loads(row['metadata']) if row['metadata'] else {}
            self.graph.add_edge(
                row['src_entity_id'],
                row['dst_entity_id'],
                key=row['relation_type'],
                confidence=row['confidence'],
                **meta
            )
    
    def _sync_networkx_to_sqlite(self):
        """Persist NetworkX changes to SQLite (not currently used - SQLite is source of truth)"""
        # Currently, we update SQLite directly on entity/relation changes
        # This method is a placeholder for future optimizations
        pass
    
    def _force_sync(self):
        """Force sync on shutdown (Comet's suggestion via atexit)"""
        if self._pending_updates > 0:
            self._sync_networkx_to_sqlite()
    
    def take_snapshot(self):
        """Take graph snapshot (Comet's debugging suggestion)"""
        cursor = self.db.cursor()
        
        # Count entities, relations, patterns
        cursor.execute("SELECT COUNT(*) FROM entities")
        entity_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM relations")
        relation_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM patterns")
        pattern_count = cursor.fetchone()[0]
        
        # Top entities by degree
        degrees = dict(self.graph.degree())
        top_entities = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:10]
        top_entity_names = [
            (self.get_entity(eid).name if self.get_entity(eid) else f"entity_{eid}", degree)
            for eid, degree in top_entities
        ]
        
        # Graph density
        density = nx.density(self.graph) if self.graph.number_of_nodes() > 0 else 0.0
        
        metadata = {
            'top_entities': top_entity_names,
            'graph_density': density
        }
        
        cursor.execute("""
            INSERT INTO graph_snapshots (snapshot_time, entity_count, relation_count, pattern_count, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (time.time(), entity_count, relation_count, pattern_count, json.dumps(metadata)))
        
        self.db.commit()
