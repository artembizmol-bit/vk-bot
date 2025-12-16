import os
import time
import random
import json
import logging
import requests
import re

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

logging.basicConfig(level=logging.INFO)

VK_TOKEN = os.environ.get("VK_TOKEN")
YANDEX_FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "")
YANDEX_IAM_TOKEN = os.environ.get("YANDEX_IAM_TOKEN", "")

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

users = {}

def human_delay(min_s=1.5, max_s=4):
    time.sleep(random.uniform(min_s, max_s))

def typing(user_id):
    try:
        vk.messages.setActivity(user_id=user_id, type="typing")
    except:
        pass

def is_quality_lead(history):
    """Фильтр КВАЛ. лидов"""
    if len(history) < 3:
        return True
    
    texts = [h["text"].lower() for h in history]
    all_text = " ".join(texts)
    
    # ❌ Тролли
    bad_patterns = [r"секс|пизд|ху[йя]", r"заебись|пиздец", r"1|2|3|4|5", r"привет|пока|тест|бот"]
    for pattern in bad_patterns:
        if re.search(pattern, all_text):
            return False
    
    # ✅ Серьёзные
    good_indicators = ["руб", "моск|питер", "взросл|дети", "июн|июл", "сочи|турци"]
    good_count = sum(1 for ind in good_indicators if ind in all_text)
    return good_count >= 1

def get_yandexgpt_next_question(user_text, history_context):
    """🤖 ИИ ТУРАГЕНТ — анализирует и задаёт вопрос"""
    if not YANDEX_FOLDER_ID or not YANDEX_IAM_TOKEN:
        return get_smart_fallback(user_text, history_context)
    
    try:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
            "x-folder-id": YANDEX_FOLDER_ID,
            "Content-Type": "application/json"
        }
        context_summary = " ".join([h["text"] for h in history_context[-5:]])
        
        messages = [
            {
                "role": "system",
                "text": """Ты живой турагент. Задавай ТОЛЬКО ОДИН умный следующий вопрос.
ПРАВИЛА:
1. НИКОГДА не говори про цены/отели/рейсы
2. Анализируй контекст и продолжай логично
3. Говори естественно: "Понял", "Окей", "Смотри"
4. Если тролль — предлагай созвон"""
            },
            {
                "role": "user",
                "text": f"""Контекст диалога: {context_summary}
Последний ответ клиента: "{user_text}"

Задай один естественный следующий вопрос."""
            }
        ]
        
        data = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite:latest",
            "completionOptions": {
                "stream": False,
                "temperature": 0.4,
                "maxTokens": 120
            },
            "messages": messages
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=12)
        if response.status_code == 200:
            result = response.json()
            ai_text = result['result']['alternatives'][0]['message']['text'].strip()
            # Фильтр галлюцинаций
            if "?" in ai_text and len(ai_text) < 180 and "руб" not in ai_text.lower():
                return ai_text
    except Exception as e:
        logging.error(f"YandexGPT error: {e}")
    
    return get_smart_fallback(user_text, history_context)

def get_smart_fallback(user_text, history):
    """🧠 Умный резерв без ИИ"""
    text_lower = user_text.lower()
    recent = [h["text"].lower() for h in history[-4:]]
    
    # Направления пойманы
    directions = ["турци", "египт", "росси", "сочи", "тур"]
    if any(d in " ".join(recent) for d in directions):
        return "Когда примерно планируете вылетать?"
    
    # Пляж/море
    if "пляж" in text_lower or "море" in text_lower:
        return "Из какого города удобнее вылетать?"
    
    # Последовательность
    if not any("человек" in h for h in recent):
        return "Сколько человек поедет?"
    if not any("когда|дата" in h for h in recent):
        return "Когда примерно вылетать удобно?"
    if not any("бюджет|деньги" in h for h in recent):
        return "Какой бюджет ориентировочно?"
    
    return "Что ещё важно для вас в поездке?"

def needs_call(text):
    return any(kw in text.lower() for kw in ["билет", "отель", "цена", "купить", "конкретно"])

def get_user_state(user_id):
    if user_id not in users:
        users[user_id] = {"history": [], "data": {}, "stage": "discovery"}
    return users[user_id]

def save_lead(user_id, reason=""):
    state = users[user_id]
    fname = f"lead_{user_id}_{int(time.time())}.json"
    state["lead_reason"] = reason
    try:
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        logging.info(f"✅ Lead {reason}: {fname}")
    except:
        pass

def send(user_id, text, keyboard=None):
    typing(user_id)
    human_delay()
    vk.messages.send(user_id=user_id, message=text, keyboard=keyboard, random_id=0)

def main_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button("Продолжить", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("Созвониться", color=VkKeyboardColor.POSITIVE)
    kb.add_button("Оставить номер", color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()

print("🚀 VK ИИ ТУРАГЕНТ v5.1 — YandexGPT + Smart Filter")

# ГЛАВНЫЙ ЦИКЛ
for event in longpoll.listen():
    if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
        continue

    user_id = event.user_id
    user_text = event.text.strip()
    
    if not user_text or len(user_text) < 2:
        continue

    state = get_user_state(user_id)
    history = state["history"]
    
    # История
    history.append({"text": user_text, "timestamp": time.time()})
    if len(history) > 20:
        history.pop(0)
    
    text_lower = user_text.lower()
    
    # ❌ КОНКРЕТИКА → СОЗВОН
    if needs_call(user_text):
        msg = "Нужна конкретика? Давайте созвонимся — так быстрее всё подберём."
        send(user_id, msg, main_keyboard())
        save_lead(user_id, "concrete")
        continue
    
    # ❌ ТРОЛЛИ → СОЗВОН ПОСЛЕ 4 сообщений
    if len(history) >= 4 and not is_quality_lead(history):
        msg = "Давайте живым разговором разберёмся. Оставьте номер — перезвоню через 15 мин."
        send(user_id, msg, main_keyboard())
        save_lead(user_id, "troll_filter")
        continue
    
    # ✅ КОМАНДЫ ЛИДОВ
    if any(w in text_lower for w in ["созвони", "номер", "телефон"]):
        msg = "Отлично! Напишите номер и удобное время — перезвоню быстро."
        send(user_id, msg)
        save_lead(user_id, "phone")
        continue
    
    # ✅ СТАРТ
    if any(w in text_lower for w in ["тур", "поезд", "отдых", "начать"]):
        state["history"] = []
        msg = "Давайте подберём поездку. Куда примерно хотите и когда можете?"
        send(user_id, msg)
        continue
    
    # 🤖 ИИ ТУРАГЕНТ — ГЛАВНАЯ ЛОГИКА
    next_question = get_yandexgpt_next_question(user_text, history)
    
    confirmations = [
        "Понял вас.", "Окей, принял.", "Хорошо.", "Ясно.", 
        "Записал.", "Понятно.", "Смотри, учту."
    ]
    
    msg = f"{random.choice(confirmations)}\n\n{next_question}"
    send(user_id, msg)
    
    # ✅ САЙВ КВАЛ. ЛИДОВ
    if len(history) >= 5 and is_quality_lead(history):
        save_lead(user_id, "quality")
