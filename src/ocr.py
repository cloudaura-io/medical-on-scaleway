"""
OCR via Pixtral vision model on Scaleway Generative APIs.

Supports single images (bytes) and multi-page PDFs.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Union

from src.config import get_generative_client, VISION_MODEL

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

Return ONLY the extracted text — no commentary.
"""

# ---------------------------------------------------------------------------
# Single-image extraction
# ---------------------------------------------------------------------------

def extract_text_from_image(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Send an image to Pixtral and return the extracted text.

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
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{b64}"

    client = get_generative_client()
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
                        "text": "Extract all text from this medical document image.",
                    },
                ],
            },
        ],
        temperature=0.0,
        max_tokens=4096,
    )

    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Multi-page PDF processing
# ---------------------------------------------------------------------------

def process_pdf(pdf_path: str, dpi: int = 200) -> list[dict]:
    """Convert each page of a PDF to an image and extract text via Pixtral.

    Requires the ``pdf2image`` library (and ``poppler-utils`` system package).

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.
    dpi:
        Resolution for rasterisation.  200 is a good balance of quality
        and token cost.

    Returns
    -------
    list[dict]
        Each entry: ``{"page": int, "text": str}``.
    """
    from pdf2image import convert_from_path
    import io

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    images = convert_from_path(str(path), dpi=dpi)

    results: list[dict] = []
    for page_num, image in enumerate(images, 1):
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        page_bytes = buf.getvalue()

        text = extract_text_from_image(page_bytes, mime_type="image/png")
        results.append({"page": page_num, "text": text})

    return results
