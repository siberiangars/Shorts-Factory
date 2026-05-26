"""
Script generation via Claude API — v3.

Ключевые улучшения:
- TTS-оптимизация: все цифры прописью, аббревиатуры расшифрованы
- Пост-обработка: автоматическая замена цифр → слова
- B-roll keywords: конкретные, тёмный/медицинский стиль (BioBase12)
- System/user разделение, ротация хуков, валидация
"""
import json
import random
import re
from typing import TYPE_CHECKING

import anthropic
import structlog

from config import get_settings
from pipeline.errors import PipelineError
from utils.cost import claude_cost_usd

if TYPE_CHECKING:
    from models.channel import Channel
    from models.topic import Topic

log = structlog.get_logger()

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
Ты — профессиональный сценарист коротких видео для YouTube Shorts. \
Специализация: здоровье, медицина, биохакинг, долголетие, питание.

━━━ КРИТИЧЕСКИ ВАЖНО: ТЕКСТ ЧИТАЕТ НЕЙРОСЕТЬ (TTS) ━━━

Текст в full_text будет озвучен голосовым ИИ. Поэтому:

ЗАПРЕЩЕНО в full_text:
✗ Цифры: не "2", не "30%", не "40 лет" — пиши: "два", "тридцать процентов", "сорока лет"
✗ Аббревиатуры: не "ВОЗ", "ТТГ", "ЛПНП" — пиши полностью: "Всемирная организация здравоохранения"
✗ Символы: нет "%", "/", "–", "№", "°C" — пиши словами: "процентов", "на", "тире", "градусов"
✗ Сокращения: не "мг", "мл", "г", "кг" — пиши: "миллиграммов", "миллилитров", "граммов"
✗ Скобки (в TTS это пауза): не (исследование 2023) — убери или перефрази
✗ Перечисление через запятую без глаголов: добавь связки

РАЗРЕШЕНО и приветствуется:
✓ Запятые для естественных пауз
✓ Многоточие для паузы: "И тогда... всё изменилось."
✓ Вопросы как пауза перед ответом: "Почему? Потому что..."
✓ Разговорные обороты: "Смотри...", "Вот что важно:", "Но есть нюанс."

━━━ ПРАВИЛА КОНТЕНТА ━━━
• Длина full_text: сто пятьдесят — двести двадцать слов (шестьдесят–девяносто секунд)
• Каждое предложение несёт смысл — никакой воды, вступлений «всем привет»
• Конкретика: механизмы действия, названия веществ, цифры (прописью!)
• Разговорный, но не примитивный — как умный друг-врач
• Последняя фраза: «Это образовательный материал, не медицинская рекомендация.»

━━━ ТИПЫ ХУКОВ ━━━
1. Шок: «Семьдесят процентов людей не знают, что...»
2. Парадокс: «Этот витамин снижает риск рака — но большинство врачей молчат»
3. История: «Мой пациент десять лет жил с этим, не зная причины»
4. Вопрос: «Ты уверен, что твои анализы в норме?»
5. Факт-удивление: «За восемь часов сна мозг выводит два литра токсинов»

━━━ SEEDANCE 2.0 VIDEO PROMPTS (КРИТИЧНО!) ━━━
Поле broll_keywords = ПРОМПТЫ для AI видео-генерации Seedance 2.0 от ByteDance.
Это НЕ просто слова — это полные кинематографические описания сцен на английском.

ФОРМУЛА каждого промпта:
[Camera move] + [Subject detail] + [Technical quality] + [Background] + [Lighting] + [Mood]

ПРАВИЛЬНЫЕ примеры (именно такой формат):
✓ "Slow orbital camera shot around photorealistic 3D anatomical human heart beating gently, pure black background, dramatic warm red subsurface lighting, cinematic 4K medical visualization"
✓ "Macro extreme close-up of magnesium mineral crystals dissolving slowly, pure black background, cool blue-white crystalline glow, bokeh depth of field, slow motion cinematic"
✓ "Cinematic push-in toward glowing human brain neurons firing electric blue pulses, pure black background, bioluminescent glow, 4K scientific visualization"
✓ "Blood cells flowing through artery in slow motion, microscope macro view, pure black background, red glowing cells with dark plasma, cinematic medical 4K"
✓ "Elderly doctor hands with stethoscope, dramatic Rembrandt lighting, dark studio background, warm cinematic portrait, professional medical atmosphere"
✓ "White supplement capsules floating in slow motion, macro close-up, pure black background, clinical blue-white product lighting, depth of field, cinematic"
✓ "DNA double helix slowly rotating, glowing blue-green molecular bonds, pure black background, bioluminescent scientific animation, 4K cinematic"

ПЛОХИЕ (никогда):
✗ "magnesium supplement" — без описания сцены
✗ "person sleeping" — неконкретно
✗ "health wellness" — абстрактно

Генерируй РОВНО 7 промптов, каждый связан с темой видео, по формуле выше.

━━━ ФОРМАТ ОТВЕТА ━━━
Только валидный JSON без markdown.\
"""

# ── User prompt template ──────────────────────────────────────────────────────
_USER_TEMPLATE = """\
ЗАДАЧА: напиши сценарий YouTube Short.

ТЕМА: {topic_title}
КОНТЕКСТ: {topic_brief}
{persona_block}
ТИП ХУКА: {hook_type}
ВАРИАЦИЯ: {random_seed}

Верни ТОЛЬКО валидный JSON:
{{
  "title": "Заголовок (до восьмидесяти символов, цифры ПРОПИСЬЮ, с магнит-словом)",
  "hook": "Первые два предложения. ВСЕ ЦИФРЫ ПРОПИСЬЮ.",
  "body": "Основная часть. ВСЕ ЦИФРЫ И АББРЕВИАТУРЫ РАСПИСАНЫ СЛОВАМИ.",
  "cta": "Вопрос для комментариев (без слова лайк, цифры прописью)",
  "full_text": "ПОЛНЫЙ текст для озвучки. КРИТИЧЕСКИ: ни одной цифры, ни одного символа процента, ни одной аббревиатуры. Только слова.",
  "tags": ["до десяти тегов на русском"],
  "description": "Три-пять строк описания плюс хештеги",
  "broll_keywords": ["7 Seedance промптов по формуле: [camera move]+[subject]+[quality]+[black background]+[lighting]+[mood], каждый 15-25 слов"],
  "estimated_duration_sec": 75.0
}}\
"""

_HOOK_TYPES = [
    "шокирующая статистика (прописью)",
    "парадоксальный факт",
    "личная история из практики",
    "провокационный вопрос",
    "цифра-удивление (прописью) плюс неожиданный вывод",
    "распространённое заблуждение",
    "сравнение-аналогия",
]

_REQUIRED_FIELDS = {
    "title", "hook", "body", "cta", "full_text",
    "tags", "description", "broll_keywords", "estimated_duration_sec"
}

# ── TTS post-processor ────────────────────────────────────────────────────────

_RU_NUMS = {
    0: "ноль", 1: "один", 2: "два", 3: "три", 4: "четыре", 5: "пять",
    6: "шесть", 7: "семь", 8: "восемь", 9: "девять", 10: "десять",
    11: "одиннадцать", 12: "двенадцать", 13: "тринадцать", 14: "четырнадцать",
    15: "пятнадцать", 16: "шестнадцать", 17: "семнадцать", 18: "восемнадцать",
    19: "девятнадцать", 20: "двадцать", 30: "тридцать", 40: "сорок",
    50: "пятьдесят", 60: "шестьдесят", 70: "семьдесят", 80: "восемьдесят",
    90: "девяносто", 100: "сто", 200: "двести", 300: "триста", 400: "четыреста",
    500: "пятьсот", 600: "шестьсот", 700: "семьсот", 800: "восемьсот",
    900: "девятьсот",
}


def _num_to_words(n: int) -> str:
    if n in _RU_NUMS:
        return _RU_NUMS[n]
    if n < 0:
        return "минус " + _num_to_words(-n)
    if n < 20:
        return _RU_NUMS.get(n, str(n))
    if n < 100:
        tens = (n // 10) * 10
        ones = n % 10
        return _RU_NUMS[tens] + (" " + _RU_NUMS[ones] if ones else "")
    if n < 1000:
        h = n // 100
        r = n % 100
        return _RU_NUMS[h * 100] + (" " + _num_to_words(r) if r else "")
    if n < 1_000_000:
        th = n // 1000
        r = n % 1000
        suffix = "тысяч"
        if th % 10 == 1 and th % 100 != 11:
            suffix = "тысяча"
        elif th % 10 in (2, 3, 4) and th % 100 not in (12, 13, 14):
            suffix = "тысячи"
        return _num_to_words(th) + " " + suffix + (" " + _num_to_words(r) if r else "")
    return str(n)


def _tts_postprocess(text: str) -> str:
    """Convert digits/symbols to speech-friendly Russian words."""
    if not text:
        return text

    # Percent: "30%" → "тридцать процентов"
    def replace_percent(m):
        try:
            return _num_to_words(int(m.group(1))) + " процентов"
        except Exception:
            return m.group(0)
    text = re.sub(r"(\d+)\s*%", replace_percent, text)

    # Ranges: "16/8" → "шестнадцать на восемь"
    def replace_slash_nums(m):
        try:
            return _num_to_words(int(m.group(1))) + " на " + _num_to_words(int(m.group(2)))
        except Exception:
            return m.group(0)
    text = re.sub(r"(\d+)/(\d+)", replace_slash_nums, text)

    # Units (before plain number replacement)
    unit_map = [
        (r"(\d+)\s*мг", lambda m: _num_to_words(int(m.group(1))) + " миллиграммов"),
        (r"(\d+)\s*мл", lambda m: _num_to_words(int(m.group(1))) + " миллилитров"),
        (r"(\d+)\s*кг", lambda m: _num_to_words(int(m.group(1))) + " килограммов"),
        (r"(\d+)\s*г\b", lambda m: _num_to_words(int(m.group(1))) + " граммов"),
        (r"(\d+)\s*км", lambda m: _num_to_words(int(m.group(1))) + " километров"),
        (r"(\d+)\s*°[Cc]", lambda m: _num_to_words(int(m.group(1))) + " градусов"),
        (r"(\d+)\s*лет\b", lambda m: _num_to_words(int(m.group(1))) + " лет"),
        (r"(\d+)\s*мин\b", lambda m: _num_to_words(int(m.group(1))) + " минут"),
        (r"(\d+)\s*сек\b", lambda m: _num_to_words(int(m.group(1))) + " секунд"),
    ]
    for pattern, replacement in unit_map:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Plain numbers (1–9999)
    def replace_number(m):
        try:
            n = int(m.group(0))
            if n <= 9999:
                return _num_to_words(n)
            return m.group(0)
        except Exception:
            return m.group(0)
    text = re.sub(r"\b\d+\b", replace_number, text)

    # Common abbreviations
    abbr = {
        "ВОЗ": "Всемирная организация здравоохранения",
        "МРТ": "магнитно-резонансная томография",
        "ТТГ": "тиреотропный гормон",
        "ЛПНП": "липопротеины низкой плотности",
        "ЛПВП": "липопротеины высокой плотности",
        "ДНК": "дэ-эн-а",
        "РНК": "эр-эн-а",
        "АТФ": "аденозинтрифосфат",
        "ИМТ": "индекс массы тела",
        "ЦНС": "центральная нервная система",
        "ЖКТ": "желудочно-кишечный тракт",
    }
    for short, full in abbr.items():
        text = re.sub(r"\b" + short + r"\b", full, text)

    # Clean up extra spaces
    text = re.sub(r" {2,}", " ", text).strip()
    return text


# ── JSON extraction ───────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"No valid JSON: {text[:200]}")


def _validate(result: dict, topic_title: str) -> dict:
    missing = _REQUIRED_FIELDS - result.keys()
    if missing:
        raise ValueError(f"Missing fields: {missing}")
    if len(result.get("full_text", "")) < 80:
        raise ValueError("full_text too short")

    # Apply TTS post-processing to full_text
    result["full_text"] = _tts_postprocess(result.get("full_text", ""))

    # Ensure broll_keywords are in English and non-empty
    kws = result.get("broll_keywords", [])
    if not kws or all(any(c > '' for c in kw) for kw in kws):
        result["broll_keywords"] = [
            "human anatomy 3d render dark background",
            "medical pills capsules black macro",
            "brain neurons glowing dark",
            "blood cells microscope dark",
            "elderly doctor white coat studio",
        ]

    # Ensure tags list
    if not isinstance(result.get("tags"), list):
        result["tags"] = [topic_title.split()[0].lower()]

    # Duration
    try:
        result["estimated_duration_sec"] = float(result["estimated_duration_sec"])
    except (TypeError, ValueError):
        result["estimated_duration_sec"] = 75.0

    # Add #shorts to title
    title = result.get("title", "")
    if "#shorts" not in title.lower():
        result["title"] = title.rstrip() + " #shorts"

    return result


# ── Main function ─────────────────────────────────────────────────────────────

def generate_script(topic: "Topic", channel: "Channel") -> dict:
    settings = get_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    persona_block = ""
    if channel.persona_description:
        persona_block = f"\nПЕРСОНАЖ: {channel.persona_description}\nПиши от первого лица этого персонажа.\n"

    raw_template = channel.script_prompt_template or _USER_TEMPLATE

    # Escape braces, restore placeholders
    safe = raw_template.replace("{", "{{").replace("}", "}}")
    for key in ("topic_title", "topic_brief", "persona_block", "hook_type", "random_seed"):
        safe = safe.replace(f"{{{{{key}}}}}", f"{{{key}}}")

    hook_type = random.choice(_HOOK_TYPES)
    user_prompt = safe.format(
        topic_title=topic.title,
        topic_brief=topic.brief or "не указан",
        persona_block=persona_block,
        hook_type=hook_type,
        random_seed=random.randint(1000, 9999),
    )

    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text.strip()
            result = _extract_json(raw)
            result = _validate(result, topic.title)

            cost = claude_cost_usd(
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
            log.info("script_generated",
                     topic_id=topic.id, hook_type=hook_type,
                     words=len(result["full_text"].split()),
                     tokens_in=response.usage.input_tokens,
                     tokens_out=response.usage.output_tokens,
                     cost_usd=cost)
            result["_cost_usd"] = cost
            return result

        except (ValueError, json.JSONDecodeError) as exc:
            last_exc = exc
            log.warning("script_gen_retry", attempt=attempt, error=str(exc)[:100])
            hook_type = random.choice([h for h in _HOOK_TYPES if h != hook_type])

    raise PipelineError(
        "script_gen",
        f"Failed after 3 attempts: {last_exc}",
        last_exc,
    )
