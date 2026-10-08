from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image
from rembg import remove


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/prep_photo.py source-photo.jpg")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path("source-prepped.png")

    if not input_path.exists():
        print(f"File not found: {input_path}")
        sys.exit(1)

    print("Removing background...")

    image = Image.open(input_path).convert("RGBA")
    foreground = remove(image)

    print("Processing image...")

    rgba = np.array(foreground)

    alpha = rgba[:, :, 3]

    coords = cv2.findNonZero(
        (alpha > 10).astype(np.uint8)
    )

    if coords is not None:
        x, y, w, h = cv2.boundingRect(coords)
        rgba = rgba[y:y + h, x:x + w]

    rgb = rgba[:, :, :3]
    alpha = rgba[:, :, 3]

    white = np.full_like(rgb, 255)

    alpha_float = alpha.astype(np.float32) / 255.0

    composited = (
        rgb.astype(np.float32) * alpha_float[:, :, None]
        + white.astype(np.float32) * (1 - alpha_float[:, :, None])
    )

    composited = composited.astype(np.uint8)

    gray = cv2.cvtColor(composited, cv2.COLOR_RGB2GRAY)

    clahe = cv2.createCLAHE(
        clipLimit=2.5,
        tileGridSize=(8, 8)
    )

    gray = clahe.apply(gray)

    height, width = gray.shape

    max_width = 900

    if width > max_width:
        new_height = int(height * max_width / width)
        gray = cv2.resize(
            gray,
            (max_width, new_height),
            interpolation=cv2.INTER_AREA
        )

    cv2.imwrite(str(output_path), gray)

    print(f"Created: {output_path}")


if __name__ == "__main__":
    main()