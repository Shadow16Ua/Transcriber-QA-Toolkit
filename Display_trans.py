import os
from groq import Groq

# Ініціалізація клієнта (ключ береться зі змінних середовища або встав сюди замість os.environ)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Системний промпт із жорсткими правилами (скорочено — менше токенів = менше шансів впертись у TPM ліміт)
SYSTEM_PROMPT = """You are a strict text normalization assistant for Polish audio transcriptions.
Twój cel to stworzenie idealnego "Display Trans".
 
ZASADY ABSOLUTNE (STRICT RULES):
1. ZACHOWAJ KAŻDE SŁOWO: Nie dodawaj, nie usuwaj i nie poprawiaj słów. Powtórzenia (np. "tak tak"), zająknięcia (np. "poś posiada") i słowa-pasożyty (np. "fill", "yyy") MUSZĄ zostać dokładnie tak, jak w oryginale. Nie używaj skrótów (np. "tak zwany" nie może stać się "tzw.").
2. PUNKTUACJA: Dodaj odpowiednie przecinki, kropki, znaki zapytania, aby podzielić tekst na logiczne zdania.
3. WIELKIE LITERY: Zaczynaj zdania z wielkiej litery. Używaj wielkich liter dla nazw własnych (np. Polska, Niemcy, Amadeusz, Prawo i Sprawiedliwość).
4. LICZBY (ITN): Zamień wszystkie liczby zapisane słownie na cyfry (np. "dwadzieścia pięć" -> "25", "sto tysięcy" -> "100 000", "pięć procent" -> "5%").
 
Nie podawaj żadnych argumentów, przemyśleń ani wyjaśnień. Zacznij od razu od sformatowanego tekstu.
"""
 
# Один короткий приклад замість трьох — економить токени
EXAMPLES = [
    {"role": "user", "content": "tak tak wiem że to fill że to głupie ale no dwadzieścia pięć procent"},
    {"role": "assistant", "content": "Tak, tak, wiem, że to fill, że to głupie, ale no, 25%."},
]
 
def format_display_trans(raw_text: str) -> str:
    if not raw_text or not raw_text.strip():
        return ""
 
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(EXAMPLES)
    messages.append({"role": "user", "content": raw_text})
 
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            temperature=0.1,
            max_tokens=4096,  # більше запасу — reasoning-модель витрачає токени і на "думки"
            reasoning_effort="low",  # менше reasoning-токенів іде на роздуми, більше лишається на відповідь
        )
 
        choice = response.choices[0]
        content = choice.message.content
 
        if not content:
            print(f"[DEBUG] Finish reason: {choice.finish_reason}")
            if hasattr(choice.message, "reasoning_content") and choice.message.reasoning_content:
                print(f"[DEBUG] Reasoning: {choice.message.reasoning_content[:200]}...")
            return "Помилка: Пустий вивід (можливо не вистачило max_tokens на reasoning)."
 
        return content.strip()
 
    except Exception as e:
        return f"Помилка API: {e}"
 
# --- Тестуємо ---
if __name__ == "__main__":
    test_segment = ""
    print("-" * 40)
    print("DISPLAY TRANS:\n", format_display_trans(test_segment))