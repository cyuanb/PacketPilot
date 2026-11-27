"""Bounded page rasterization shared by isolated parsing and authenticated previews."""

import threading

from PIL import Image, ImageOps

PDF_LOCK = threading.Lock()


def page_image(source, suffix, number=1):
    if suffix == ".pdf":
        import pypdfium2 as pdfium

        with PDF_LOCK:
            with pdfium.PdfDocument(source) as pdf:
                if number < 1 or number > len(pdf):
                    raise ValueError("页面不存在")
                page = pdf[number - 1]
                w, h = page.get_size()
                if w <= 0 or h <= 0:
                    raise ValueError("页面尺寸无效")
                scale = min(2.0, 2400 / max(w, h))
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil().copy()
                bitmap.close()
                page.close()
                return image
    if number != 1:
        raise ValueError("图片只有一页")
    with Image.open(source) as image:
        if image.width * image.height > 40_000_000:
            raise ValueError("图片超过 4000 万像素限制")
        result = ImageOps.exif_transpose(image).convert("RGB")
        result.thumbnail((2400, 2400))
        return result
