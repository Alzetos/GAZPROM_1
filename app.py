import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import json
import shutil
from PIL import Image

import main_ocr
from agent1 import process_document, ExtractedDocument, NomenclatureItem
from agent2 import CabinetAgent
from shadow_agent import ShadowAgent
from qr_generator import generate_label
from data_exporter import export_to_excel

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class GazpromApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Интеллектуальное ОТК: Система сборки шкафов")
        self.geometry("1100x850")

        self.folders = ["passports", "json", "data/exports", "data/exports/labels"]
        for f in self.folders:
            os.makedirs(f, exist_ok=True)

        self.clear_temp_folders()

        # Структуры для пакетной обработки (Per-file data)
        self.raw_ocr_results = {}  # filename -> raw text
        self.ai_raw_outputs = {}  # filename -> оригинальный JSON от Агента 1
        self.session_results = {}  # filename -> отредактированный JSON
        self.current_val_file = None  # имя текущего выбранного файла в валидации

        self.cabinet_passports = []

        # Создаем интерфейс
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(padx=20, pady=20, fill="both", expand=True)

        self.tab_ocr = self.tabview.add("1. Оцифровка")
        self.tab_val = self.tabview.add("2. Валидация (Shadow)")
        self.tab_build = self.tabview.add("3. Аудит и Отчеты")

        self.setup_ocr_tab()
        self.setup_val_tab()
        self.setup_build_tab()

    # OCR + АГЕНТ 1
    def setup_ocr_tab(self):
        ctk.CTkLabel(
            self.tab_ocr,
            text="Загрузка и распознавание документов",
            font=("Arial", 22, "bold"),
        ).pack(pady=10)

        btn_frame = ctk.CTkFrame(self.tab_ocr, fg_color="transparent")
        btn_frame.pack(pady=5)

        self.btn_select = ctk.CTkButton(
            btn_frame, text="Выбрать PDF/Изображения", command=self.select_files
        )
        self.btn_select.pack(side="left", padx=10)

        self.btn_run = ctk.CTkButton(
            btn_frame,
            text="Запустить ИИ-конвейер",
            fg_color="green",
            command=self.start_pipeline,
        )
        self.btn_run.pack(side="left", padx=10)

        self.ocr_log = ctk.CTkTextbox(
            self.tab_ocr, width=950, height=500, font=("Consolas", 12)
        )
        self.ocr_log.pack(pady=10)

    def clear_temp_folders(self):
        print("[INIT] Очистка временных папок...")
        for folder in ["passports", "json"]:
            if os.path.exists(folder):
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    except Exception as e:
                        print(f"Не удалось удалить {file_path}: {e}")

    def select_files(self):
        files = filedialog.askopenfilenames(
            filetypes=[("PDF and Images", "*.pdf *.jpg *.jpeg *.png")]
        )
        if files:
            for f in files:
                try:
                    shutil.copy(f, "passports")
                except Exception as e:
                    print(f"Ошибка копирования {f}: {e}")

            self.write_log(
                f"Добавлено файлов: {len(files)}. Всего в очереди: {len(os.listdir('passports'))}"
            )

    def start_pipeline(self):
        self.btn_run.configure(state="disabled")
        self.ocr_log.delete("0.0", "end")
        threading.Thread(target=self.pipeline_worker, daemon=True).start()

    def pipeline_worker(self):
        try:
            self.write_log("[ШАГ 1/2] Запуск PaddleOCR. Анализируем страницы...")
            main_ocr.run_ocr_pipeline("passports", "json")

            json_files = [f for f in os.listdir("json") if f.endswith(".json")]
            self.write_log(
                f"[ШАГ 2/2] Агент 1 приступает к анализу {len(json_files)} документов..."
            )

            self.raw_ocr_results.clear()
            self.ai_raw_outputs.clear()
            self.session_results.clear()

            for j_file in json_files:
                path = os.path.join("json", j_file)
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.raw_ocr_results[j_file] = content

                    self.write_log(f"   Обработка: {j_file}...")
                    res = process_document(content)

                    if res and res.items:
                        items_dump = [item.model_dump() for item in res.items]

                        self.ai_raw_outputs[j_file] = {
                            "items": items_dump
                        }  # Оригинал для Shadow
                        self.session_results[j_file] = items_dump  # Черновик для правок

                        for item in res.items:
                            self.write_log(
                                f"      Распознано: {item.name} (SN: {item.serial_number})"
                            )

            self.after(0, self.update_val_ui)
            self.write_log("\nКОНВЕЙЕР ЗАВЕРШЕН. Переходите к Валидации.")
        except Exception as e:
            self.write_log(f"ОШИБКА: {e}")
        finally:
            self.after(0, lambda: self.btn_run.configure(state="normal"))

    # ВАЛИДАЦИЯ + ТЕНЕВОЙ АГЕНТ
    def setup_val_tab(self):
        ctk.CTkLabel(
            self.tab_val,
            text="Контроль качества и правка данных",
            font=("Arial", 22, "bold"),
        ).pack(pady=10)

        # ДОБАВЛЕНО: Выпадающий список файлов
        self.file_selector = ctk.CTkOptionMenu(
            self.tab_val,
            values=["Ожидание данных..."],
            command=self.on_file_select,
            width=450,
            font=("Arial", 14),
        )
        self.file_selector.pack(pady=5)

        self.val_edit = ctk.CTkTextbox(
            self.tab_val, width=900, height=350, font=("Consolas", 12)
        )
        self.val_edit.pack(pady=10)

        btn_frame = ctk.CTkFrame(self.tab_val, fg_color="transparent")
        btn_frame.pack(pady=10)

        self.btn_save_val = ctk.CTkButton(
            btn_frame,
            text="Применить и Сохранить",
            fg_color="#2c6e49",
            command=self.save_validation_changes,
        )
        self.btn_save_val.pack(side="left", padx=10)

        self.btn_single_qr = ctk.CTkButton(
            btn_frame,
            text="Создать QR",
            fg_color="#b35900",
            command=self.generate_single_qr,
        )
        self.btn_single_qr.pack(side="left", padx=10)

        self.btn_export_agent1 = ctk.CTkButton(
            btn_frame,
            text="Excel (Текущий файл)",
            command=self.export_agent1_excel,
        )
        self.btn_export_agent1.pack(side="left", padx=10)

        self.btn_train_shadow = ctk.CTkButton(
            btn_frame,
            text="Обучить Shadow",
            fg_color="#1f538d",
            command=self.train_shadow_logic,
        )
        self.btn_train_shadow.pack(side="left", padx=10)

    def update_val_ui(self):
        """Обновляет выпадающий список после окончания оцифровки"""
        if self.session_results:
            files = list(self.session_results.keys())
            self.file_selector.configure(values=files)
            self.file_selector.set(files[0])
            self.on_file_select(files[0])  # Загружаем первый файл в редактор
        else:
            self.file_selector.configure(values=["Нет данных"])
            self.file_selector.set("Нет данных")
            self.val_edit.delete("0.0", "end")
            self.val_edit.insert("0.0", "[\n  // Оборудование не найдено\n]")

    def on_file_select(self, selected_file):
        """Срабатывает при выборе файла в выпадающем списке"""
        if selected_file == "Нет данных" or selected_file not in self.session_results:
            return

        self.current_val_file = selected_file
        data = self.session_results[selected_file]

        self.val_edit.delete("0.0", "end")
        self.val_edit.insert("0.0", json.dumps(data, ensure_ascii=False, indent=4))

    def save_validation_changes(self):
        """Сохраняет правки только для текущего выбранного файла"""
        if not self.current_val_file:
            return messagebox.showwarning("Внимание", "Файл не выбран.")

        try:
            raw_text = self.val_edit.get("0.0", "end").strip()
            updated_data = json.loads(raw_text)

            if isinstance(updated_data, dict) and "items" in updated_data:
                updated_data = updated_data["items"]
            elif not isinstance(updated_data, list):
                updated_data = [updated_data]

            # Сохраняем в память приложения
            self.session_results[self.current_val_file] = updated_data

            # Сохраняем на диск индивидуальным файлом
            save_dir = os.path.join("data", "parsed_passports")
            os.makedirs(save_dir, exist_ok=True)

            clean_name = self.current_val_file.replace(".json", "")
            save_path = os.path.join(save_dir, f"VALIDATED_{clean_name}.json")

            with open(save_path, "w", encoding="utf-8") as f:
                json.dump({"items": updated_data}, f, ensure_ascii=False, indent=4)

            messagebox.showinfo(
                "Успех",
                f"Изменения сохранены!\n\nГотовый JSON лежит здесь:\n{save_path}",
            )

        except json.JSONDecodeError as e:
            messagebox.showerror(
                "Ошибка JSON", f"Не удалось сохранить: проверьте синтаксис.\n{e}"
            )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Что-то пошло не так: {e}")

    def export_agent1_excel(self):
        """Экспорт в Excel только для данных в текстовом поле"""
        try:
            current_data = json.loads(self.val_edit.get("0.0", "end"))

            if isinstance(current_data, dict) and "items" in current_data:
                current_data = current_data["items"]
            elif not isinstance(current_data, list):
                current_data = [current_data]

            items = [NomenclatureItem(**item) for item in current_data]
            doc_to_export = ExtractedDocument(items=items)

            output_path = export_to_excel(
                doc_to_export,
                f"Экспорт_{self.current_val_file.replace('.json', '')}.xlsx",
            )
            if output_path:
                messagebox.showinfo("Готово", f"Таблица Excel создана:\n{output_path}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка генерации Excel: {e}")

    def generate_single_qr(self):
        """QR для первого элемента из выбранного файла"""
        try:
            current_data = json.loads(self.val_edit.get("0.0", "end"))
            item = (
                current_data[0]
                if isinstance(current_data, list)
                else current_data.get("items", [{}])[0]
            )

            if not item or "name" not in item:
                return messagebox.showwarning("Ошибка", "Не найдены данные прибора.")

            qr_path = generate_label(item, "data/exports/labels")
            self.show_qr_popup(qr_path)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать QR: {e}")

    def show_qr_popup(self, image_path):
        popup = ctk.CTkToplevel(self)
        popup.title("Готовая этикетка")
        popup.geometry("350x450")
        popup.attributes("-topmost", True)
        ctk.CTkLabel(
            popup, text="Этикетка успешно сгенерирована!", text_color="green"
        ).pack(pady=10)
        img = ctk.CTkImage(light_image=Image.open(image_path), size=(280, 350))
        ctk.CTkLabel(popup, image=img, text="").pack(pady=10)

    def train_shadow_logic(self):
        """Обучает Shadow Agent на основе текущего выбранного файла"""
        if not self.current_val_file:
            return messagebox.showwarning("Внимание", "Нет данных для сравнения.")

        try:
            human_json = json.loads(self.val_edit.get("0.0", "end"))
            human_formatted = {
                "items": human_json if isinstance(human_json, list) else [human_json]
            }

            # Берем оригинальный текст и ИИ-черновик
            original_text = self.raw_ocr_results[self.current_val_file]
            ai_original_json = self.ai_raw_outputs[self.current_val_file]

            shadow = ShadowAgent()
            threading.Thread(
                target=shadow.process_correction,
                args=(original_text, ai_original_json, human_formatted),
                daemon=True,
            ).start()

            messagebox.showinfo(
                "Обучение",
                f"Shadow Agent начал анализ расхождений для файла {self.current_val_file}...",
            )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при запуске обучения: {e}")

    # АГЕНТ 2 + ЭКСПОРТ
    def setup_build_tab(self):
        ctk.CTkLabel(
            self.tab_build, text="Сборка шкафа и Аудит", font=("Arial", 22, "bold")
        ).pack(pady=10)

        btn_frame = ctk.CTkFrame(self.tab_build, fg_color="transparent")
        btn_frame.pack(pady=5)

        ctk.CTkButton(
            btn_frame, text="Загрузить План (ТЗ)", command=self.load_plan
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            btn_frame,
            text="Выбрать паспорта (Факт)",
            command=self.load_passports_for_cabinet,
        ).pack(side="left", padx=10)
        ctk.CTkButton(
            btn_frame,
            text="Запустить Агент 2",
            fg_color="orange",
            command=self.run_audit,
        ).pack(side="left", padx=10)

        self.audit_box = ctk.CTkTextbox(
            self.tab_build, width=950, height=300, font=("Consolas", 13)
        )
        self.audit_box.pack(pady=10)
        self.audit_box.insert("0.0", "Ожидание данных для сборки шкафа...")

        self.qr_label = ctk.CTkLabel(self.tab_build, text="")
        self.qr_label.pack(pady=10)

    def load_plan(self):
        file = filedialog.askopenfilename(
            title="Выберите JSON файл плана (ТЗ)", filetypes=[("JSON Files", "*.json")]
        )
        if file:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    self.expected_plan = json.load(f)
                if (
                    isinstance(self.expected_plan, dict)
                    and "items" in self.expected_plan
                ):
                    self.expected_plan = self.expected_plan["items"]
                elif not isinstance(self.expected_plan, list):
                    self.expected_plan = [self.expected_plan]
                self.audit_box.insert(
                    "end", f"\nПлан (ТЗ) загружен: {len(self.expected_plan)} позиций."
                )
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось загрузить план: {e}")

    def load_passports_for_cabinet(self):
        files = filedialog.askopenfilenames(
            title="Выберите JSON файлы", filetypes=[("JSON Files", "*.json")]
        )
        if files:
            self.cabinet_passports = []
            for f in files:
                try:
                    with open(f, "r", encoding="utf-8") as file:
                        data = json.load(file)
                        if isinstance(data, dict) and "items" in data:
                            self.cabinet_passports.extend(data["items"])
                        elif isinstance(data, list):
                            self.cabinet_passports.extend(data)
                        else:
                            self.cabinet_passports.append(data)
                except Exception as e:
                    print(f"Ошибка чтения {f}: {e}")
            self.audit_box.insert(
                "end",
                f"\nФактических паспортов загружено: {len(self.cabinet_passports)}. Готово к аудиту.",
            )

    def run_audit(self):
        if not getattr(self, "expected_plan", None):
            return messagebox.showwarning("ОТК", "Загрузите План (ТЗ)!")
        if not self.cabinet_passports:
            return messagebox.showwarning("ОТК", "Загрузите паспорта (Факт)!")

        agent2 = CabinetAgent(cabinet_name="Шкаф MIREA", cabinet_sn="SN-001")
        agent2.set_expected_plan(self.expected_plan)
        agent2.cabinet_data["found_items"] = []
        agent2.add_found_passports(self.cabinet_passports)

        report = agent2.run_audit()
        self.audit_box.delete("0.0", "end")

        if report:
            status = (
                "КОМПЛЕКТАЦИЯ В НОРМЕ" if report.is_complete else "ОБНАРУЖЕНЫ ОШИБКИ"
            )
            self.audit_box.insert(
                "end", f"Статус: {status}\n\nВердикт: {report.feedback_for_agent_1}\n"
            )
            if report.missing_items:
                self.audit_box.insert(
                    "end", f"\nНе хватает: {', '.join(report.missing_items)}"
                )
            if report.extra_items:
                self.audit_box.insert(
                    "end", f"\nЛишние позиции: {', '.join(report.extra_items)}"
                )
        else:
            self.audit_box.insert("end", "Не удалось сформировать отчет аудита.")

        qr_path = generate_label(
            {
                "name": agent2.cabinet_name,
                "serial_number": agent2.cabinet_sn,
                "article": "Сборка завершена",
            },
            "data/exports/labels",
        )
        qr_img = ctk.CTkImage(light_image=Image.open(qr_path), size=(180, 180))
        self.qr_label.configure(image=qr_img)

        items = [NomenclatureItem(**item) for item in self.cabinet_passports]
        doc_to_export = ExtractedDocument(items=items)
        export_to_excel(doc_to_export, "Спецификация_Шкафа.xlsx")
        messagebox.showinfo("Готово", "Аудит завершен. Файлы сохранены в data/exports/")

    def write_log(self, message):
        self.after(0, lambda: self.ocr_log.insert("end", f"{message}\n"))
        self.after(0, lambda: self.ocr_log.see("end"))


if __name__ == "__main__":
    app = GazpromApp()
    app.mainloop()
