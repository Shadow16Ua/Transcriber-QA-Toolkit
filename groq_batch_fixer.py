import json
import os
import glob
import re
import subprocess
import tempfile
import wave
import uuid
from pathlib import Path
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

AUDIO_FILES = glob.glob("*.wav")
AUDIO_PATH = AUDIO_FILES[0] if AUDIO_FILES else None

GUIDELINES = """
Правила транскрипції (укр., SpeechTX_FY26 - ОНОВЛЕНІ):
1. ПОЧАТОК І КІНЕЦЬ: Кожен сегмент ЗАВЖДИ починається з великої літери (або цифри). Кожен сегмент закінчується знаком (., ?, !).
2. ЧИСЛА ТА ТИСЯЧІ: 
   - АБСОЛЮТНО ВСІ числа перетворюй на цифри (напр. "двох синів" -> "2 синів").
   - Усі порядкові числа з дефісним закінченням (1-й, 2-го, 3-ю).
   - ТИСЯЧІ пишуться ПОВНІСТЮ ЦИФРАМИ (10000, 5000, а НЕ 10 тисяч).
   - СТОЛІТТЯ пишемо римськими цифрами БЕЗ ЗАКІНЧЕНЬ (XX століття).
   - Винятки словами: "по-перше", "по-друге", "двійка", "вдвічі".
3. МАТЕМАТИКА ТА ВАЛЮТА: Змінні латиницею (x1 = - 6). Валюта ПІСЛЯ значення ("10000 ₴", "50 $").
4. ОДИНИЦІ ВИМІРУ: Пиши повністю словами ("кілометрів", "сантиметрів").
5. НІКОЛИ не використовуй "#" чи "№", пиши слово "номер".
6. ПРЯМА МОВА ТА ЦИТАТИ (СУВОРО!): 
   - Якщо йде пряма мова або цитата, ОБОВ'ЯЗКОВО став двокрапку перед нею і виділяй її лапками-«ялинками» « ». 
   - Приклад: Тоді він сказав: «Не хочу!»
7. ТЕГИ <PName> ТА <UNKNOWN/> (СУВОРІ ПРОБІЛИ):
   - <PName> ставити ТІЛЬКИ на імена та прізвища людей (наприклад: <PName>Ісус</PName>, <PName>Тарас</PName>).
   - СУВОРО ЗАБОРОНЕНО ставити пробіли всередині тегу та перед знаками після нього! 
     ПРАВИЛЬНО: <PName>Тарас</PName>. або <UNKNOWN/>. 
     НЕПРАВИЛЬНО: <PName> Тарас </PName> . або <UNKNOWN/> .
   - На країни, міста, звичайні назви установ тег НЕ СТАВИТИ.
   - Після будь-якого тегу слово починається з ВЕЛИКОЇ ЛІТЕРИ, якщо це початок речення.
8. ТРИ ВИДИ ТИРЕ (СУВОРО!):
    - ДЕФІС (-): всередині слів БЕЗ ПРОБІЛІВ (інтернет-магазин, по-перше, 1-й).
    - КОРОТКЕ ТИРЕ (–): для діапазонів чисел, часу, маршрутів БЕЗ ПРОБІЛІВ (2025–2026, 10–15).
    - ДОВГЕ ТИРЕ (—): між словами у реченні З ПРОБІЛАМИ з обох боків (Наша мета — стабільність).
9. VERBATIM: Зберігай усі слова мовця строго так, як звучить (суржик, помилки не виправляти).
"""

EXAMPLES = """
### ПРИКЛАДИ (ЯК БУЛО -> ЯК МАЄ БУТИ):

--- 1. ПРЯМА МОВА, ЧИСЛА ТА ІМЕНА (<PName>) ---
❌ ПОМИЛКА: Тож у відповідь вони Ісусові сказали: «Не знаємо!» Тоді він промовив до них, і я не скажу вам, якою владою я це чиню. Як вам здається, один чоловік мав двох синів, і прийшовши до першого, сказав, син, іди попрацюй сьогодні у виноградах.
✅ ПРАВИЛЬНО: Тож у відповідь вони <PName>Ісусові</PName> сказали: «Не знаємо!» Тоді він промовив до них: «І я не скажу вам, якою владою я це чиню. Як вам здається? Один чоловік мав 2 синів. І, прийшовши до 1-го, сказав: «Сину, йди попрацюй сьогодні у винограднику».

--- 2. ТЕГИ ТА ПРОБІЛИ (БЕЗ ПРОБІЛІВ ВСЕРЕДИНІ ТА ПЕРЕД КРАПКОЮ!) ---
❌ ПОМИЛКА: шось <PName> Тарас </PName> . Потім <PName> Аліна </PName> продала золото.
✅ ПРАВИЛЬНО: шось <PName>Тарас</PName>. Потім <PName>Аліна</PName> продала золото.

❌ ПОМИЛКА: <UNKNOWN/> .
✅ ПРАВИЛЬНО: <UNKNOWN/>.

--- 3. ТИСЯЧІ ТА ВАЛЮТА ---
❌ ПОМИЛКА: Він отримав 10 тисяч гривень, а потім ще 5 тис доларів.
✅ ПРАВИЛЬНО: Він отримав 10000 ₴, а потім ще 5000 $.

--- 4. МАТЕМАТИКА ---
❌ ПОМИЛКА: Х помножити на у дорівнює 3072. Мінус 14, поділити на 7, дорівнює мінус 2, бо мінус 2, помножити на 7, дорівнює мінус 14. Мінус 0,6, поділити на мінус 0,2, дорівнює 3.
✅ ПРАВИЛЬНО: x * y = 3072. - 14 / 7 = - 2, бо - 2 * 7 = - 14. - 0,6 / - 0,2 = 3.

--- 5. ТИРЕ, ДЕФІСИ ТА ДІАПАЗОНИ ---
❌ ПОМИЛКА: за хвилин 30-40 або 10 - 15 сторінок. Наша мета - продажі.
✅ ПРАВИЛЬНО: за хвилин 30–40 або 10–15 сторінок. Наша мета — продажі.
"""

SYSTEM_PROMPT = f"""ТИ — СУВОРИЙ QA-АЛГОРИТМ. ТИ НЕ ЧАТ-БОТ! 
ТВОЯ ЄДИНА МЕТА: застосувати правила до тексту в JSON.
КАТЕГОРИЧНО ЗАБОРОНЕНО відповідати на питання в тексті, продовжувати думку мовця, генерувати свої коментарі або писати "Відповідь на цей випадок". 
ПРОСТО ПОВЕРНИ ВІДФОРМАТОВАНИЙ ТЕКСТ.

{GUIDELINES}

{EXAMPLES}

Тобі надійде JSON-масив об'єктів [{{ "id": N, "text": "..." }}, ...].
Поверни ЛИШЕ валідний JSON-масив такого самого формату з виправленим text, без жодних коментарів, без markdown-обгортки."""

HALLUCINATION_PHRASES = [
    "підписуйтесь на канал",
    "дякую за перегляд",
    "дякую за увагу",
    "субтитри створені",
    "відповідь на цей випадок",
    "ось виправлений",
    "www.",
]

def is_likely_hallucination(text: str) -> bool:
    normalized = text.strip().lower().rstrip('.,!?').strip()
    if not normalized:
        return True
    for phrase in HALLUCINATION_PHRASES:
        if normalized == phrase or (len(normalized) < 60 and normalized.startswith(phrase)):
            return True
    return False

def get_audio_duration(file_path: str) -> float:
    try:
        with wave.open(file_path, 'rb') as f:
            return f.getnframes() / float(f.getframerate())
    except Exception as e:
        print(f"🚨 [Помилка читання wav]: {e}")
        return 0.0

def extract_audio_clip(audio_path: str, start: float, end: float, pad: float = 0.5) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    real_start = max(0.0, start - pad)
    duration = max((end + pad) - real_start, 0.1)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(real_start), "-i", audio_path, "-t", str(duration),
        "-ar", "16000", "-ac", "1", tmp.name
    ]
    subprocess.run(cmd, check=True)
    return tmp.name

def _whisper_call(audio_path: str, start: float, end: float) -> str:
    clip_path = extract_audio_clip(audio_path, start, end)
    try:
        with open(clip_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(clip_path), f.read()),
                model="whisper-large-v3",
                language="uk",
                response_format="text"
            )
    finally:
        os.unlink(clip_path)
    return str(transcription).strip()

def transcribe_with_whisper(audio_path: str, start: float, end: float) -> str:
    if not audio_path or not os.path.exists(audio_path):
        return ""
    try:
        text = _whisper_call(audio_path, start, end)
        if is_likely_hallucination(text):
            return ""
        return text
    except Exception as e:
        print(f"🚨 [КРИТИЧНА ПОМИЛКА API або Аудіо]: {e}")
        return ""

def validate_and_fix_locally(text: str) -> tuple[str, list[str]]:
    warnings = []
    stripped = text.strip()

    if not stripped:
        return stripped, warnings

    if "<PName>" in stripped:
        original = stripped
        stripped = re.sub(r'<PName>\s*(.*?)\s*</PName>', r'<PName>\1</PName>', stripped)
        if original != stripped:
            warnings.append("виправлено пробіли всередині <PName>")

    if ">" in stripped:
        original = stripped
        stripped = re.sub(r'(>)\s+([.,!?])', r'\1\2', stripped)
        if original != stripped:
            warnings.append("прибрано пробіл між тегом і знаком")

    if '#' in stripped or '№' in stripped:
        stripped = re.sub(r'[#№]\s*', 'номер ', stripped)

    original_thousands = stripped
    stripped = re.sub(r'\b(\d+)\s*тис(?:яч[аіиь]?)?\.?\b', r'\g<1>000', stripped)
    if original_thousands != stripped:
        warnings.append("слово 'тисяч' перетворено на нулі")

    def convert_century(match):
        val = int(match.group(1))
        roman_map = {1:'I', 2:'II', 3:'III', 4:'IV', 5:'V', 6:'VI', 7:'VII', 8:'VIII', 9:'IX', 10:'X',
                     11:'XI', 12:'XII', 13:'XIII', 14:'XIV', 15:'XV', 16:'XVI', 17:'XVII', 18:'XVIII', 19:'XIX', 20:'XX', 21:'XXI'}
        roman = roman_map.get(val, str(val))
        return f"{roman} столітт"

    stripped = re.sub(r'\b(\d{1,2})(?:-й|-е|-го|-му|-ім)?\s+столітт', convert_century, stripped)

    stripped = re.sub(r'(\d+)\s*[-—–]\s*(\d+)', r'\1–\2', stripped)
    
    if re.search(r'\s+[-–]\s+', stripped):
        stripped = re.sub(r'\s+[-–]\s+', ' — ', stripped)

    stripped = re.sub(r'\b[хХ](\d+)\b', r'x\1', stripped)
    stripped = re.sub(r'(?i)\bмініміксер\w*\b', lambda m: m.group(0).replace('міні', 'міні-').replace('Міні', 'Міні-'), stripped)

    patterns_currency = [
        (r'(\d+(?:\s+мільйон[а-я]*|\s+мільярд[а-я]*)?)\s+(?:гривень|гривні|гривня)', r'\1 ₴'),
        (r'(\d+(?:\s+мільйон[а-я]*|\s+мільярд[а-я]*)?)\s+(?:євро)', r'\1 €'),
        (r'(\d+(?:\s+мільйон[а-я]*|\s+мільярд[а-я]*)?)\s+(?:доларів|долари|долара|долар)', r'\1 $'),
    ]
    for pattern, replacement in patterns_currency:
        stripped = re.sub(pattern, replacement, stripped)

    # 🟢 ФІКС: Броньована локальна заміна математичних слів + видалення ком навколо них
    math_words = [
        (r'(?i),?\s*поділити на\s*,?', r' / '),
        (r'(?i),?\s*помножити на\s*,?', r' * '),
        (r'(?i),?\s*дорівнює\s*,?', r' = '),
        (r'(?i)\bмінус\s+(\d)', r'- \1'), # мінус 14 -> - 14
        (r'(?i)\bмінус\b', r'-'),         # просто мінус
        (r'(?i)\bплюс\b', r'+')
    ]
    for pattern, repl in math_words:
        stripped = re.sub(pattern, repl, stripped)

    # Видаляємо коми, які могли залишитися перед або після математичних знаків
    stripped = re.sub(r',\s*([-+*/=])', r' \1', stripped)
    stripped = re.sub(r'([-+*/=])\s*,', r'\1 ', stripped)

    if any(char in stripped for char in ['+', '=']):
        stripped = re.sub(r'\s*([+=])\s*', r' \1 ', stripped)

    stripped = re.sub(r'=\s*-\s*(\d)', r'= - \1', stripped)
    stripped = re.sub(r' {2,}', ' ', stripped)

    stripped = re.sub(r'\b[хХ]\b\s*([-+*=/])', r'x \1', stripped)
    stripped = re.sub(r'([-+*=/])\s*\b[хХ]\b', r'\1 x', stripped)
    stripped = re.sub(r'\b[уУ]\b\s*([-+*=/])', r'y \1', stripped)
    stripped = re.sub(r'([-+*=/])\s*\b[уУ]\b', r'\1 y', stripped)

    first_char = stripped[0]
    if first_char.isalpha() and first_char.islower():
        stripped = first_char.upper() + stripped[1:]

    stripped = re.sub(r',\s*\.', '.', stripped)
    if re.search(r'[,:;]\s*$', stripped):
        stripped = re.sub(r'[,:;]\s*$', '.', stripped)
    else:
        has_end = re.search(r'[.!?]\s*$', stripped)
        if not has_end:
            stripped = stripped + '.'
            
    stripped = re.sub(r'\s+\.$', '.', stripped)

    return stripped, warnings

def format_batch_with_groq(batch: list[dict]) -> list[dict]:
    payload = json.dumps(batch, ensure_ascii=False)
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
        )
        raw = chat_completion.choices[0].message.content.strip()
        raw = re.sub(r'^```json\s*|\s*```$', '', raw, flags=re.MULTILINE)
        return json.loads(raw)
    except Exception as e:
        print(f"  [Помилка форматування]: {e}")
        return batch

def chunked(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

def main():
    if not AUDIO_PATH or not os.path.exists(AUDIO_PATH):
        print(f"❌ Не знайдено аудіофайл: {AUDIO_PATH}")
        return

    json_files = [f for f in glob.glob("*.json") if not f.endswith("_cleaned.json")]
    if not json_files:
        print("Не знайдено нових JSON-файлів.")
        return

    BATCH_SIZE = 10
    total_audio_duration = get_audio_duration(AUDIO_PATH)

    for file_path in json_files:
        print(f"\n=== ОБРОБКА ФАЙЛУ: {file_path} ===")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        original_segments = data.get("segments", data) if isinstance(data, dict) else data
        original_segments = sorted(original_segments, key=lambda x: x.get("start", 0))

        final_segments = []
        to_process = []
        index_map = {}
        last_end = 0.0
        last_speaker = "S1"

        for i, seg in enumerate(original_segments):
            start = seg.get("start", 0)
            end = seg.get("end", 0)
            sid = seg.get("id", i)
            original_text = seg.get("text", "").strip()

            gap_duration = start - last_end
            if gap_duration > 0.5:
                gap_text = transcribe_with_whisper(AUDIO_PATH, last_end, start)
                if gap_text and re.search(r'[а-яА-Яa-zA-Z]', gap_text):
                    print(f"   ➕ [Знайдено пропущений текст]: {gap_text}")
                    new_sid = f"seg-gap-{uuid.uuid4().hex[:16]}"
                    new_seg = {
                        "id": new_sid,
                        "order": 0,
                        "start": round(last_end + 0.01, 3),
                        "end": round(start - 0.01, 3),
                        "speaker": last_speaker,
                        "text": gap_text
                    }
                    final_segments.append(new_seg)
                    to_process.append({"id": new_sid, "text": gap_text})
                    index_map[new_sid] = len(final_segments) - 1

            recognized_text = transcribe_with_whisper(AUDIO_PATH, start, end)
            duration = end - start

            if "<UNKNOWN" in original_text.upper():
                print(f"   -> [Збережено тег музики/шуму]: <UNKNOWN/>.")
                to_process.append({"id": sid, "text": "<UNKNOWN/>."})
            elif recognized_text:
                if original_text and len(recognized_text) < (len(original_text) * 0.4) and len(original_text) > 15:
                    print(f"   ⚠️ [Захист] Whisper з'їв текст. Врятовано оригінал: {original_text}")
                    to_process.append({"id": sid, "text": original_text})
                else:
                    if not original_text:
                        print(f"   ➕ [Додано текст у порожній сегмент]: {recognized_text}")
                    else:
                        print(f"   -> [Whisper розпізнав з аудіо]: {recognized_text}")
                    to_process.append({"id": sid, "text": recognized_text})
            elif original_text:
                print(f"   -> [Залишено оригінальний текст з JSON]: {original_text}")
                to_process.append({"id": sid, "text": original_text})
            else:
                if duration > 5.0:
                    print(f"   -> [Тиша > 5с] Залишено порожнім.")
                seg["text"] = ""

            final_segments.append(seg)
            if "<UNKNOWN" in original_text.upper() or recognized_text or original_text:
                index_map[sid] = len(final_segments) - 1

            last_end = max(last_end, end)
            last_speaker = seg.get("speaker", last_speaker)

        if total_audio_duration > last_end:
            tail_duration = total_audio_duration - last_end
            if tail_duration > 0.5:
                gap_text = transcribe_with_whisper(AUDIO_PATH, last_end, total_audio_duration)
                if gap_text and re.search(r'[а-яА-Яa-zA-Z]', gap_text):
                    print(f"   ➕ [Знайдено пропущений текст в кінці]: {gap_text}")
                    new_sid = f"seg-gap-{uuid.uuid4().hex[:16]}"
                    new_seg = {
                        "id": new_sid,
                        "order": 0,
                        "start": round(last_end + 0.01, 3),
                        "end": round(total_audio_duration, 3),
                        "speaker": last_speaker,
                        "text": gap_text
                    }
                    final_segments.append(new_seg)
                    to_process.append({"id": new_sid, "text": gap_text})
                    index_map[new_sid] = len(final_segments) - 1

        if to_process:
            print("\n📝 Запускаю форматування...")
            for batch in chunked(to_process, BATCH_SIZE):
                fixed_batch = format_batch_with_groq(batch)
                for item in fixed_batch:
                    item_sid = item.get("id")
                    if item_sid in index_map:
                        seg_idx = index_map[item_sid]
                        final_text, warns = validate_and_fix_locally(item.get("text", ""))
                        final_segments[seg_idx]["text"] = final_text

        final_segments = sorted(final_segments, key=lambda x: x.get("start", 0))
        for order_idx, segment in enumerate(final_segments):
            segment["order"] = order_idx + 1

        if isinstance(data, dict):
            data["segments"] = final_segments
        else:
            data = final_segments

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ Готово! Оновлено файл: {file_path}\n")

        try:
            if AUDIO_PATH and os.path.exists(AUDIO_PATH):
                os.remove(AUDIO_PATH)
            print("✨ Аудіофайл очищено, JSON готов до завантаження!\n")
        except Exception as cleanup_error:
            pass

if __name__ == "__main__":
    main()