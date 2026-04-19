import os
import subprocess
from llama_cpp import Llama

MODEL_PATH = "qwen2.5-3b-instruct-q4_k_m.gguf"

if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"Файл модели {MODEL_PATH} не найден! Положите его рядом со скриптами."
    )


def check_gpu_available():
    try:
        subprocess.run(
            ["nvidia-smi"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


print("[LLM BACKEND] Проверка оборудования")
has_gpu = check_gpu_available()

n_gpu_layers = -1 if has_gpu else 0

if has_gpu:
    print("[LLM BACKEND] Видеокарта NVIDIA обнаружена! Включаем аппаратное ускорение.")
else:
    print(
        "[LLM BACKEND] Видеокарта не обнаружена или недоступна. Запуск только на CPU."
    )

print("[LLM BACKEND] Загрузка модели...")

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=8192,
    n_threads=6,
    n_gpu_layers=n_gpu_layers,
    n_batch=2048,  # Ускоряет "проглатывание" входного текста
    flash_attn=True,  # Ускоряет работу с длинным контекстом в 2-3 раза
    verbose=False,
)

print("[LLM BACKEND] Модель успешно загружена!")
