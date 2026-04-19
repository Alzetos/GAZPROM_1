import json
import os


def add_to_memory(
    raw_text: str,
    corrected_data: dict = None,
    memory_file: str = "memory.json",
):
    new_entry = {
        "raw_text": raw_text.strip(),
        "corrected": json.dumps(corrected_data, ensure_ascii=False)
        if corrected_data
        else "RULE_ONLY",
    }
    memory_data = []

    if os.path.exists(memory_file):
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                memory_data = json.load(f)
        except json.JSONDecodeError:
            memory_data = []

    memory_data.append(new_entry)

    if len(memory_data) > 30:
        memory_data = memory_data[:-30]
    with open(memory_file, "w", encoding="utf-8") as f:
        json.dump(memory_data, ensure_ascii=False, indent=2)
    print("Память обновлена")
