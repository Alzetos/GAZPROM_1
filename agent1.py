import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from llm_backend import llm
import time
import os


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Agent_1")


class Features(BaseModel):
    param_name: str = Field(
        description="Название характеристики (например, 'Габариты', 'Масса', 'Напряжение')"
    )
    param_value: str = Field(
        description="Значение с единицами измерения (например, '130x50x211 мм', 'IP20')"
    )
    source_page: Optional[int] = Field(
        description="Номер страницы, где найдена хаарктеристика"
    )


class NomenclatureItem(BaseModel):
    position_code: Optional[str] = Field(
        default=None,
        description="Код позиции. Заполняй ТОЛЬКО если он явно указан в тексте. Иначе передавай null. НЕ выдумывай значения вроде user.1",
    )
    name: str = Field(description="Наименование")
    article: Optional[str] = Field(default=None, description="Артикул/марка")
    unit: str = Field(default="шт.", description="Единица измерения")
    quantity: int = Field(default=1, description="Количество")
    serial_number: Optional[str] = Field(default="б/н", description="Серийный номер ")
    source_page: Optional[int] = Field(
        description="Номер страницы, где найдена информация"
    )
    specifications: List[Features] = Field(
        default_factory=list, description="Список технических характеристик"
    )


class ExtractedDocument(BaseModel):
    items: List[NomenclatureItem]


def load_memory() -> str:
    try:
        with open("memory.json", "r", encoding="utf-8") as f:
            memory_data = json.load(f)

            if not isinstance(memory_data, list):
                return ""

            if not memory_data:
                return ""

            memory_promt = "ОБРАТИ ВНИМАНИЕ НА ПРОШЛЫЙ ОПЫТ (ИСПРАВЛЕНИЯ ОПЕРАТОРА):\n"
            for entry in memory_data[-3:]:
                memory_promt += f"Текст: {entry['raw_text']}\nПравильный вывод: {entry['corrected']}\n\n"
            return memory_promt
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


def clean_json_bbox(raw_json_str: str) -> str:
    try:
        data = json.loads(raw_json_str)
        lines = []
        for item in data:
            lines.append(f"[Стр.{item.get('page')}] {item.get('text')}")
        return "\n".join(lines)
    except Exception:
        return raw_json_str


def process_document(ocr_json_str: str) -> Optional[ExtractedDocument]:
    print("[AGENT 1] ФУНКЦИЯ ЗАПУЩЕНА")
    logger.info("Агент 1 запущен")
    optimized_json = clean_json_bbox(ocr_json_str)

    print(f"[AGENT 1] Длина текста для llama: {len(optimized_json)} символов")
    base_promt = (
        "Ты строгий технический ИИ-аналитик. Тебе на вход подается текст документа после OCR.\n"
        "ВАЖНО: Документ может быть как ПАСПОРТОМ на ОДИН прибор, так и ПЕРЕЧНЕМ (списком многих приборов).\n\n"
        "ТВОЙ АЛГОРИТМ ДЕЙСТВИЙ:\n"
        "1. ОПРЕДЕЛИ ТИП ДОКУМЕНТА:\n"
        "   - Если это 'Перечень документации' (таблица): создай отдельный элемент в 'items' для каждой значимой строки. В 'specifications' ничего не пиши.\n"
        "   - Если это ПАСПОРТ на конкретный прибор: создай СТРОГО ОДИН элемент в 'items'. Найди его главный серийный номер (часто на штампе ОТК или в 'Свидетельстве о приемке').\n"
        "2. СЕРИЙНЫЕ НОМЕРА И НАЗВАНИЯ: Исправляй ошибки OCR. Букву 'O' в цифрах меняй на ноль '0' (например, 'M12O1E' -> 'M1201E', 'G4MIO821' -> 'G4M0821'). Если номера нет, пиши 'б/н'.\n"
        "3. ХАРАКТЕРИСТИКИ ('specifications'): Обязательно ищи раздел 'Технические характеристики' (Тип процессора, ОЗУ, Габариты, Масса, Напряжение и т.д.). Если документ — это Паспорт, ВЫТАЩИ ВСЕ физические и электрические параметры в этот список.\n"
        "4. КРИТИЧЕСКОЕ ПРАВИЛО: Не дроби один паспорт на несколько 'items' из-за упоминания других систем в тексте. Верни валидный JSON, строго соответствующий схеме."
    )
    memory_promt = load_memory()
    system_instruction = f"{base_promt}\n\n{memory_promt}"

    try:
        print("[AGENT 1] ГЕНЕРАЦИЯ LLAMA-CPP. ЖДЕМ")

        schema = ExtractedDocument.model_json_schema()

        response = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_instruction},
                {
                    "role": "user",
                    "content": f"Извлеки данные в формате JSON:\n\n{optimized_json}",
                },
            ],
            response_format={"type": "json_object", "schema": schema},
            temperature=0.0,
            max_tokens=2000,
        )

        json_str = response["choices"][0]["message"]["content"]
        parsed_data = ExtractedDocument.model_validate_json(json_str)

        print("[AGENT 1] ОТВЕТ УСПЕШНО ПОЛУЧЕН!")
        logger.info(f"Извлечено {len(parsed_data.items)} позиций")

        save_dir = "data/parsed_passports"
        os.makedirs(save_dir, exist_ok=True)
        filename = f"parsed_{int(time.time())}.json"
        if parsed_data.items:
            filename = f"{parsed_data.items[0].name.replace(' ', '_').replace('/', '_')}_{int(time.time())}.json"

        file_path = os.path.join(save_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(parsed_data.model_dump_json(indent=2))

        return parsed_data
    except Exception as e:
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА АГЕНТА 1: {type(e).__name__} - {e}")
        return None


def self_reflectiojn_step(raw_text: str, first_draft_json: str):
    print("[AGENT 1] ЗАПУСК САМОПРОВЕРКИ")

    reflection_prompt = (
        "Ты — технический контролер. Перед тобой исходный текст и JSON, который составил твой коллега.\n"
        f"ИСХОДНЫЙ ТЕКСТ: {raw_text}\n"
        f"JSON ДЛЯ ПРОВЕРКИ: {first_draft_json}\n"
        "ЗАДАЧА: Проверь, не перепутаны ли поля. Особое внимание серийному номеру и артикулу. "
        "ВЕРНИ СТРОГО ВАЛИДНЫЙ JSON. Если всё верно — верни исходный JSON. Если есть ошибка — исправь её."
    )

    try:
        schema = ExtractedDocument.model_json_schema()

        response = llm.create_chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": "Ты строгий ИИ-аудитор. Возвращай только валидный JSON без комментариев.",
                },
                {"role": "user", "content": reflection_prompt},
            ],
            response_format={"type": "json_object", "schema": schema},
            temperature=0.0,
            max_tokens=2000,
        )

        corrected_json_str = response["choices"][0]["message"]["content"]
        print("[AGENT 1] САМОПРОВЕРКА ЗАВЕРШЕНА")
        return corrected_json_str

    except Exception as e:
        logger.error(f"Ошибка при самопроверке (Reflection): {e}")
        return first_draft_json
