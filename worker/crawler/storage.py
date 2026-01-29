"""Storage for crawled pages."""

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from worker.crawler.crawler import CrawlPage, CrawlResult

logger = structlog.get_logger(__name__)


def _serialize_datetime(obj: Any) -> Any:
    """JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


@dataclass
class StoredPage:
    """A page stored in the crawl storage."""

    page_id: str
    url: str
    final_url: str
    title: str | None
    html_hash: str
    html_size: int
    content_type: str | None
    status_code: int
    depth: int
    fetch_time_ms: int
    fetched_at: str  # ISO format
    links_found: int


@dataclass
class CrawlManifest:
    """Manifest for a stored crawl."""

    crawl_id: str
    domain: str
    start_url: str
    pages: list[StoredPage]
    urls_discovered: int
    urls_crawled: int
    urls_skipped: int
    urls_failed: int
    started_at: str
    completed_at: str
    duration_seconds: float
    robots_respected: bool
    max_depth_reached: int


class CrawlStorage:
    """Storage manager for crawled pages."""

    def __init__(self, base_path: Path | str):
        """
        Initialize storage.

        Args:
            base_path: Base directory for storing crawl data
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_crawl_dir(self, crawl_id: str) -> Path:
        """Get the directory for a specific crawl."""
        return self.base_path / crawl_id

    def _hash_content(self, content: str) -> str:
        """Create a hash of content for deduplication."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def _page_to_stored(self, page: CrawlPage, page_id: str) -> StoredPage:
        """Convert CrawlPage to StoredPage."""
        return StoredPage(
            page_id=page_id,
            url=page.url,
            final_url=page.final_url,
            title=page.title,
            html_hash=self._hash_content(page.html),
            html_size=len(page.html.encode("utf-8")),
            content_type=page.content_type,
            status_code=page.status_code,
            depth=page.depth,
            fetch_time_ms=page.fetch_time_ms,
            fetched_at=page.fetched_at.isoformat(),
            links_found=page.links_found,
        )

    def store_crawl(self, result: CrawlResult) -> str:
        """
        Store a crawl result.

        Args:
            result: The CrawlResult to store

        Returns:
            The crawl ID
        """
        crawl_id = str(uuid.uuid4())
        crawl_dir = self._get_crawl_dir(crawl_id)
        crawl_dir.mkdir(parents=True, exist_ok=True)

        # Create pages directory
        pages_dir = crawl_dir / "pages"
        pages_dir.mkdir(exist_ok=True)

        stored_pages: list[StoredPage] = []

        for i, page in enumerate(result.pages):
            page_id = f"page_{i:04d}"

            # Store HTML
            html_path = pages_dir / f"{page_id}.html"
            html_path.write_text(page.html, encoding="utf-8")

            # Create stored page record
            stored = self._page_to_stored(page, page_id)
            stored_pages.append(stored)

        # Create manifest
        manifest = CrawlManifest(
            crawl_id=crawl_id,
            domain=result.domain,
            start_url=result.start_url,
            pages=stored_pages,
            urls_discovered=result.urls_discovered,
            urls_crawled=result.urls_crawled,
            urls_skipped=result.urls_skipped,
            urls_failed=result.urls_failed,
            started_at=result.started_at.isoformat(),
            completed_at=result.completed_at.isoformat(),
            duration_seconds=result.duration_seconds,
            robots_respected=result.robots_respected,
            max_depth_reached=result.max_depth_reached,
        )

        # Store manifest
        manifest_path = crawl_dir / "manifest.json"
        manifest_dict = asdict(manifest)
        manifest_path.write_text(
            json.dumps(manifest_dict, indent=2, default=_serialize_datetime),
            encoding="utf-8",
        )

        logger.info(
            "crawl_stored",
            crawl_id=crawl_id,
            pages=len(stored_pages),
            path=str(crawl_dir),
        )

        return crawl_id

    def load_manifest(self, crawl_id: str) -> CrawlManifest | None:
        """
        Load a crawl manifest.

        Args:
            crawl_id: The crawl ID

        Returns:
            CrawlManifest or None if not found
        """
        manifest_path = self._get_crawl_dir(crawl_id) / "manifest.json"
        if not manifest_path.exists():
            return None

        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        # Convert pages list
        pages = [StoredPage(**p) for p in data.pop("pages")]

        return CrawlManifest(pages=pages, **data)

    def load_page_html(self, crawl_id: str, page_id: str) -> str | None:
        """
        Load HTML for a specific page.

        Args:
            crawl_id: The crawl ID
            page_id: The page ID

        Returns:
            HTML content or None if not found
        """
        html_path = self._get_crawl_dir(crawl_id) / "pages" / f"{page_id}.html"
        if not html_path.exists():
            return None

        return html_path.read_text(encoding="utf-8")

    def list_crawls(self) -> list[str]:
        """List all stored crawl IDs."""
        crawls = []
        for path in self.base_path.iterdir():
            if path.is_dir() and (path / "manifest.json").exists():
                crawls.append(path.name)
        return sorted(crawls)

    def delete_crawl(self, crawl_id: str) -> bool:
        """
        Delete a stored crawl.

        Args:
            crawl_id: The crawl ID to delete

        Returns:
            True if deleted, False if not found
        """
        crawl_dir = self._get_crawl_dir(crawl_id)
        if not crawl_dir.exists():
            return False

        import shutil

        shutil.rmtree(crawl_dir)

        logger.info("crawl_deleted", crawl_id=crawl_id)
        return True

    def get_total_size(self, crawl_id: str) -> int:
        """Get total storage size for a crawl in bytes."""
        crawl_dir = self._get_crawl_dir(crawl_id)
        if not crawl_dir.exists():
            return 0

        total = 0
        for path in crawl_dir.rglob("*"):
            if path.is_file():
                total += path.stat().st_size
        return total
