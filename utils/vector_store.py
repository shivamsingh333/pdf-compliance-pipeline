"""
Vector Store — RAG Compliance Engine
Stores and retrieves compliance rules using FAISS + ChromaDB.
Uses sentence-transformers to convert rule text into vectors.
"""

import os
import json
import uuid
from datetime import datetime
from typing import List, Dict

# ─── Embedding Model ──────────────────────────────────────────────────────────
_embedder = None

def get_embedder():
    """Lazy-load the sentence embedding model (downloads once, cached after)."""
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def embed_text(text: str) -> list:
    """Convert a rule string into a 384-dim vector."""
    model = get_embedder()
    return model.encode([text])[0].tolist()


# ─── ChromaDB Store ───────────────────────────────────────────────────────────
_chroma_client = None
_chroma_collection = None

def get_chroma_collection():
    """Get or create the ChromaDB collection for compliance rules."""
    global _chroma_client, _chroma_collection
    if _chroma_collection is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path="./chroma_db")
        _chroma_collection = _chroma_client.get_or_create_collection(
            name="compliance_rules",
            metadata={"description": "Dynamic compliance rules for PDF scanning"}
        )
    return _chroma_collection


def save_rule_to_chroma(rule_id: str, rule_text: str, category: str, metadata: dict = None):
    """Save a compliance rule to ChromaDB with its embedding."""
    collection = get_chroma_collection()
    embedding = embed_text(rule_text)
    meta = {
        "category": category,
        "created_at": datetime.now().isoformat(),
        "rule_text": rule_text,
        **(metadata or {})
    }
    collection.upsert(
        ids=[rule_id],
        embeddings=[embedding],
        documents=[rule_text],
        metadatas=[meta]
    )


def delete_rule_from_chroma(rule_id: str):
    """Delete a rule from ChromaDB by its ID."""
    collection = get_chroma_collection()
    try:
        collection.delete(ids=[rule_id])
    except Exception:
        pass


def retrieve_rules_from_chroma(query_text: str, top_k: int = 5) -> List[Dict]:
    """
    Retrieve the most relevant compliance rules for a given document text.
    Returns top_k rules sorted by similarity.
    """
    collection = get_chroma_collection()
    if collection.count() == 0:
        return []

    query_embedding = embed_text(query_text)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"]
    )

    rules = []
    for i, doc in enumerate(results["documents"][0]):
        rules.append({
            "id": results["ids"][0][i],
            "text": doc,
            "category": results["metadatas"][0][i].get("category", "General"),
            "similarity": round(1 - results["distances"][0][i], 3),
            "created_at": results["metadatas"][0][i].get("created_at", "")
        })
    return rules


def get_all_rules_from_chroma() -> List[Dict]:
    """Fetch all stored rules from ChromaDB."""
    collection = get_chroma_collection()
    if collection.count() == 0:
        return []
    results = collection.get(include=["documents", "metadatas"])
    rules = []
    for i, doc in enumerate(results["documents"]):
        rules.append({
            "id": results["ids"][i],
            "text": doc,
            "category": results["metadatas"][i].get("category", "General"),
            "created_at": results["metadatas"][i].get("created_at", "")
        })
    return rules


# ─── FAISS Store (fast local similarity search) ───────────────────────────────
_faiss_index = None
_faiss_rule_map = {}   # maps integer index → rule dict
_faiss_counter = 0

def get_faiss_index():
    """Get or create an in-memory FAISS index (384 dimensions)."""
    global _faiss_index
    if _faiss_index is None:
        import faiss
        _faiss_index = faiss.IndexFlatL2(384)
    return _faiss_index


def add_rule_to_faiss(rule_id: str, rule_text: str, category: str):
    """Add a rule vector to the FAISS index."""
    global _faiss_counter
    import numpy as np
    index = get_faiss_index()
    embedding = embed_text(rule_text)
    vec = np.array([embedding], dtype="float32")
    index.add(vec)
    _faiss_rule_map[_faiss_counter] = {
        "id": rule_id,
        "text": rule_text,
        "category": category
    }
    _faiss_counter += 1


def retrieve_rules_from_faiss(query_text: str, top_k: int = 5) -> List[Dict]:
    """Retrieve top-k most similar rules from FAISS index."""
    import numpy as np
    index = get_faiss_index()
    if index.ntotal == 0:
        return []

    query_vec = np.array([embed_text(query_text)], dtype="float32")
    k = min(top_k, index.ntotal)
    distances, indices = index.search(query_vec, k)

    rules = []
    for i, idx in enumerate(indices[0]):
        if idx in _faiss_rule_map:
            rule = dict(_faiss_rule_map[idx])
            rule["distance"] = round(float(distances[0][i]), 4)
            rules.append(rule)
    return rules


def rebuild_faiss_from_chroma():
    """
    Rebuild the FAISS in-memory index from all rules in ChromaDB.
    Call this on app startup to keep FAISS in sync.
    """
    global _faiss_index, _faiss_rule_map, _faiss_counter
    import faiss
    import numpy as np

    _faiss_index = faiss.IndexFlatL2(384)
    _faiss_rule_map = {}
    _faiss_counter = 0

    all_rules = get_all_rules_from_chroma()
    for rule in all_rules:
        add_rule_to_faiss(rule["id"], rule["text"], rule["category"])


# ─── High-Level API (used by pipeline and UI) ────────────────────────────────
def add_compliance_rule(rule_text: str, category: str = "General") -> str:
    """
    Add a new compliance rule to both ChromaDB and FAISS.
    Returns the new rule's ID.
    """
    rule_id = str(uuid.uuid4())[:8]
    save_rule_to_chroma(rule_id, rule_text, category)
    add_rule_to_faiss(rule_id, rule_text, category)
    return rule_id


def delete_compliance_rule(rule_id: str):
    """Delete a rule from ChromaDB (FAISS rebuild happens on next startup)."""
    delete_rule_from_chroma(rule_id)


def retrieve_relevant_rules(document_text: str, top_k: int = 5) -> str:
    """
    Main retrieval function used by the LangGraph pipeline.
    Returns a formatted string of the most relevant rules
    ready to be injected into the AI prompt.
    """
    rules = retrieve_rules_from_chroma(document_text[:1000], top_k=top_k)

    if not rules:
        return _get_default_rules_text()

    formatted = "COMPLIANCE RULES TO ENFORCE (retrieved from rule database):\n"
    for i, rule in enumerate(rules, 1):
        formatted += f"\n{i}. [{rule['category']}] {rule['text']}"
    return formatted


def _get_default_rules_text() -> str:
    """Fallback rules if Vector DB is empty."""
    return """COMPLIANCE RULES TO ENFORCE (default rules):
1. [PII] Flag any personal information: email addresses, phone numbers, Aadhaar numbers, PAN card numbers, SSN, credit card numbers
2. [Confidential] Flag confidential business info: trade secrets, internal financials, API keys, passwords, IP details
3. [Encoding] Check UTF-8 encoding consistency (English only supported)
4. [Abusive] Flag abusive, offensive, or unlawful content"""


def seed_default_rules():
    """
    Seed the Vector DB with default compliance rules on first run.
    Only adds rules if the DB is empty.
    """
    collection = get_chroma_collection()
    if collection.count() > 0:
        return  # already seeded

    default_rules = [
        ("Never allow PII: email addresses, phone numbers, Aadhaar numbers, PAN card numbers, SSN, credit card numbers", "PII"),
        ("Never allow confidential business information: trade secrets, internal financial data, unreleased product details", "Confidential"),
        ("Never allow API keys, passwords, tokens, or authentication credentials in documents", "Confidential"),
        ("Flag abusive, offensive, threatening, or unlawful content including hate speech", "Abusive"),
        ("Check for consistent UTF-8 encoding — only English language text is supported", "Encoding"),
        ("Never allow internal employee data: salaries, performance reviews, HR records", "PII"),
        ("Flag any sensitive government identifiers: passport numbers, driving licence numbers, voter ID", "PII"),
    ]

    for rule_text, category in default_rules:
        add_compliance_rule(rule_text, category)