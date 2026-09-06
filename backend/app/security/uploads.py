"""CV upload validation and text extraction.

A CV is the most sensitive thing this product touches, and an upload endpoint
that accepts arbitrary bytes and runs a parser over them is the most exposed
thing it offers. So validation is layered and fails closed:

* size checked while streaming, not after buffering - otherwise the limit is
  enforced only once the machine has already accepted the memory cost;
* extension AND declared content type AND magic bytes must agree, because any
  one of the three is trivially forged;
* PDFs are opened with a page and size ceiling, and an encrypted PDF is
  rejected rather than brute-forced with an empty password;
* the extracted text goes straight to :class:`~app.security.guard.Provenance`
  ``UPLOADED_FILE``, which fails closed on injection.

Filenames from the client are never used as paths. Storage names are random.
"""

from __future__ import annotations

import io
import logging
import secrets
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.logging_config import Event, log_event, redact_text

logger = logging.getLogger(__name__)

#: Content types we accept, with their permitted extensions and magic prefixes.
#: DOCX is deliberately absent: it is a ZIP container, and unpacking untrusted
#: archives to read a CV is a materially larger attack surface than this MVP
#: needs. The paste-text path covers those users at zero risk.
ALLOWED: dict[str, tuple[frozenset[str], tuple[bytes, ...]]] = {
    "application/pdf": (frozenset({".pdf"}), (b"%PDF-",)),
    "text/plain": (frozenset({".txt", ".md"}), ()),
    "text/markdown": (frozenset({".md", ".txt"}), ()),
}

MAX_PDF_PAGES = 30
MIN_USEFUL_CHARS = 120


class UploadRejectedError(ValueError):
    """Raised with a message intended to be shown to the user verbatim."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class ValidatedUpload:
    original_filename: str
    #: Random, generated here. The client's filename never reaches the filesystem.
    storage_name: str
    content_type: str
    size_bytes: int
    data: bytes


def _safe_display_name(raw: str) -> str:
    """A filename safe to store and render. Not used as a path component."""
    cleaned = unicodedata.normalize("NFKC", raw).replace("\x00", "")
    cleaned = cleaned.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(c for c in cleaned if c.isprintable())
    return (cleaned or "upload")[:200]


def validate_upload(
    *,
    filename: str,
    declared_type: str,
    data: bytes,
    max_bytes: int,
) -> ValidatedUpload:
    """Reject anything that is not plausibly a CV, before any parser runs."""
    if not data:
        raise UploadRejectedError("That file is empty.", reason="empty")
    if len(data) > max_bytes:
        raise UploadRejectedError(
            f"That file is larger than the {max_bytes // 1_000_000} MB limit.",
            reason="too_large",
        )

    normalised_type = (declared_type or "").split(";")[0].strip().lower()
    if normalised_type not in ALLOWED:
        raise UploadRejectedError(
            "Please upload a PDF or a plain-text file, or paste your CV as text instead.",
            reason="content_type",
        )

    extensions, magic = ALLOWED[normalised_type]
    display = _safe_display_name(filename)
    suffix = Path(display).suffix.lower()
    if suffix and suffix not in extensions:
        raise UploadRejectedError(
            f"The file extension {suffix} does not match its declared type.",
            reason="extension_mismatch",
        )
    if magic and not any(data.startswith(prefix) for prefix in magic):
        # The declared type said PDF but the bytes disagree. This is the check
        # that a renamed executable fails.
        raise UploadRejectedError(
            "That file does not look like the type it claims to be.",
            reason="magic_mismatch",
        )
    if normalised_type.startswith("text/"):
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise UploadRejectedError(
                "That text file is not valid UTF-8.", reason="encoding"
            ) from error

    upload = ValidatedUpload(
        original_filename=display,
        storage_name=f"{secrets.token_hex(16)}{suffix or '.bin'}",
        content_type=normalised_type,
        size_bytes=len(data),
        data=data,
    )
    log_event(
        logger,
        Event.CV_UPLOAD_ACCEPTED,
        "upload passed validation",
        content_type=normalised_type,
        size_bytes=len(data),
    )
    return upload


def extract_text(upload: ValidatedUpload) -> str:
    """Pull plain text out of a validated upload.

    Returns text only; no images, no embedded files, no JavaScript, and no
    following of any link the document contains.
    """
    if upload.content_type.startswith("text/"):
        text = upload.data.decode("utf-8", errors="replace")
    else:
        text = _extract_pdf_text(upload.data)

    text = text.strip()
    if len(text) < MIN_USEFUL_CHARS:
        raise UploadRejectedError(
            "We could not read enough text from that file - it may be a scan or "
            "an image-only PDF. Please paste your CV as text instead.",
            reason="no_text",
        )
    log_event(
        logger,
        Event.CV_EXTRACTION_COMPLETED,
        "extracted text from upload",
        **redact_text(text),
    )
    return text


def _extract_pdf_text(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
    except (PdfReadError, ValueError, OSError) as error:
        raise UploadRejectedError(
            "That PDF could not be opened. Please paste your CV as text instead.",
            reason="pdf_unreadable",
        ) from error

    if reader.is_encrypted:
        # Do not attempt an empty-password decrypt. If the user encrypted their
        # CV, silently working around that is not our call to make.
        raise UploadRejectedError(
            "That PDF is password-protected. Please upload an unprotected copy "
            "or paste your CV as text.",
            reason="pdf_encrypted",
        )

    pages = reader.pages[:MAX_PDF_PAGES]
    parts: list[str] = []
    for page in pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # a single malformed page must not lose the whole CV
            logger.warning("could not extract text from one PDF page")
    return "\n\n".join(parts)


def store(upload: ValidatedUpload, directory: Path) -> Path:
    """Write the file under its generated name, never the client's.

    The path is constructed from a random hex token, so a filename containing
    ``../`` or a null byte cannot escape the directory - the client's name is
    only ever stored as a display string.
    """
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / upload.storage_name
    destination.write_bytes(upload.data)
    return destination


def delete_stored(path: Path | None) -> bool:
    """Remove a stored CV. Idempotent - a missing file is a success, not an error."""
    if path is None:
        return True
    try:
        path.unlink(missing_ok=True)
    except OSError:
        logger.warning("could not delete stored upload", exc_info=True)
        return False
    return True
