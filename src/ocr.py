"""
OCR via Mistral Small 3.2 vision on Scaleway Generative APIs.

Supports single images (bytes) and multi-page PDFs.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from src.config import VISION_MODEL, get_generative_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_OCR_SYSTEM_PROMPT = """\
You are a medical document OCR system.  Extract ALL text from the provided
image exactly as it appears.  Preserve:
- Headings, section labels, and list structure.
- Table layout (use Markdown tables).
- Numbers, units, dates, and dosages verbatim.
- Any handwritten text you can reasonably decipher (flag uncertain words
  with [unclear]).

Return ONLY the extracted text - no commentary.
"""

# ---------------------------------------------------------------------------
# Single-image extraction
# ---------------------------------------------------------------------------


def extract_text_from_image(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Send an image to the vision model and return the extracted text.

    Parameters
    ----------
    image_bytes:
        Raw bytes of the image (PNG, JPEG, TIFF, etc.).
    mime_type:
        MIME type of the image.  Defaults to ``image/png``.

    Returns
    -------
    str
        The full text extracted from the image.
    """
    logger.info("extract_text_from_image called, image_size=%d bytes, mime_type=%s", len(image_bytes), mime_type)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"
    logger.debug("Base64-encoded image length=%d chars", len(b64))

    client = get_generative_client()
    logger.debug("Sending OCR request to model=%s, max_tokens=16384", VISION_MODEL)
    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {"role": "system", "content": _OCR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                    {
                        "type": "text",
                        "text": "Extract all text from this image.",
                    },
                ],
            },
        ],
        temperature=0.0,
        max_tokens=16384,
    )

    text = response.choices[0].message.content
    logger.info("extract_text_from_image completed, extracted_text_length=%d chars", len(text) if text else 0)
    return text


# ---------------------------------------------------------------------------
# Multi-page PDF processing
# ---------------------------------------------------------------------------


def process_pdf(pdf_path: str, dpi: int = 300) -> list[dict]:
    """Convert each page of a PDF to an image and extract text via vision model.

    Requires the ``pdf2image`` library (and ``poppler-utils`` system package).

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.
    dpi:
        Resolution for rasterisation.  300 gives good accuracy on dense
        lab-result tables; lower values may lose small-font numerics.

    Returns
    -------
    list[dict]
        Each entry: ``{"page": int, "text": str}``.
    """
    import io

    from pdf2image import convert_from_path

    logger.info("process_pdf called, pdf_path=%s, dpi=%d", pdf_path, dpi)
    path = Path(pdf_path)
    if not path.exists():
        logger.error("PDF not found: %s", pdf_path)
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    images = convert_from_path(str(path), dpi=dpi)
    logger.info("PDF rasterised into %d page(s)", len(images))

    results: list[dict] = []
    for page_num, image in enumerate(images, 1):
        logger.debug("Processing page %d/%d", page_num, len(images))
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        page_bytes = buf.getvalue()

        text = extract_text_from_image(page_bytes, mime_type="image/png")
        results.append({"page": page_num, "text": text})

    logger.info("process_pdf completed, pages_processed=%d", len(results))
    return results
