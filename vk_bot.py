import os
import time
import random
import json
import logging
import requests

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from flask import Flask
import threading

# ЛОГИ
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

VK_TOKEN = os.environ.get("VK_TOKEN")
YANDEX_FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "")
YANDEX_IAM_TOKEN = os.environ.get("YANDEX_IAM_TOKEN", "")

print(f"🔍 YANDEX_FOLDER_ID: {YANDEX_FOLDER_ID[:10]}...")
print(f"🔍 YANDEX_IAM_TOKEN: {YANDEX_IAM_TOKEN[:10]}...")

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

users = {}

def human_delay(min_s=1.5, max_s=3):
    time.sleep(random.uniform(min_s, max_s))

def typing(user_id):
    try:
        vk.messages.setActivity(user_id=user_id, type="typing")
    except:
        pass

def yandexgpt_request(user_text, history_context):
    """🤖 YANDEXGPT С ОТЛАДКОЙ"""
    if not YANDEX_FOLDER_ID or not YANDEX_IAM_TOKEN:
        print("❌ Нет ключей YandexGPT")
        return smart_fallback(user_text, history_context)
    
    try:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
            "x-folder-id": YANDEX_FOLDER_ID,
            "Content-Type": "application/json"
        }
        
        context = "\n".join([f"Клиент: {h['text']}" for h in history_context[-4:]])
        messages = [
            {
                "role": "system",
                "text": """Ты живой турагент. ПРАВИЛА:
1. Задавай ТОЛЬКО ОДИН следующий вопрос
2. НЕ называй цены/отели/рейсы
3. Говори естественно: "Понял", "Окей"
4. Анализируй контекст диалога"""
            },
            {
                "role": "user", 
                "text": f"Диалог:\n{context}\n\nПоследнее: {user_text}\n\nЗадай один вопрос:"
            }
        ]
        
        data = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.4,
                "maxTokens": 120
            },
            "messages": messages
        }
        
        print(f"🔍 YandexGPT запрос...")
        response = requests.post(url, headers=headers, json=data, timeout=15)
        
        print(f"🔍 Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            ai_text = result['result']['alternatives'][0]['message']['text'].strip()
            if len(ai_text) > 10 and "?" in ai_text:
                print(f"✅ ИИ: {ai_text[:50]}...")
                return ai_text
        else:
            print(f"❌ YandexGPT {response.status_code}: {response.text[:100]}")
            
    except Exception as e:
        print(f"❌ YandexGPT ошибка: {e}")
    
    print("🔄 Fallback на умную логику")
    return smart_fallback(user_text, history_context)

def smart_fallback(user_text, history):
    """🧠 УМНАЯ ЛОГИКА БЕЗ ИИ"""
    text_lower = user_text.lower()
    recent = [h['text'].lower() for h in history[-5:]]
    all_context = ' '.join(recent)
    
    # Конкретные направления
    if any(word in all_context for word in ['египт', 'турци', 'турция']):
        return "Из какого города вылетаешь?"
    if any(word in all_context for word in ['таилан', 'оаэ', 'дубай']):
        return "Сколько ночей планируешь?"
    
    # Время
    if any(word in text_lower for word in ['завтра', 'скоро', 'немедленно']):
        return "Срочно! Сколько человек поедет?"
    
    # Число людей
    if re.search(r'\b(1|один|одна)\b', text_lower):
        return "Один. Бюджет примерно сколько на человека?"
    if re.search(r'\b(2|два|две)\b', text_lower):
        return "Двое. Бюджет на человека или общий?"
    
    # Города
    if any(word in all_context for word in ['моск', 'москва']):
        return "Из Москвы. Когда вылетать удобно?"
    if any(word in all_context for word in ['питер', 'спб']):
        return "Из Питера. Новый год или позже?"
    
    # Раздражение
    if any(word in text_lower for word in ['так', 'че', 'чего', 'дальше']):
        return "Давай созвонимся? Напиши номер телефона."
    
    # Последовательность вопросов
    asked_people = any('человек|сколько' in r for r in recent)
    asked_budget = any('бюджет|деньги|сколько' in r for r in recent)
    asked_dates = any('когда|дата|вылет' in r for r in recent)
    
    if not asked_people:
        return "Сколько человек поедет?"
    if not asked_dates:
        return "Когда примерно планируешь вылетать?"
    if not asked_budget:
        return "Бюджет на человека примерно какой?"
    
    return "Что важно: all inclusive, экскурсии или спокойный отдых?"

def get_user_state(user_id):
    if user_id not in users:
        users[user_id] = {"history": []}
    return users[user_id]

def send(user_id, text):
    typing(user_id)
    human_delay()
    vk.messages.send(
        user_id=user_id,
        message=text,
        random_id=random.randint(1, 1000000)
    )

# FLASK HEALTHCHECK ДЛЯ RENDER
app = Flask(__name__)

@app.route('/')
def health():
    return {"status": "VK AI Travel Agent OK", "yandexgpt": bool(YANDEX_FOLDER_ID)}

if __name__ == "__main__":
    # Flask в фоне
    port = int(os.environ.get('PORT', 10000))
    threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=port, debug=False),
        daemon=True
    ).start()
    
    print("🚀 VK ИИ ТУРАГЕНТ v8.0 + Healthcheck запущен!")
    
    # ГЛАВНЫЙ ЦИКЛ
    for event in longpoll.listen():
        if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
            continue

        user_id = event.user_id
        user_text = event.text.strip()
        
        if not user_text or len(user_text) < 1:
            continue

        state = get_user_state(user_id)
        history = state["history"]
        
        history.append({"text": user_text, "timestamp": time.time()})
        if len(history) > 20:
            history.pop(0)
        
        print(f"💬 {user_id}: {user_text}")
        print(f"📊 История: {[h['text'] for h in history[-3:]]}")
        
        text_lower = user_text.lower()
        
        # Созвон
        if any(word in text_lower for word in ["созвони", "позвони", "номер", "телефон"]):
            send(user_id, "Отлично! Напиши номер и когда удобно — перезвоню быстро.")
            continue
        
        # Старт
        if any(word in text_lower for word in ["привет", "начать", "тур", "поезд", "отдых"]):
            state["history"] = []
            send(user_id, "Привет! Давай подберем поездку. Куда примерно хочешь?")
            continue
        
        # ИИ + FALLBACK
        ai_response =
