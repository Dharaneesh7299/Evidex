"""Deterministic keyword-based retrieval.

A lightweight BM25-style scorer with a TF component and length
normalisation. The retrieval layer is intentionally simple: it must
work without an embedding service and always return the original passage
text for citation validation downstream.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from app.db.database import Database


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "were",
    "with", "we", "our", "their", "they", "but", "not", "can", "may", "these",
    "those", "such", "into", "than", "then", "so", "if", "do", "does", "did",
    "been", "being", "more", "most", "other", "some", "any", "all", "each",
}


def tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOPWORDS and len(t) > 1]


@dataclass
class RetrievalHit:
    chunk_id: str
    paper_id: str
    page_number: int
    text: str
    score: float
    matched_terms: List[str]


class Retriever:
    """Builds a per-paper BM25 index from the database ``chunks`` table."""

    def __init__(self, db: Database, paper_id: str):
        self.db = db
        self.paper_id = paper_id
        self.chunks = db.get_chunks(paper_id)
        self._tokenised: List[List[str]] = [tokenize(c["text"]) for c in self.chunks]
        self._doc_freq: Dict[str, int] = Counter()
        self._doc_len: List[int] = [len(toks) for toks in self._tokenised]
        for toks in self._tokenised:
            for term in set(toks):
                self._doc_freq[term] += 1
        self.avgdl = sum(self._doc_len) / max(len(self._doc_len), 1)
        self.total_docs = max(len(self.chunks), 1)

    def search(self, query: str, top_k: int = 5) -> List[RetrievalHit]:
        if not query.strip():
            return []
        query_terms = tokenize(query)
        if not query_terms:
            return []
        scores: List[Tuple[int, float, List[str]]] = []
        for idx, doc_terms in enumerate(self._tokenised):
            if not doc_terms:
                continue
            term_counts = Counter(doc_terms)
            matched: List[str] = []
            score = 0.0
            for term in query_terms:
                if term not in term_counts:
                    continue
                matched.append(term)
                df = self._doc_freq.get(term, 1)
                idf = math.log(1 + (self.total_docs - df + 0.5) / (df + 0.5))
                tf = term_counts[term]
                denom = tf + 1.5 * (1 - 0.75 + 0.75 * self._doc_len[idx] / max(self.avgdl, 1))
                score += idf * (tf * (1.5 + 1)) / max(denom, 1e-6)
            if score > 0:
                scores.append((idx, score, matched))
        scores.sort(key=lambda t: t[1], reverse=True)
        hits: List[RetrievalHit] = []
        for idx, score, matched in scores[:top_k]:
            chunk = self.chunks[idx]
            hits.append(
                RetrievalHit(
                    chunk_id=chunk["id"],
                    paper_id=self.paper_id,
                    page_number=chunk["page_number"],
                    text=chunk["text"],
                    score=score,
                    matched_terms=matched,
                )
            )
        return hits


def multi_paper_search(
    db: Database,
    paper_ids: Sequence[str],
    query: str,
    top_k_per_paper: int = 3,
) -> List[RetrievalHit]:
    """Run retrieval across multiple papers and return merged results."""

    all_hits: List[RetrievalHit] = []
    for pid in paper_ids:
        retriever = Retriever(db, pid)
        all_hits.extend(retriever.search(query, top_k=top_k_per_paper))
    all_hits.sort(key=lambda h: h.score, reverse=True)
    return all_hits


def search_across_papers(
    db: Database,
    paper_ids: Sequence[str],
    query: str,
    top_k: int = 8,
) -> List[RetrievalHit]:
    return multi_paper_search(db, paper_ids, query, top_k_per_paper=max(3, top_k // max(len(paper_ids), 1)))


def validate_evidence_reference(
    db: Database,
    paper_id: str,
    page_number: int,
    passage: str,
    *,
    min_overlap: float = 0.35,
) -> Tuple[bool, str]:
    """Confirm that ``passage`` actually appears in the paper's page text.

    Uses a character n-gram overlap heuristic so that minor whitespace
    differences do not cause false negatives. The original page text is
    always returned untouched for downstream display.
    """
    page_text = db.get_page_text(paper_id, page_number)
    if not page_text:
        return False, "No text extracted from the cited page."
    norm_passage = _normalise(passage)
    norm_page = _normalise(page_text)
    if not norm_passage:
        return False, "Empty passage."
    if norm_passage in norm_page:
        return True, "Exact substring match."
    grams = _ngrams(norm_passage, 6)
    if not grams:
        return False, "Passage too short to validate."
    hits = sum(1 for g in grams if g in norm_page)
    overlap = hits / max(len(grams), 1)
    if overlap >= min_overlap:
        return True, f"n-gram overlap {overlap:.2f} >= {min_overlap:.2f}"
    return False, f"Insufficient overlap ({overlap:.2f}) with extracted page text."


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _ngrams(text: str, n: int) -> List[str]:
    if len(text) < n:
        return [text] if text else []
    return [text[i : i + n] for i in range(len(text) - n + 1)]
