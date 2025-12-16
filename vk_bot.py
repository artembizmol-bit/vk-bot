import os
import time
import random
import json
import logging
import requests

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

logging.basicConfig(level=logging.INFO)

VK_TOKEN = os.environ.get("VK_TOKEN")
YANDEX_FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "")
YANDEX_IAM_TOKEN = os.environ.get("YANDEX_IAM_TOKEN", "")

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

users = {}

def human_delay(min_s=2, max_s=4):
    time.sleep(random.uniform(min_s, max_s))

def typing(user_id):
    try:
        vk.messages.setActivity(user_id=user_id, type="typing")
    except:
        pass

def get_yandexgpt_next_question(user_text, history_context):
    """🤖 ЧИСТЫЙ ИИ ТУРАГЕНТ"""
    if not YANDEX_FOLDER_ID or not YANDEX_IAM_TOKEN:
        return "Расскажите подробнее о поездке: куда, когда, с кем?"
    
    try:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
            "x-folder-id": YANDEX_FOLDER_ID,
            "Content-Type": "application/json"
        }
        
        context_summary = "\n".join([f"Клиент: {h['text']}" for h in history_context[-8:]])
        
        messages = [
            {
                "role": "system",
                "text": """Ты живой турагент с 10-летним опытом. 
                
ПРАВИЛА:
1. НИКОГДА не называй цены, отели, рейсы, ссылки
2. Задавай ТОЛЬКО ОДИН логичный следующий вопрос
3. Говори естественно: "Понял", "Окей", "Смотри"
4. Анализируй ВЕСЬ контекст диалога
5. Если конкретику просят — предлагай созвон
6. НЕ повторяй один и тот же вопрос
7. НИКОГДА не предлагай кнопки

Стиль: спокойный профессионал, который сначала понимает клиента."""
            },
            {
                "role": "user",
                "text": f"""Полный контекст диалога:
{context_summary}

Последний ответ клиента: "{user_text}"

Задай один естественный следующий вопрос (только текст, без кнопок)."""
            }
        ]
        
        data = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite:latest",
            "completionOptions": {
                "stream": False,
                "temperature": 0.5,
                "maxTokens": 150
            },
            "messages": messages
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            result = response.json()
            ai_text = result['result']['alternatives'][0]['message']['text'].strip()
            
            if len(ai_text) > 10 and len(ai_text) < 250 and "?" in ai_text:
                return ai_text
                
    except Exception as e:
        logging.error(f"YandexGPT error: {e}")
    
    return "Расскажите подробнее: куда хотите, когда, сколько человек?"

def get_user_state(user_id):
    if user_id not in users:
        users[user_id] = {"history": []}
    return users[user_id]

def save_conversation(user_id):
    state = users[user_id]
    fname = f"dialog_{user_id}_{int(time.time())}.json"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except:
        pass

def send(user_id, text):
    typing(user_id)
    human_delay()
    vk.messages.send(
        user_id=user_id,
        message=text,
        random_id=random.randint(1, 1000000)
    )

print("🚀 ЧИСТЫЙ ИИ ТУРАГЕНТ v6.1 — Только текст")

# ГЛАВНЫЙ ЦИКЛ — 100% ИИ
for event in longpoll.listen():
    if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
        continue

    user_id = event.user_id
    user_text = event.text.strip()
    
    if not user_text or len(user_text) < 1:
        continue

    state = get_user_state(user_id)
    history = state["history"]
    
    # История
    history.append({"text": user_text, "timestamp": time.time()})
    if len(history) > 30:
        history.pop(0)
    
    text_lower = user_text.lower()
    
    # Только созвон по явному запросу
    if any(word in text_lower for word in ["созвони", "позвони", "номер", "телефон"]):
        msg = "Отлично! Напишите номер и когда удобно — перезвоню быстро."
        send(user_id, msg)
        save_conversation(user_id)
        continue
    
    # СТАРТ
    if any(word in text_lower for word in ["привет", "начать", "тур", "поезд", "отдых"]):
        state["history"] = []
        msg = "Привет! Давай подберём тебе поездку. Куда примерно хочешь и когда можешь вылетать?"
        send(user_id, msg)
        continue
    
    # 🤖 100% ИИ ТУРАГЕНТ
    next_question = get_yandexgpt_next_question(user_text, history)
    
    confirmations = [
        "Понял.", "Окей.", "Хорошо.", "Записал.", 
        "Понятно.", "Смотри.", "Ясно."
    ]
    
    msg = f"{random.choice(confirmations)}\n\n{next_question}"
    send(user_id, msg)
    
    # Сейв каждые 7 сообщений
    if len(history) % 7 == 0:
        save_conversation(user_id)
