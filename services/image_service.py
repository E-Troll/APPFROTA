"""
Image Processing Service
Handles file uploads, EXIF auto-rotation, watermarking with timestamp,
mileage, vehicle plate, and safe storage in local uploads folder.
"""

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
    stage_label,       # 'SAÍDA', 'PARADA', 'CHEGADA'
    km_value,          # float or str
    plate,             # str
    driver_name="",    # str
    extra_text="",     # e.g. stop reason
    timestamp_str=None,
    upload_folder=None
):
    """
    Reads an uploaded image stream, corrects EXIF orientation,
    stamps an immutable visual watermark badge with date/time, mileage and vehicle,
    and saves it to the uploads directory.
    Returns the saved filename.
    """
    target_folder = upload_folder or DEFAULT_UPLOAD_FOLDER
    os.makedirs(target_folder, exist_ok=True)

    # Open image
    img = Image.open(file_storage.stream)

    # Correct EXIF rotation (smartphones often shoot sideways)
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Convert to RGB if needed
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # Resize if extremely large (e.g. > 1920px max dimension)
    max_dim = 1920
    if max(img.width, img.height) > max_dim:
        scale = max_dim / float(max(img.width, img.height))
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Prepare visual timestamp
    if not timestamp_str:
        dt = datetime.now()
    else:
        try:
            # Handles ISO format 'YYYY-MM-DDTHH:MM:SS' or 'YYYY-MM-DD HH:MM:SS'
            clean_ts = timestamp_str.replace('T', ' ')
            if len(clean_ts) > 19:
                clean_ts = clean_ts[:19]
            dt = datetime.strptime(clean_ts, '%Y-%m-%d %H:%M:%S')
        except Exception:
            dt = datetime.now()

    date_formatted = dt.strftime('%d/%m/%Y %H:%M:%S')

    # Watermark dimensions relative to image width
    w, h = img.size
    banner_height = max(70, int(h * 0.12))
    font_size_large = max(14, int(banner_height * 0.28))
    font_size_small = max(12, int(banner_height * 0.22))

    font_large = get_font(font_size_large)
    font_small = get_font(font_size_small)

    # Create RGBA overlay for semi-transparent dark banner
    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Draw bottom banner
    banner_y1 = h - banner_height
    draw.rectangle([(0, banner_y1), (w, h)], fill=(15, 23, 42, 210)) # Dark slate with 82% opacity

    # Stage Badge color
    badge_colors = {
        'SAÍDA': (37, 99, 235),     # Blue
        'PARADA': (217, 119, 6),    # Amber
        'CHEGADA': (22, 163, 74)    # Green
    }
    badge_color = badge_colors.get(stage_label.upper(), (79, 70, 229))

    # Badge rectangle on the left
    badge_w = int(font_size_large * len(stage_label) * 0.9) + 20
    badge_h = int(font_size_large * 1.5)
    badge_x = 16
    badge_y = banner_y1 + int((banner_height - badge_h) / 2)
    draw.rounded_rectangle(
        [(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)],
        radius=6,
        fill=badge_color + (255,)
    )
    draw.text(
        (badge_x + 10, badge_y + 3),
        stage_label.upper(),
        fill=(255, 255, 255, 255),
        font=font_large
    )

    # Text details
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

    # Merge overlay with original
    final_img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')

    # Generate unique filename
    clean_stage = stage_label.lower().replace('í', 'i')
    unique_suffix = uuid.uuid4().hex[:8]
    timestamp_prefix = dt.strftime('%Y%m%d_%H%M%S')
    filename = f"{clean_stage}_{timestamp_prefix}_{unique_suffix}.jpg"

    file_path = os.path.join(target_folder, filename)
    final_img.save(file_path, 'JPEG', quality=88, optimize=True)

    return filename


def delete_image_file(filename, upload_folder=None):
    """Safely removes an image file from the uploads directory."""
    if not filename:
        return
    folder = upload_folder or DEFAULT_UPLOAD_FOLDER
    path = os.path.join(folder, os.path.basename(filename))
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass
