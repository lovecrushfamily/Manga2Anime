from __future__ import annotations

from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageStat

from manga2anime.models import LayeredPage, PageImage


TILE_SIZE = 96


def preprocess_pages(pages: list[PageImage], output_dir: Path) -> list[LayeredPage]:
    output_dir.mkdir(parents=True, exist_ok=True)
    layered: list[LayeredPage] = []
    previous_bbox: tuple[int, int, int, int] | None = None

    for page in pages:
        page_dir = output_dir / f"page_{page.index:03d}"
        page_dir.mkdir(parents=True, exist_ok=True)

        with Image.open(page.path) as source:
            source = ImageOps.exif_transpose(source).convert("RGB")

        regions = detect_dialogue_regions(source)
        clean_path = page_dir / "clean.png"
        background_path = page_dir / "background.png"
        character_path = page_dir / "character.png"

        clean = remove_dialogue_regions(source, regions)
        clean.save(clean_path, "PNG")
        create_background_plate(clean, background_path)
        foreground_bbox = create_character_cutout(clean, character_path, regions)
        motion_hint = infer_motion_hint(previous_bbox, foreground_bbox)
        previous_bbox = foreground_bbox or previous_bbox

        layered.append(
            LayeredPage(
                index=page.index,
                original_page=page,
                clean_page=_page_image(page.index, clean_path),
                background_path=background_path,
                character_path=character_path,
                dialogue_regions=regions,
                foreground_bbox=foreground_bbox,
                motion_hint=motion_hint,
            )
        )

    return layered


def detect_dialogue_regions(image: Image.Image) -> list[tuple[int, int, int, int]]:
    gray = image.convert("L")
    component_regions = _white_component_dialogue_regions(gray)
    if component_regions:
        return _merge_regions(component_regions, gray.width, gray.height)

    columns = max(1, (gray.width + TILE_SIZE - 1) // TILE_SIZE)
    rows = max(1, (gray.height + TILE_SIZE - 1) // TILE_SIZE)
    candidate = [[False for _ in range(columns)] for _ in range(rows)]

    for row in range(rows):
        for column in range(columns):
            left = column * TILE_SIZE
            top = row * TILE_SIZE
            right = min(gray.width, left + TILE_SIZE)
            bottom = min(gray.height, top + TILE_SIZE)
            crop = gray.crop((left, top, right, bottom))
            area = crop.width * crop.height
            histogram = crop.histogram()
            dark = sum(histogram[:85]) / area
            white = sum(histogram[235:]) / area
            contrast = ImageStat.Stat(crop).stddev[0]

            # Speech bubbles/caption boxes are usually mostly white with clustered ink.
            is_page_edge = row == 0 or column == 0 or row == rows - 1 or column == columns - 1
            candidate[row][column] = (
                not is_page_edge and white > 0.58 and 0.003 < dark < 0.20 and contrast > 9
            )

    regions = _candidate_regions(candidate, rows, columns, gray.width, gray.height)
    return _merge_regions(regions, gray.width, gray.height)


def _white_component_dialogue_regions(gray: Image.Image) -> list[tuple[int, int, int, int]]:
    max_side = 640
    scale = min(1.0, max_side / max(gray.width, gray.height))
    small_size = (max(1, round(gray.width * scale)), max(1, round(gray.height * scale)))
    small = gray.resize(small_size, Image.Resampling.LANCZOS)
    white = small.point(lambda value: 255 if value > 245 else 0)
    pixels = white.load()
    width, height = white.size
    seen = bytearray(width * height)
    regions: list[tuple[int, int, int, int]] = []

    for y in range(height):
        for x in range(width):
            offset = y * width + x
            if seen[offset] or pixels[x, y] == 0:
                continue
            queue = deque([(x, y)])
            seen[offset] = 1
            min_x = max_x = x
            min_y = max_y = y
            count = 0
            touches_edge = False

            while queue:
                current_x, current_y = queue.popleft()
                count += 1
                min_x = min(min_x, current_x)
                max_x = max(max_x, current_x)
                min_y = min(min_y, current_y)
                max_y = max(max_y, current_y)
                if current_x == 0 or current_y == 0 or current_x == width - 1 or current_y == height - 1:
                    touches_edge = True

                for next_x, next_y in (
                    (current_x - 1, current_y),
                    (current_x + 1, current_y),
                    (current_x, current_y - 1),
                    (current_x, current_y + 1),
                ):
                    if next_x < 0 or next_y < 0 or next_x >= width or next_y >= height:
                        continue
                    next_offset = next_y * width + next_x
                    if seen[next_offset] or pixels[next_x, next_y] == 0:
                        continue
                    seen[next_offset] = 1
                    queue.append((next_x, next_y))

            if touches_edge:
                continue
            if count < 80:
                continue

            mapped = (
                round(min_x / scale),
                round(min_y / scale),
                round((max_x + 1) / scale),
                round((max_y + 1) / scale),
            )
            region = _expand_region(mapped, gray.width, gray.height)
            if _component_region_is_plausible(region, gray.width, gray.height) and _has_inner_text(
                gray,
                region,
            ):
                regions.append(region)

    return regions


def _has_inner_text(gray: Image.Image, region: tuple[int, int, int, int]) -> bool:
    left, top, right, bottom = region
    width = right - left
    height = bottom - top
    inset_x = max(8, width // 9)
    inset_y = max(8, height // 9)
    inner = (
        min(right - 1, left + inset_x),
        min(bottom - 1, top + inset_y),
        max(left + 1, right - inset_x),
        max(top + 1, bottom - inset_y),
    )
    if inner[2] <= inner[0] or inner[3] <= inner[1]:
        return False
    crop = gray.crop(inner)
    area = crop.width * crop.height
    histogram = crop.histogram()
    dark = sum(histogram[:95]) / area
    white = sum(histogram[235:]) / area
    return white > 0.45 and 0.0015 < dark < 0.16


def remove_dialogue_regions(
    image: Image.Image,
    regions: list[tuple[int, int, int, int]],
) -> Image.Image:
    clean = image.convert("RGB")
    draw = ImageDraw.Draw(clean)
    for region in regions:
        draw.rounded_rectangle(region, radius=18, fill=(255, 255, 255))
    return clean


def create_background_plate(image: Image.Image, output_path: Path) -> None:
    background = image.convert("L")
    background = ImageOps.autocontrast(background)
    background = background.filter(ImageFilter.GaussianBlur(radius=0.35))
    background.convert("RGB").save(output_path, "PNG")


def create_character_cutout(
    image: Image.Image,
    output_path: Path,
    dialogue_regions: list[tuple[int, int, int, int]],
) -> tuple[int, int, int, int] | None:
    gray = ImageOps.autocontrast(image.convert("L"))
    alpha = gray.point(lambda value: 255 if value < 188 else 0)

    mask_draw = ImageDraw.Draw(alpha)
    for region in dialogue_regions:
        mask_draw.rectangle(region, fill=0)
    alpha = alpha.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(radius=1.0))

    bbox = alpha.getbbox()
    rgba = image.convert("RGBA")
    rgba.putalpha(alpha)
    rgba.save(output_path, "PNG")
    return bbox


def infer_motion_hint(
    previous_bbox: tuple[int, int, int, int] | None,
    current_bbox: tuple[int, int, int, int] | None,
) -> str:
    if not current_bbox:
        return "background_or_establishing"
    if not previous_bbox:
        return "establish_subject"

    previous_center = ((previous_bbox[0] + previous_bbox[2]) / 2, (previous_bbox[1] + previous_bbox[3]) / 2)
    current_center = ((current_bbox[0] + current_bbox[2]) / 2, (current_bbox[1] + current_bbox[3]) / 2)
    dx = current_center[0] - previous_center[0]
    dy = current_center[1] - previous_center[1]

    if abs(dx) > abs(dy) and abs(dx) > 48:
        return "subject_moves_right" if dx > 0 else "subject_moves_left"
    if abs(dy) > 48:
        return "subject_moves_down" if dy > 0 else "subject_moves_up"
    return "subject_holds_or_camera_push"


def build_direction_context(layered_pages: list[LayeredPage], dialogue_text: str) -> str:
    removed = sum(len(page.dialogue_regions) for page in layered_pages)
    motion_lines = [
        f"page {page.index}: {page.motion_hint}, dialogue_regions_removed={len(page.dialogue_regions)}"
        for page in layered_pages
    ]
    dialogue_section = dialogue_text.strip() or "No subtitle/OCR dialogue script available."
    return (
        "Preprocess requirements: dialogue/text regions have been removed from source frames. "
        "Do not put speech bubbles, captions, text, subtitles, sound effects, or lettering inside frames. "
        "Use dialogue only as off-frame story context.\n"
        f"Removed dialogue/text regions: {removed}.\n"
        "Layer/motion notes:\n"
        + "\n".join(motion_lines)
        + "\nDialogue script metadata:\n"
        + dialogue_section[:4000]
    )


def _candidate_regions(
    candidate: list[list[bool]],
    rows: int,
    columns: int,
    width: int,
    height: int,
) -> list[tuple[int, int, int, int]]:
    seen = [[False for _ in range(columns)] for _ in range(rows)]
    regions: list[tuple[int, int, int, int]] = []

    for row in range(rows):
        for column in range(columns):
            if seen[row][column] or not candidate[row][column]:
                continue
            queue = deque([(row, column)])
            seen[row][column] = True
            cells: list[tuple[int, int]] = []
            while queue:
                current_row, current_column = queue.popleft()
                cells.append((current_row, current_column))
                for next_row in range(max(0, current_row - 1), min(rows, current_row + 2)):
                    for next_column in range(max(0, current_column - 1), min(columns, current_column + 2)):
                        if seen[next_row][next_column] or not candidate[next_row][next_column]:
                            continue
                        seen[next_row][next_column] = True
                        queue.append((next_row, next_column))

            if len(cells) < 1:
                continue
            min_row = min(cell[0] for cell in cells)
            max_row = max(cell[0] for cell in cells)
            min_col = min(cell[1] for cell in cells)
            max_col = max(cell[1] for cell in cells)
            region = _expand_region(
                (
                    min_col * TILE_SIZE,
                    min_row * TILE_SIZE,
                    min(width, (max_col + 1) * TILE_SIZE),
                    min(height, (max_row + 1) * TILE_SIZE),
                ),
                width,
                height,
            )
            if _region_is_plausible(region, width, height):
                regions.append(region)
    return regions


def _expand_region(
    region: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    pad_x = max(20, TILE_SIZE // 2)
    pad_y = max(20, TILE_SIZE // 2)
    return (
        max(0, region[0] - pad_x),
        max(0, region[1] - pad_y),
        min(width, region[2] + pad_x),
        min(height, region[3] + pad_y),
    )


def _region_is_plausible(region: tuple[int, int, int, int], width: int, height: int) -> bool:
    region_width = region[2] - region[0]
    region_height = region[3] - region[1]
    area_ratio = (region_width * region_height) / (width * height)
    aspect = region_width / max(region_height, 1)
    return 0.006 <= area_ratio <= 0.38 and 0.18 <= aspect <= 6.0


def _component_region_is_plausible(
    region: tuple[int, int, int, int],
    width: int,
    height: int,
) -> bool:
    region_width = region[2] - region[0]
    region_height = region[3] - region[1]
    area_ratio = (region_width * region_height) / (width * height)
    aspect = region_width / max(region_height, 1)
    return 0.004 <= area_ratio <= 0.14 and 0.25 <= aspect <= 5.5


def _merge_regions(
    regions: list[tuple[int, int, int, int]],
    width: int,
    height: int,
) -> list[tuple[int, int, int, int]]:
    merged: list[tuple[int, int, int, int]] = []
    for region in regions:
        active = region
        changed = True
        while changed:
            changed = False
            remaining: list[tuple[int, int, int, int]] = []
            for other in merged:
                if _overlaps_or_touches(active, other):
                    active = (
                        max(0, min(active[0], other[0])),
                        max(0, min(active[1], other[1])),
                        min(width, max(active[2], other[2])),
                        min(height, max(active[3], other[3])),
                    )
                    changed = True
                else:
                    remaining.append(other)
            merged = remaining
        merged.append(active)
    return merged


def _overlaps_or_touches(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    pad = TILE_SIZE // 3
    return not (a[2] + pad < b[0] or b[2] + pad < a[0] or a[3] + pad < b[1] or b[3] + pad < a[1])


def _page_image(index: int, path: Path) -> PageImage:
    with Image.open(path) as image:
        return PageImage(index=index, path=path, width=image.width, height=image.height)
