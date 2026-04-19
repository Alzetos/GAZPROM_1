import qrcode
import os
from PIL import Image, ImageDraw, ImageFont


def generate_label(item_data, output_folder="data/exports/labels"):
    os.makedirs(output_folder, exist_ok=True)
    qr_text = (
        f"ID: {item_data.get('position_code', 'N/A')}\n"
        f"Name: {item_data.get('name')}\n"
        f"SN: {item_data.get('serial_number')}\n"
        f"Art: {item_data.get('article')}"
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=40,
        border=4,
    )

    qr.add_data(qr_text)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    canvas_width = qr_img.size[0]
    canvas_height = qr_img.size[1] + 80
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    canvas.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(canvas)

    try:
        font = ImageFont.truetype("arial.tff", 20)
    except:
        font = ImageFont.load_default()

    draw.text(
        (20, qr_img.size[1] + 5),
        f"Модель: {item_data.get('name')[:25]}...",
        fill="black",
        font=font,
    )
    draw.text(
        (20, qr_img.size[1] + 35),
        f"S/N: {item_data.get('serial_number')}",
        fill="black",
        font=font,
    )

    file_path = os.path.join(
        output_folder, f"Label {item_data.get('serial_number')}.png"
    )
    canvas.save(file_path)
    return file_path
