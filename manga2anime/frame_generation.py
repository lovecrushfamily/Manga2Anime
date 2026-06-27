from __future__ import annotations

import base64
import shutil
from contextlib import ExitStack
from pathlib import Path

from openai import OpenAI
from PIL import Image, ImageOps

from manga2anime.config import AppConfig
from manga2anime.models import DirectorPlan, PageImage, RenderFrame
from manga2anime.openai_utils import extract_image_b64, image_to_data_url


def generate_action_frames(
    pages: list[PageImage],
    plan: DirectorPlan,
    style_prompt: str,
    config: AppConfig,
    output_dir: Path,
    enabled: bool,
    character_references: dict[int, Path] | None = None,
) -> list[RenderFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    frames: list[RenderFrame] = []
    page_by_index = {page.index: page for page in pages}

    client = OpenAI(api_key=config.openai_api_key) if config.has_openai_key and enabled else None
    for shot_index, shot in enumerate(plan.shots, start=1):
        source = page_by_index.get(shot.source_page) or pages[0]
        generated_path = output_dir / f"shot_{shot_index:03d}.png"
        if client:
            try:
                _generate_frame(
                    client,
                    config,
                    source,
                    character_references.get(source.index) if character_references else None,
                    shot.frame_prompt,
                    plan.style_directive,
                    style_prompt,
                    generated_path,
                    reference_paths=[],
                )
                frames.append(RenderFrame(path=generated_path, source_page=source.index, generated=True))
                continue
            except Exception:
                pass
        fallback_path = output_dir / f"shot_{shot_index:03d}_source.png"
        shutil.copyfile(source.path, fallback_path)
        frames.append(RenderFrame(path=fallback_path, source_page=source.index, generated=False))
    return frames


def _generate_frame(
    client: OpenAI,
    config: AppConfig,
    source: PageImage,
    character_reference: Path | None,
    frame_prompt: str,
    style_directive: str,
    style_prompt: str,
    output_path: Path,
    reference_paths: list[Path] | None = None,
) -> None:
    reference_paths = reference_paths or []
    prompt = (
        "Create one new transition/action frame for a short fanmade anime adaptation. "
        "Use clean black-and-white manga/anime line art with high-contrast ink. "
        "IDENTITY LOCK: the uploaded reference is the character model sheet. Preserve the exact "
        "same face identity, facial proportions, eye shape, nose, mouth, hairstyle, hairline, "
        "costume details, silhouette, body proportions, line weight, screentone feel, and manga "
        "drawing style. Do not beautify, age up/down, redesign, swap gender, change expression "
        "structure, change hairstyle, change outfit, or invent a new face. Camera angle, crop, "
        "pose, and background may change only when the character is still unmistakably the same "
        "model from the reference. If a requested camera angle would require guessing the face, "
        "keep the original readable face angle instead. If the reference face is hidden, blank, "
        "simple, cropped, or not clearly drawn, do not invent eyes, mouth, hair, clothing, or "
        "anime facial details; keep that face hidden/simple exactly as the source implies. "
        "No color, no text bubbles, no captions, "
        "no watermark. Preserve the story beat while using the source page and character cutout "
        "as identity references. Redraw any missing background naturally as clean inked "
        "environment art. Keep dialogue off-frame; do not render subtitles or lettering. "
        "When additional approved keyframes are provided, use them only as continuity references "
        "for pose, camera flow, lighting, and motion spacing; never overwrite the source character "
        "identity. "
        f"{style_directive}\n\nDirector frame prompt: {frame_prompt}\nUser prompt: {style_prompt}"
    )
    errors: list[str] = []
    image_b64 = None
    for generator in (
        lambda: _generate_with_image_edit_api(
            client,
            config,
            source,
            character_reference,
            reference_paths,
            prompt,
        ),
        lambda: _generate_with_responses_tool(
            client,
            config,
            source,
            character_reference,
            reference_paths,
            prompt,
        ),
    ):
        try:
            image_b64 = generator()
        except Exception as exc:  # noqa: BLE001 - try the next supported image path.
            errors.append(f"{type(exc).__name__}: {exc}")
            continue
        if image_b64:
            break
    if not image_b64:
        detail = "; ".join(errors) if errors else "no image data returned"
        raise RuntimeError(f"OpenAI image generation failed: {detail}")
    output_path.write_bytes(base64.b64decode(image_b64))
    _force_black_and_white(output_path)
    if not _passes_identity_detail_guard(source.path, output_path):
        output_path.unlink(missing_ok=True)
        raise RuntimeError("Generated frame rejected because it added too much new character detail.")


def _generate_with_image_edit_api(
    client: OpenAI,
    config: AppConfig,
    source: PageImage,
    character_reference: Path | None,
    reference_paths: list[Path],
    prompt: str,
) -> str | None:
    with ExitStack() as stack:
        image_files = [stack.enter_context(source.path.open("rb"))]
        if character_reference and character_reference.exists():
            image_files.append(stack.enter_context(character_reference.open("rb")))
        for reference_path in reference_paths:
            if reference_path.exists():
                image_files.append(stack.enter_context(reference_path.open("rb")))
        image: object = image_files if len(image_files) > 1 else image_files[0]
        return _image_edit_request(client, config, image, prompt)


def _image_edit_request(
    client: OpenAI,
    config: AppConfig,
    image: object,
    prompt: str,
) -> str | None:
    response = client.images.edit(
        model=config.image_model,
        image=image,
        prompt=prompt,
        size="1024x1536",
        n=1,
        input_fidelity="high",
    )
    if not response.data:
        return None
    return getattr(response.data[0], "b64_json", None)


def _generate_with_responses_tool(
    client: OpenAI,
    config: AppConfig,
    source: PageImage,
    character_reference: Path | None,
    reference_paths: list[Path],
    prompt: str,
) -> str | None:
    content = [
        {"type": "input_text", "text": prompt},
        {"type": "input_image", "image_url": image_to_data_url(source.path)},
    ]
    if character_reference and character_reference.exists():
        content.append({"type": "input_image", "image_url": image_to_data_url(character_reference)})
    for reference_path in reference_paths:
        if reference_path.exists():
            content.append({"type": "input_image", "image_url": image_to_data_url(reference_path)})
    response = client.responses.create(
        model=config.vision_model,
        input=[
            {
                "role": "user",
                "content": content,
            }
        ],
        tools=[{"type": "image_generation", "size": "1024x1536"}],
    )
    return extract_image_b64(response)


def _force_black_and_white(path: Path) -> None:
    with Image.open(path) as image:
        image = ImageOps.autocontrast(image.convert("L")).convert("RGB")
        image.save(path, "PNG")


def _passes_identity_detail_guard(source_path: Path, generated_path: Path) -> bool:
    source_density = _ink_density(source_path)
    generated_density = _ink_density(generated_path)
    if source_density < 0.07 and generated_density > 0.12:
        return False
    return generated_density <= max(0.5, source_density * 4.5)


def generate_studio_image_asset(
    source: PageImage,
    character_reference: Path | None,
    reference_paths: list[Path],
    frame_prompt: str,
    style_directive: str,
    style_prompt: str,
    config: AppConfig,
    output_path: Path,
    enabled: bool,
) -> bool:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=config.openai_api_key) if enabled and config.has_openai_key else None
    if client:
        try:
            _generate_frame(
                client,
                config,
                source,
                character_reference,
                frame_prompt,
                style_directive,
                style_prompt,
                output_path,
                reference_paths=reference_paths,
            )
            return True
        except Exception:
            output_path.unlink(missing_ok=True)
    shutil.copyfile(source.path, output_path)
    return False


def _ink_density(path: Path) -> float:
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("L")
        ratio = 256 / max(1, image.width)
        size = (256, max(1, round(image.height * ratio)))
        image = image.resize(size, Image.Resampling.LANCZOS)
        histogram = image.histogram()
        area = image.width * image.height
        return sum(histogram[:120]) / area
