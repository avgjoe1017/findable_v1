"""BM25 lexical search implementation."""

import math
import re
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class BM25Config:
    """Configuration for BM25 index."""

    k1: float = 1.5  # Term frequency saturation
    b: float = 0.75  # Document length normalization
    min_token_length: int = 2  # Minimum token length to index
    lowercase: bool = True  # Lowercase tokens


@dataclass
class BM25Document:
    """A document in the BM25 index."""

    doc_id: str
    content: str
    tokens: list[str] = field(default_factory=list)
    token_count: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class BM25Result:
    """Result from BM25 search."""

    doc_id: str
    score: float
    content: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "doc_id": self.doc_id,
            "score": self.score,
            "content": self.content,
            "metadata": self.metadata,
        }


# Simple tokenization pattern
TOKEN_PATTERN = re.compile(r"\b\w+\b")


def tokenize(text: str, config: BM25Config) -> list[str]:
    """
    Tokenize text for BM25 indexing.

    Args:
        text: Text to tokenize
        config: BM25 configuration

    Returns:
        List of tokens
    """
    if config.lowercase:
        text = text.lower()

    tokens = TOKEN_PATTERN.findall(text)

    # Filter by minimum length
    tokens = [t for t in tokens if len(t) >= config.min_token_length]

    return tokens


class BM25Index:
    """
    BM25 (Best Matching 25) index for lexical search.

    BM25 is a bag-of-words ranking function that scores documents
    based on term frequency and inverse document frequency.
    """

    def __init__(self, config: BM25Config | None = None):
        self.config = config or BM25Config()

        # Document storage
        self._documents: dict[str, BM25Document] = {}

        # Inverted index: token -> list of (doc_id, term_freq)
        self._inverted_index: dict[str, list[tuple[str, int]]] = {}

        # Document frequencies: token -> number of docs containing token
        self._doc_freqs: dict[str, int] = {}

        # Statistics
        self._total_docs: int = 0
        self._avg_doc_length: float = 0.0
        self._total_tokens: int = 0

    @property
    def document_count(self) -> int:
        """Number of documents in index."""
        return self._total_docs

    @property
    def avg_document_length(self) -> float:
        """Average document length in tokens."""
        return self._avg_doc_length

    def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        """
        Add a document to the index.

        Args:
            doc_id: Unique document identifier
            content: Document text content
            metadata: Optional metadata
        """
        # Tokenize
        tokens = tokenize(content, self.config)
        token_counts = Counter(tokens)

        # Create document
        doc = BM25Document(
            doc_id=doc_id,
            content=content,
            tokens=tokens,
            token_count=len(tokens),
            metadata=metadata or {},
        )

        # Remove old version if exists
        if doc_id in self._documents:
            self.remove_document(doc_id)

        # Store document
        self._documents[doc_id] = doc

        # Update inverted index
        for token, freq in token_counts.items():
            if token not in self._inverted_index:
                self._inverted_index[token] = []
                self._doc_freqs[token] = 0

            self._inverted_index[token].append((doc_id, freq))
            self._doc_freqs[token] += 1

        # Update statistics
        self._total_docs += 1
        self._total_tokens += len(tokens)
        self._avg_doc_length = self._total_tokens / self._total_docs

    def add_documents(
        self,
        documents: list[dict],
    ) -> None:
        """
        Add multiple documents to the index.

        Args:
            documents: List of dicts with 'doc_id', 'content', and optional 'metadata'
        """
        for doc in documents:
            self.add_document(
                doc_id=doc["doc_id"],
                content=doc["content"],
                metadata=doc.get("metadata"),
            )

    def remove_document(self, doc_id: str) -> bool:
        """
        Remove a document from the index.

        Args:
            doc_id: Document ID to remove

        Returns:
            True if removed, False if not found
        """
        if doc_id not in self._documents:
            return False

        doc = self._documents[doc_id]

        # Update inverted index
        token_counts = Counter(doc.tokens)
        for token, _freq in token_counts.items():
            if token in self._inverted_index:
                self._inverted_index[token] = [
                    (did, f) for did, f in self._inverted_index[token] if did != doc_id
                ]
                self._doc_freqs[token] -= 1

                # Clean up empty entries
                if not self._inverted_index[token]:
                    del self._inverted_index[token]
                    del self._doc_freqs[token]

        # Update statistics
        self._total_docs -= 1
        self._total_tokens -= doc.token_count
        self._avg_doc_length = (
            self._total_tokens / self._total_docs if self._total_docs > 0 else 0.0
        )

        # Remove document
        del self._documents[doc_id]

        return True

    def search(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[BM25Result]:
        """
        Search the index using BM25 scoring.

        Args:
            query: Search query
            limit: Maximum results to return
            min_score: Minimum score threshold

        Returns:
            List of BM25Result objects
        """
        if self._total_docs == 0:
            return []

        # Tokenize query
        query_tokens = tokenize(query, self.config)

        if not query_tokens:
            return []

        # Calculate scores for each document
        scores: dict[str, float] = {}

        for token in query_tokens:
            if token not in self._inverted_index:
                continue

            # IDF: log((N - df + 0.5) / (df + 0.5))
            df = self._doc_freqs[token]
            idf = math.log((self._total_docs - df + 0.5) / (df + 0.5) + 1.0)

            # Score each document containing this token
            for doc_id, tf in self._inverted_index[token]:
                doc = self._documents[doc_id]
                doc_length = doc.token_count

                # BM25 term score
                # (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl/avgdl))
                numerator = tf * (self.config.k1 + 1)
                denominator = tf + self.config.k1 * (
                    1 - self.config.b + self.config.b * doc_length / self._avg_doc_length
                )
                term_score = idf * numerator / denominator

                if doc_id not in scores:
                    scores[doc_id] = 0.0
                scores[doc_id] += term_score

        # Sort by score
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        # Build results
        results: list[BM25Result] = []
        for doc_id, score in sorted_docs[:limit]:
            if score < min_score:
                continue

            doc = self._documents[doc_id]
            results.append(
                BM25Result(
                    doc_id=doc_id,
                    score=score,
                    content=doc.content,
                    metadata=doc.metadata,
                )
            )

        return results

    def get_document(self, doc_id: str) -> BM25Document | None:
        """Get a document by ID."""
        return self._documents.get(doc_id)

    def clear(self) -> None:
        """Clear the entire index."""
        self._documents.clear()
        self._inverted_index.clear()
        self._doc_freqs.clear()
        self._total_docs = 0
        self._avg_doc_length = 0.0
        self._total_tokens = 0

    def get_stats(self) -> dict:
        """Get index statistics."""
        return {
            "total_documents": self._total_docs,
            "total_tokens": self._total_tokens,
            "avg_document_length": round(self._avg_doc_length, 2),
            "vocabulary_size": len(self._inverted_index),
        }
