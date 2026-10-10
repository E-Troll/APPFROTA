"""
Image Processing Service
Handles file uploads, EXIF auto-rotation, watermarking with timestamp,
mileage, vehicle plate, and safe storage in local uploads folder.
"""

import io
import os
import uuid
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
DEFAULT_UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_font(size):
    """Attempts to load a clean TrueType font, falling back to default."""
    font_paths = [
        '/System/Library/Fonts/Helvetica.ttc',
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        '/Library/Fonts/Arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
        'C:\\Windows\\Fonts\\arial.ttf'
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def process_and_save_odometer_photo(
    file_storage,
    stage_label,
    km_value,
    plate,
    driver_name="",
    extra_text="",
    timestamp_str=None,
    upload_folder=None
):
    """Rotate, watermark and compress a photo before writing it to storage."""
    target_folder = upload_folder or DEFAULT_UPLOAD_FOLDER
    os.makedirs(target_folder, exist_ok=True)
    img = Image.open(file_storage.stream)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    if img.mode != 'RGB':
        img = img.convert('RGB')

    max_dim = 1280
    if max(img.width, img.height) > max_dim:
        scale = max_dim / float(max(img.width, img.height))
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)

    if not timestamp_str:
        dt = datetime.now()
    else:
        try:
            clean_ts = timestamp_str.strip().replace('T', ' ')
            dt = datetime.fromisoformat(clean_ts)
        except Exception:
            dt = datetime.now()

    date_formatted = dt.strftime('%d/%m/%Y %H:%M:%S')
    w, h = img.size
    banner_height = max(70, int(h * 0.12))
    font_size_large = max(14, int(banner_height * 0.28))
    font_size_small = max(12, int(banner_height * 0.22))
    font_large = get_font(font_size_large)
    font_small = get_font(font_size_small)

    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    banner_y1 = h - banner_height
    draw.rectangle([(0, banner_y1), (w, h)], fill=(15, 23, 42, 210))
    badge_colors = {
        'SAÍDA': (37, 99, 235),
        'PARADA': (217, 119, 6),
        'CHEGADA': (22, 163, 74)
    }
    badge_color = badge_colors.get(stage_label.upper(), (79, 70, 229))
    badge_w = int(font_size_large * len(stage_label) * 0.9) + 20
    badge_h = int(font_size_large * 1.5)
    badge_x = 16
    badge_y = banner_y1 + int((banner_height - badge_h) / 2)
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
        radius=6,
        fill=badge_color + (255,)
    )
    draw.text((badge_x + 10, badge_y + 3), stage_label.upper(), fill=(255, 255, 255, 255), font=font_large)
    text_x = badge_x + badge_w + 16
    try:
        km_formatted = f"{float(km_value):,.1f}".replace(',', 'X').replace('.', ',').replace('X', '.') + " KM"
    except Exception:
        km_formatted = f"{km_value} KM"
    line1 = f"ODÔMETRO: {km_formatted}  |  VEÍCULO: {plate.upper()}"
    line2 = f"REGISTRO: {date_formatted}"
    if driver_name:
        line2 += f"  |  CONDUTOR: {driver_name}"
    if extra_text:
        line2 += f"  |  {extra_text}"
    draw.text((text_x, banner_y1 + 10), line1, fill=(255, 255, 255, 255), font=font_large)
    draw.text((text_x, banner_y1 + 10 + font_size_large + 6), line2, fill=(203, 213, 225, 255), font=font_small)
    final_img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')

    clean_stage = stage_label.lower().replace('í', 'i')
    filename = f"{clean_stage}_{dt.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
    file_path = os.path.join(target_folder, filename)

    # Aim for <= 220 KiB so the free Storage quota holds more photos.
    working_img = final_img
    quality = 62
    max_bytes = 220 * 1024
    while True:
        output = io.BytesIO()
        working_img.save(output, 'JPEG', quality=quality, optimize=True, progressive=True, subsampling=2)
        if output.tell() <= max_bytes:
            break
        longest_side = max(working_img.size)
        if quality > 42:
            quality = max(42, quality - 8)
        elif longest_side > 720:
            scale = max(720 / longest_side, 0.85)
            new_size = (max(1, int(working_img.width * scale)), max(1, int(working_img.height * scale)))
            working_img = working_img.resize(new_size, Image.Resampling.LANCZOS)
            quality = 54
        else:
            break
    with open(file_path, 'wb') as image_file:
        image_file.write(output.getvalue())
    return filename


def delete_image_file(filename, upload_folder=None):
    """Safely removes an image file from the local uploads directory."""
    if not filename:
        return
    folder = upload_folder or DEFAULT_UPLOAD_FOLDER
    path = os.path.join(folder, os.path.basename(filename))
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass
