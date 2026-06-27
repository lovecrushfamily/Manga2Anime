from __future__ import annotations

from pathlib import Path
from io import BytesIO
from typing import Iterable

from PIL import Image, ImageOps
import pypdfium2 as pdfium

from manga2anime.models import PageImage


SUPPORTED_IMAGES = {".png", ".jpg", ".jpeg", ".webp"}


def load_chapter_uploads(uploaded_files: Iterable, output_dir: Path, max_pages: int) -> list[PageImage]:
    output_dir.mkdir(parents=True, exist_ok=True)
    uploaded = list(uploaded_files)
    if not uploaded:
        raise ValueError("No uploaded files.")

    pdfs = [file for file in uploaded if Path(file.name).suffix.lower() == ".pdf"]
    if len(pdfs) > 1 or (pdfs and len(uploaded) > 1):
        raise ValueError("Upload either one PDF or multiple page images, not both.")

    if pdfs:
        return _load_pdf(pdfs[0], output_dir, max_pages)
    return _load_images(uploaded, output_dir, max_pages)


def _load_pdf(uploaded_file, output_dir: Path, max_pages: int) -> list[PageImage]:
    pdf_path = output_dir / "chapter.pdf"
    pdf_path.write_bytes(_upload_bytes(uploaded_file))

    pages: list[PageImage] = []
    document = pdfium.PdfDocument(str(pdf_path))
    for index in range(min(len(document), max_pages)):
        bitmap = document[index].render(scale=2.0)
        image = bitmap.to_pil()
        page_path = output_dir / f"page_{index + 1:03d}.png"
        _save_clean_page(image, page_path)
        pages.append(_page_image(index + 1, page_path))
    return pages


def _load_images(uploaded_files: list, output_dir: Path, max_pages: int) -> list[PageImage]:
    pages: list[PageImage] = []
    for index, uploaded_file in enumerate(sorted(uploaded_files, key=lambda item: item.name), start=1):
        if index > max_pages:
            break
        suffix = Path(uploaded_file.name).suffix.lower()
        if suffix not in SUPPORTED_IMAGES:
            continue
        image = Image.open(BytesIO(_upload_bytes(uploaded_file))).convert("RGB")
        page_path = output_dir / f"page_{index:03d}.png"
        _save_clean_page(image, page_path)
        pages.append(_page_image(index, page_path))
    if not pages:
        raise ValueError("No supported image pages found.")
    return pages


def _save_clean_page(image: Image.Image, path: Path) -> None:
    image = ImageOps.exif_transpose(image).convert("L")
    image.thumbnail((1600, 2400), Image.Resampling.LANCZOS)
    ImageOps.autocontrast(image).convert("RGB").save(path, "PNG")


def _page_image(index: int, path: Path) -> PageImage:
    with Image.open(path) as image:
        return PageImage(index=index, path=path, width=image.width, height=image.height)


def _upload_bytes(uploaded_file) -> bytes:
    data = uploaded_file.getbuffer()
    if isinstance(data, bytes):
        return data
    return bytes(data)
