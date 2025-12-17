import os
import time
import random
import logging
import re
import requests
from flask import Flask
import threading

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

logging.basicConfig(level=logging.INFO)
VK_TOKEN = os.environ.get("VK_TOKEN")
YANDEX_FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID")
YANDEX_IAM_TOKEN = os.environ.get("YANDEX_IAM_TOKEN")

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)
users = {}

def human_delay():
    time.sleep(random.uniform(1.5, 3))

def typing(user_id):
    try:
        vk.messages.setActivity(user_id=user_id, type="typing")
    except: pass

def yandexgpt_request(user_text, history_context):
    """🤖 YANDEXGPT API"""
    if not YANDEX_FOLDER_ID or not YANDEX_IAM_TOKEN:
        return "❌ YandexGPT ключи не настроены"
    
    try:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
            "x-folder-id": YANDEX_FOLDER_ID,
            "Content-Type": "application/json"
        }
        
        context = "\n".join([f"Клиент: {h['text']}" for h in history_context[-5:]])
        
        messages = [
            {
                "role": "system",
                "text": """Ты живой турагент. ПРАВИЛА:
1. Задавай ТОЛЬКО ОДИН следующий логичный вопрос
2. Говори естественно: "Понял", "Окей", "Записал"
3. Анализируй ВЕСЬ контекст диалога выше
4. Никогда не повторяй один и тот же вопрос"""
            },
            {
                "role": "user",
                "text": f"""Диалог с клиентом:
{context}

Последнее сообщение клиента: {user_text}

Задай ОДИН следующий вопрос:"""
            }
        ]
        
        data = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.6,
                "maxTokens": 100
            },
            "messages": messages
        }
        
        print(f"🔍 GPT запрос: {user_text[:30]}...")
        response = requests.post(url, headers=headers, json=data, timeout=15)
        
        print(f"🔍 Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            ai_text = result['result']['alternatives'][0]['message']['text'].strip()
            print(f"✅ GPT: {ai_text[:50]}...")
            return ai_text
        else:
            error_text = response.text[:100]
            print(f"❌ GPT {response.status_code}: {error_text}")
            return f"🤖 GPT ошибка {response.status_code}. Проверь ключи."
            
    except Exception as e:
        print(f"❌ GPT Exception: {e}")
        return "🤖 GPT недоступен. Созвонимся?"

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

app = Flask(__name__)

@app.route('/')
def health():
    return {"status": "YANDEXGPT Bot", "gpt_ready": bool(YANDEX_FOLDER_ID and YANDEX_IAM_TOKEN)}

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=port, debug=False),
        daemon=True
    ).start()
    
    print("🚀 VK YANDEXGPT ТУРАГЕНТ v10.0")
    
    for event in longpoll.listen():
        if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
            continue
            
        user_id = event.user_id
        user_text = event.text.strip()
        if not user_text:
            continue
            
        state = get_user_state(user_id)
        history = state["history"]
        history.append({"text": user_text, "time": time.time()})
        if len(history) > 15:
            history.pop(0)
        
        print(f"💬 {user_id}: {user_text}")
        
        text_lower = user_text.lower()
        
        if any(w in text_lower for w in ["привет", "начать", "старт"]):
            state["history"] = []
            send(user_id, "Привет! Куда хочешь поехать? 🏝️")
            continue
        
        response = yandexgpt_request(user_text, history)
        send(user_id, response)
