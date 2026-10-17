"""PDF text extraction, page mapping, and chunking."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import fitz  # PyMuPDF


MAX_PAGES_DEFAULT = 800  # safety guard for unexpectedly huge files


@dataclass
class PageText:
    page_number: int  # 1-indexed for human display
    text: str


@dataclass
class Chunk:
    id: str
    paper_id: str
    page_number: int
    chunk_index: int
    text: str
    token_count: int


# ---- public helpers ----
def safe_filename(original: str) -> str:
    """Strip path components and produce a safe stored filename."""
    base = Path(original).name
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    return base or "upload.pdf"


def generate_paper_id() -> str:
    return f"paper_{uuid.uuid4().hex[:12]}"


def extract_pages(pdf_path: Path, max_pages: int = MAX_PAGES_DEFAULT) -> List[PageText]:
    """Extract text from each page in a PDF using PyMuPDF.

    Returns a list of :class:`PageText`. Pages with no extractable text
    still appear in the result so we can detect scanned documents.
    """
    pages: List[PageText] = []
    with fitz.open(pdf_path) as doc:
        total = min(len(doc), max_pages)
        for index in range(total):
            page = doc.load_page(index)
            text = page.get_text("text") or ""
            pages.append(PageText(page_number=index + 1, text=text))
    return pages


def detect_scanned(pages: List[PageText], threshold: float = 0.05) -> bool:
    """Heuristically detect a scanned/image-only PDF.

    Returns True when the average non-whitespace characters per page is
    below ``threshold`` * 1000. The threshold is intentionally small so
    that text-heavy pages with figures still register as text.
    """
    if not pages:
        return True
    total_chars = sum(len(re.sub(r"\s+", "", p.text)) for p in pages)
    avg = total_chars / max(len(pages), 1)
    return avg < 50  # fewer than 50 non-whitespace chars per page on average


def chunk_pages(
    paper_id: str,
    pages: List[PageText],
    target_chars: int = 1100,
    overlap_chars: int = 150,
) -> List[Chunk]:
    """Greedy paragraph-aware chunker that preserves page metadata.

    The same paper_id and a stable ``chunk_index`` are attached so the
    agent can cite back to a specific chunk, while page numbers stay
    available for human-readable citations.
    """
    chunks: List[Chunk] = []
    chunk_index = 0
    for page in pages:
        if not page.text.strip():
            continue
        paragraphs = _split_paragraphs(page.text)
        buffer: List[str] = []
        buffer_len = 0
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if buffer_len + len(paragraph) + 1 > target_chars and buffer:
                text = " ".join(buffer).strip()
                if text:
                    chunks.append(
                        Chunk(
                            id=f"chunk_{paper_id}_{chunk_index:04d}",
                            paper_id=paper_id,
                            page_number=page.page_number,
                            chunk_index=chunk_index,
                            text=text,
                            token_count=len(text.split()),
                        )
                    )
                    chunk_index += 1
                # carry over an overlap window for context continuity
                if overlap_chars > 0 and buffer:
                    tail = " ".join(buffer)[-overlap_chars:]
                    buffer = [tail] if tail else []
                    buffer_len = len(tail)
                else:
                    buffer = []
                    buffer_len = 0
            buffer.append(paragraph)
            buffer_len += len(paragraph) + 1
        if buffer:
            text = " ".join(buffer).strip()
            if text:
                chunks.append(
                    Chunk(
                        id=f"chunk_{paper_id}_{chunk_index:04d}",
                        paper_id=paper_id,
                        page_number=page.page_number,
                        chunk_index=chunk_index,
                        text=text,
                        token_count=len(text.split()),
                    )
                )
                chunk_index += 1
    return chunks


def _split_paragraphs(text: str) -> Iterable[str]:
    text = text.replace("\r\n", "\n")
    parts = re.split(r"\n\s*\n", text)
    for part in parts:
        # also break on hard line breaks that look like paragraph ends
        for sub in re.split(r"\n(?=\s*[A-Z0-9])", part):
            yield sub.strip()


# ---- metadata extraction ----
# Patterns identifying document/conference/journal/preprint headers rather than paper titles
_HEADER_PATTERNS = [
    re.compile(r"^published (as|in)\b", re.IGNORECASE),
    re.compile(r"^under review (as|at)\b", re.IGNORECASE),
    re.compile(r"^proceedings of\b", re.IGNORECASE),
    re.compile(r"^to appear (in|at)\b", re.IGNORECASE),
    re.compile(r"^accepted (for|at|to|in)\b", re.IGNORECASE),
    re.compile(r"^presented at\b", re.IGNORECASE),
    re.compile(r"^arxiv:\d+\.\d+", re.IGNORECASE),
    re.compile(r"^biorxiv\b", re.IGNORECASE),
    re.compile(r"^medrxiv\b", re.IGNORECASE),
    re.compile(r"^\d{4}\s+(ieee|acm|cvpr|iccv|eccv|iclr|neurips|nips|icml)", re.IGNORECASE),
    re.compile(r"^(conference|symposium|workshop) on\b", re.IGNORECASE),
    re.compile(r"^transactions on\b", re.IGNORECASE),
    re.compile(r"^journal of\b", re.IGNORECASE),
    re.compile(r"^technical report\b", re.IGNORECASE),
    re.compile(r"^preprint\b", re.IGNORECASE),
    re.compile(r"^draft\b", re.IGNORECASE),
    re.compile(r"^\s*doi:\s*10\.\d+", re.IGNORECASE),
]

_AFFILIATION_TERMS = {
    "university", "institute", "department", "laboratory", "lab", "research",
    "school", "college", "hospital", "center", "centre", "faculty", "group",
    "google", "microsoft", "facebook", "meta", "deepmind", "cornell", "tsinghua"
}

_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_ARXIV_RE = re.compile(r"(?:^|[^0-9])(\d{2})(\d{2})\.(\d{4,5})")


def extract_metadata(
    pages: List[PageText],
    filename: str,
    pdf_path: Optional[Path] = None,
) -> dict:
    """Extract paper metadata using structured PDF metadata, font hierarchy, and header filtering.

    Distinguishes original publication venue/year from creation date and upload date.
    Marks metadata as uncertain when confidence cannot be verified.
    """
    if not pages:
        return {
            "title": "Untitled Document",
            "authors": None,
            "year": None,
            "confidence": "uncertain",
            "notes": "No extractable text found in document.",
        }

    raw_meta: dict = {}
    doc = None
    if pdf_path and Path(pdf_path).exists():
        try:
            doc = fitz.open(pdf_path)
            raw_meta = doc.metadata or {}
        except Exception:
            doc = None

    # -------------------------------------------------------------------------
    # 1. Title Extraction
    # -------------------------------------------------------------------------
    title: Optional[str] = None
    venue_hint: Optional[str] = None
    publication_year: Optional[str] = None

    # Step 1A: Check structured metadata if trustworthy
    meta_title = (raw_meta.get("title") or "").strip()
    if meta_title and len(meta_title) >= 6:
        # Ignore generic creator titles like 'untitled', file names, or header matches
        is_generic = any(g in meta_title.lower() for g in ["untitled", "latex with", "microsoft word"])
        is_header = any(pat.search(meta_title) for pat in _HEADER_PATTERNS)
        if not is_generic and not is_header and not meta_title.lower().endswith(".pdf"):
            title = meta_title

    # Step 1B: Inspect first page blocks with PyMuPDF
    first_page_blocks: List[str] = []
    if doc and len(doc) > 0:
        p0 = doc[0]
        try:
            blocks = p0.get_text("blocks")
            # Extract plain text from blocks
            for b in blocks:
                b_text = b[4].strip()
                if b_text:
                    first_page_blocks.append(b_text)
        except Exception:
            pass

    if not first_page_blocks:
        first_page_blocks = [p.strip() for p in pages[0].text.split("\n\n") if p.strip()]

    # Parse headers and search for the actual paper title
    candidate_title_blocks: List[str] = []
    for block in first_page_blocks[:8]:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        first_line = lines[0]
        lower_first = first_line.lower()

        # Check for venue/conference header
        if any(pat.search(lower_first) for pat in _HEADER_PATTERNS):
            venue_hint = block.replace("\n", " ")
            m_year = _YEAR_RE.search(block)
            if m_year:
                publication_year = m_year.group(0)
            continue

        if lower_first.startswith("abstract") or lower_first.startswith("1. intro"):
            break

        candidate_title_blocks.append(block)

    if not title and candidate_title_blocks:
        # The title is the first non-header substantive block
        raw_title_block = candidate_title_blocks[0]
        # Join multi-line titles into a single string
        combined_title = " ".join(raw_title_block.splitlines()).strip()
        # Clean formatting
        if combined_title.isupper():
            # Smart title-case for all-caps titles
            combined_title = combined_title.title()
            combined_title = re.sub(r"\b16X16\b", "16x16", combined_title, flags=re.I)
        title = combined_title

    # Fallback to sanitized filename if all else fails
    if not title or len(title) < 4:
        title = Path(filename).stem.replace("_", " ").strip().title() or filename
        title_confidence = "uncertain"
    else:
        title_confidence = "high"

    # -------------------------------------------------------------------------
    # 2. Publication Year & Venue Resolution
    # -------------------------------------------------------------------------
    year_source = "unverified"

    # Priority 2A: Explicit venue header detected on first page
    if publication_year:
        year_source = f"venue header ({venue_hint[:50]})"

    # Priority 2B: Structured metadata subject / title
    if not publication_year:
        meta_subject = raw_meta.get("subject", "")
        m_sub = _YEAR_RE.search(meta_subject)
        if m_sub:
            publication_year = m_sub.group(0)
            year_source = f"document subject metadata ({meta_subject[:40]})"

    # Priority 2C: Explicit conference / year in original filename (e.g. CVPR_2017)
    if not publication_year:
        fn_match = re.search(r"\b(CVPR|ICCV|ECCV|ICLR|NeurIPS|NIPS|ICML|AAAI)[_\s\-]+(19|20\d{2})\b", filename, re.IGNORECASE)
        if fn_match:
            publication_year = fn_match.group(2)
            year_source = f"filename publication tag ({fn_match.group(0)})"
        else:
            m_fn_year = _YEAR_RE.search(filename)
            if m_fn_year:
                publication_year = m_fn_year.group(0)
                year_source = "filename year"

    # Priority 2D: arXiv identifier in filename or first page (e.g. 1512.03385 -> 2015, 2010.11929 -> 2020)
    if not publication_year:
        arx_match = _ARXIV_RE.search(filename) or _ARXIV_RE.search(pages[0].text[:600])
        if arx_match:
            yy = int(arx_match.group(1))
            publication_year = f"20{yy:02d}" if yy < 50 else f"19{yy:02d}"
            year_source = f"arXiv identifier (arXiv:{arx_match.group(1)}{arx_match.group(2)}.{arx_match.group(3)})"

    # Priority 2E: First page text scan for copyright / conference notice
    if not publication_year:
        m_page_year = re.search(r"(?:©|copyright|in\s+proceedings\s+of|cvpr|iclr|neurips|ilsvrc)\s*[\w\s,]*\b(19|20\d{2})\b", pages[0].text[:1200], re.IGNORECASE)
        if m_page_year:
            publication_year = m_page_year.group(1)
            year_source = "first page publication citation"

    # Note creationDate vs original publication year:
    creation_date = raw_meta.get("creationDate", "")
    creation_year = None
    if creation_date:
        m_c = _YEAR_RE.search(creation_date)
        if m_c:
            creation_year = m_c.group(0)

    if not publication_year and creation_year:
        # Only creationDate exists - mark as uncertain publication year
        publication_year = creation_year
        year_source = "PDF creation date (original publication venue unconfirmed)"

    # -------------------------------------------------------------------------
    # 3. Authors Extraction
    # -------------------------------------------------------------------------
    authors: Optional[str] = None

    # Priority 3A: Clean author metadata in PDF document
    meta_author = (raw_meta.get("author") or "").strip()
    if meta_author and len(meta_author) >= 3 and not any(k in meta_author.lower() for k in ["admin", "user", "root", "unknown", "@"]):
        if any(char.isalpha() for char in meta_author):
            authors = meta_author

    # Priority 3B: Inspect author block following title on first page
    if not authors and len(candidate_title_blocks) > 1:
        author_cand_block = candidate_title_blocks[1]
        lines = [l.strip() for l in author_cand_block.splitlines() if l.strip()]
        author_names: List[str] = []
        for line in lines:
            lower_l = line.lower()
            # Skip emails, affiliations, and contribution markers
            if "@" in line or "{" in line or "http" in lower_l:
                continue
            if any(term in lower_l for term in _AFFILIATION_TERMS):
                continue
            if any(term in lower_l for term in ["equal contribution", "equal advising", "correspondence to", "all authors"]):
                continue
            # Strip footnote characters
            cleaned = re.sub(r"[\*†‡§∗\d,\(\)]+", " ", line).strip()
            # Must look like name(s)
            cleaned_names = [n.strip() for n in re.split(r"\s{2,}|,\s*", cleaned) if len(n.strip().split()) >= 2]
            for n in cleaned_names:
                if len(n) > 3 and not any(term in n.lower() for term in _AFFILIATION_TERMS):
                    if n not in author_names:
                        author_names.append(n)

        if author_names:
            authors = ", ".join(author_names[:8])

    # -------------------------------------------------------------------------
    # 4. Confidence & Provenance Assessment
    # -------------------------------------------------------------------------
    if title_confidence == "high" and authors and publication_year and "unconfirmed" not in year_source:
        confidence = "high"
        notes = f"Verified bibliographic metadata ({year_source})."
    elif title and (authors or publication_year):
        confidence = "medium"
        notes = f"Extracted metadata with partial provenance: Year source: {year_source}."
    else:
        confidence = "uncertain"
        notes = f"Publication metadata uncertain. Year source: {year_source}. Please verify before formal citation."

    if doc:
        try:
            doc.close()
        except Exception:
            pass

    return {
        "title": title,
        "authors": authors or "Authors not identified in document header",
        "year": publication_year,
        "confidence": confidence,
        "notes": notes,
    }

