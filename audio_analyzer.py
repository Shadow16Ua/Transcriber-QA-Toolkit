import json
import os
import glob
from pathlib import Path
from groq import Groq
import pymupdf4llm

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def load_pdf_guidelines() -> str:
    """
    Шукає всі .pdf файли у папці зі скриптом, 
    витягує з них текст зі збереженням таблиць (через Markdown) 
    і формує єдину базу знань.
    """
    knowledge_base = ""
    pdf_files = glob.glob("*.pdf")
    
    if not pdf_files:
        print("  [Увага]: Не знайдено PDF-файлів з гайдлайнами у поточній папці!")
        return ""

    print(f"📄 Знайдено PDF-гайдлайни: {pdf_files}. Витягую дані...")
    
    for file in pdf_files:
        try:
            # Магія pymupdf4llm: конвертує PDF з таблицями у чистий Markdown
            md_text = pymupdf4llm.to_markdown(file)
            knowledge_base += f"\n\n=== ОФІЦІЙНИЙ ГАЙДЛАЙН: {file} ===\n"
            knowledge_base += md_text
        except Exception as e:
            print(f"  [Помилка читання {file}]: {e}")
            
    return knowledge_base

def format_text_with_groq(text: str, knowledge_base: str) -> str:
    if not text or not text.strip():
        return text

    # Динамічний промпт із вбудованими PDF-гайдлайнами
    SYSTEM_PROMPT = f"""
    Ти професійний QA-редактор транскрипцій. 
    Твоє завдання — перевірити та виправити наданий текст СУВОРО на основі бази знань нижче.
    Особливу увагу звертай на таблиці з правилами ITN, форматування тегів та пунктуацію.
    
    БАЗА ЗНАНЬ (ГАЙДЛАЙНИ ПРОЄКТУ):
    {knowledge_base}

    ІНСТРУКЦІЯ ДЛЯ ДІЇ:
    1. Проаналізуй текст користувача.
    2. Знайди відповідні правила у базі знань (як ставити теги, скорочення, числа, пунктуацію).
    3. Виправ текст згідно з цими правилами.
    4. Поверни ЛИШЕ виправлений текст, без жодних коментарів, пояснень чи форматування (не використовуй markdown-блоки для коду у відповіді).
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
        )
        return chat_completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [Помилка Groq API]: {e}")
        return text

def main():
    # 1. Читаємо всі PDF один раз перед початком обробки JSON
    knowledge_base = load_pdf_guidelines()
    
    if not knowledge_base:
        print("❌ Роботу зупинено: поклади файли гайдлайнів (.pdf) у папку зі скриптом.")
        return

    json_files = [f for f in glob.glob("*.json") if not f.endswith("_cleaned.json")]
    
    if not json_files:
        print("Не знайдено нових JSON-файлів для обробки.")
        return

    for file_path in json_files:
        print(f"\n==========================================")
        print(f"   ОБРОБКА ФАЙЛУ: {file_path}")
        print(f"==========================================\n")
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        segments = data.get("segments", data) if isinstance(data, dict) else data
        
        if not isinstance(segments, list):
            print("Невідомий формат сегментів у JSON.")
            continue

        for seg in segments:
            seg_num = seg.get("order", seg.get("id", "?"))
            original_text = seg.get("text", "").strip()
            
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            duration = end - start

            # Правило 5+ секунд шуму
            if duration > 5.0 and not original_text:
                cleaned_text = "<UNKNOWN/>."
            elif original_text:
                # 2. Згодовуємо текст та PDF-базу знань моделі
                cleaned_text = format_text_with_groq(original_text, knowledge_base)
            else:
                cleaned_text = ""

            seg["text"] = cleaned_text

            print(f"--- [ Сегмент #{seg_num} | {duration:.1f}s ] ---")
            print(f"Оригінал : {original_text}")
            print(f"Виправлено: {cleaned_text}\n")

        path_obj = Path(file_path)
        output_name = f"{path_obj.stem}_cleaned{path_obj.suffix}"
        
        with open(output_name, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"------------------------------------------")
        print(f"✅ Готово! Збережено файл: {output_name}\n")

if __name__ == "__main__":
    main()