import os
import json
import fitz
import cv2
import numpy as np
from paddleocr import PaddleOCR


def run_ocr_pipeline(input_folder="passport", output_folder="json"):
    if not os.path.exists("json"):
        os.makedirs("json")

    ocr = PaddleOCR(use_textline_orientation=True, lang="ru", show_log=False)

    files = [f for f in os.listdir(input_folder) if not f.startswith(".")]

    for name in files:
        path = os.path.join(input_folder, name)
        ext = name.lower()
        extracted_data = []

        try:
            if ext.endswith(".pdf"):
                print("Processing PDF:", name)
                doc = fitz.open(path)
                for page_num in range(len(doc)):
                    print(f"Страница {page_num + 1}/{len(doc)}")
                    page = doc[page_num]
                    # убираем прозрачность, делая белый фон
                    pix = page.get_pixmap(dpi=300, alpha=False)

                    # Прямая конвертация в OpenCV без сохранения temp.png
                    img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                        pix.height, pix.width, pix.n
                    )

                    if pix.n == 1:
                        img_cv2 = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)
                    elif pix.n == 3:
                        img_cv2 = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                    elif pix.n == 4:
                        img_cv2 = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
                    else:
                        img_cv2 = img_np

                    results = ocr.ocr(img_cv2)

                    if results and results[0]:
                        for line in results[0]:
                            bbox = line[0]  # Координаты блока
                            text = line[1][0]  # текст

                            extracted_data.append(
                                {"page": page_num + 1, "text": text, "bbox": bbox}
                            )
                doc.close()

            elif ext.endswith((".jpg", ".jpeg", ".png")):
                print("Processing image:", name)
                img_cv2 = cv2.imread(path)
                results = ocr.ocr(img_cv2)
                if results and results[0]:
                    for line in results[0]:
                        extracted_data.append(
                            {"page": 1, "text": line[1][0], "bbox": line[0]}
                        )
            else:
                print(f"(неизвестный формат): {name}")
                continue

            json_name = name + ".json"
            final_path = os.path.join("json", json_name)

            with open(final_path, "w", encoding="utf-8") as f:
                json.dump(extracted_data, f, ensure_ascii=False, indent=4)

        except Exception as e:
            print("Ошибка в файле", name, ":", e)


if __name__ == "__main__":
    run_ocr_pipeline()
