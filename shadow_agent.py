import json
from memory_manager import add_to_memory
from llm_backend import llm


class ShadowAgent:
    def __init__(self):
        pass

    def process_correction(
        self, original_text: str, ai_parsed_json: dict, human_correction_json: dict
    ):

        print("\n[SHADOW AGENT] ")

        if ai_parsed_json == human_correction_json:
            print("Правки не обнаружены.")
            return
        safe_raw_text = original_text
        if len(safe_raw_text) > 12000:
            safe_raw_text = (
                safe_raw_text[:12000]
                + "\n\n[ТЕКСТ СЛИШКОМ БОЛЬШОЙ, ОСТАТОК ОБРЕЗАН ДЛЯ ЭКОНОМИИ ПАМЯТИ]"
            )

        prompt = f"""
Ты — старший инженер ОТК.
ОШИБКА АССИСТЕНТА: {json.dumps(ai_parsed_json, ensure_ascii=False)}
ИСПРАВЛЕНИЕ ЧЕЛОВЕКА: {json.dumps(human_correction_json, ensure_ascii=False)}
ИСХОДНЫЙ ТЕКСТ: {safe_raw_text}

ЗАДАЧА:
Сравни ошибку и исправление. Пойми, в чем состояла логика человека (например: человек исправил латинскую 'I' на цифру '1', или человек понял, что 'TREL' это на самом деле 'TREI', или человек склеил разорванный серийный номер).

Напиши ОДНО краткое, строгое правило для ассистента на будущее. 
Например: "Всегда заменяй TREL на TREI в артикулах" или "Если серийный номер разорван пробелом, склеивай его".

ВЫВЕДИ ТОЛЬКО ТЕКСТ ПРАВИЛА. Никаких приветствий и объяснений.
"""
        try:
            response = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": "Ты — строгий аналитик данных."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=150,
            )

            new_rule = response["choices"][0]["message"]["content"].strip()
            print(f" Сгенерировано новое правило -> {new_rule}")

            add_to_memory(raw_text="SYSTEM_RULE", corrected_data={"rule": new_rule})
            print(" Правило успешно сохранено в Базу Знаний (Memory).")

        except Exception as e:
            print(f"Ошибка Shadow Agent: {e}")


def send_to_shadow_agent(original_text, ai_json, human_json):
    agent = ShadowAgent()
    agent.process_correction(original_text, ai_json, human_json)
