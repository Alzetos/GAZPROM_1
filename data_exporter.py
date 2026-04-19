import os
import pandas as pd
from agent1 import ExtractedDocument


def export_to_excel(
    extracted_data: ExtractedDocument, output_filename: str = "passport_data.xlsx"
) -> str:
    export_dir = os.path.join("data", "exports")
    os.makedirs(export_dir, exist_ok=True)

    output_path = os.path.join(export_dir, output_filename)

    main_table_rows = []
    specs_table_rows = []

    for item in extracted_data.items:
        main_table_rows.append(
            {
                "Код позиции": item.position_code,
                "Наименование": item.name,
                "Артикул/Марка": item.article,
                "Ед. изм.": item.unit,
                "Количество": item.quantity,
                "Серийный номер": item.serial_number,
                "Страница (Источник)": item.source_page,
            }
        )

        for spec in item.specifications:
            specs_table_rows.append(
                {
                    "Наименование": item.name,
                    "Серийный номер": item.serial_number,
                    "Параметр": spec.param_name,
                    "Значение": spec.param_value,
                    "Страница (Источник)": spec.source_page,
                }
            )

    df_main = pd.DataFrame(main_table_rows)
    df_specs = pd.DataFrame(specs_table_rows)

    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_main.to_excel(writer, sheet_name="Основная", index=False)

            if not df_specs.empty:
                df_specs.to_excel(writer, sheet_name="Характеристики", index=False)

        print(f"Данные успешно сохранены в: {output_path}")
        return output_path

    except Exception as e:
        print(f"Ошибка при сохранении Excel: {e}")
        return ""
