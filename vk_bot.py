import os
import time
import random
import logging
import requests
import re
from flask import Flask
import threading

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

def human_delay():
    time.sleep(random.uniform(1.5, 3))

def typing(user_id):
    try:
        vk.messages.setActivity(user_id=user_id, type="typing")
    except: pass

def yandexgpt_request(user_text, history):
    if not YANDEX_FOLDER_ID or not YANDEX_IAM_TOKEN:
        return smart_fallback(user_text, history)
    
    try:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
            "x-folder-id": YANDEX_FOLDER_ID,
            "Content-Type": "application/json"
        }
        
        data = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.4,
                "maxTokens": 100
            },
            "messages": [
                {"role": "system", "text": "Ты турагент. Задай один вопрос."},
                {"role": "user", "text": user_text}
            ]
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            return result['result']['alternatives'][0]['message']['text'].strip()
    except:
        pass
    
    return smart_fallback(user_text, history)

def smart_fallback(user_text, history):
    text_lower = user_text.lower()
    recent = [h['text'].lower() for h in history[-3:]]
    
    if any(w in ' '.join(recent) for w in ['египт', 'турци']):
        return "Из какого города вылетаешь?"
    if any(n in text_lower for n in ['1', 'один']):
        return "Бюджет примерно какой?"
    if any(w in text_lower for w in ['завтра', 'скоро']):
        return "Сколько человек поедет?"
    if any(w in text_lower for w in ['так', 'че']):
        return "Давай созвонимся? Напиши номер."
    
    asked_people = any('человек' in r for r in recent)
    if not asked_people:
        return "Сколько человек поедет?"
    return "Когда планируешь?"

def get_user_state(user_id):
    if user_id not in users:
        users[user_id] = {"history": []}
    return users[user_id]

def send(user_id, text):
    typing(user_id)
    human_delay()
    vk.messages.send(user_id=user_id, message=text, random_id=0)

# FLASK HEALTHCHECK
app = Flask(__name__)

@app.route('/')
def health():
    return "VK Bot OK"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=port),
        daemon=True
    ).start()
    
    print("🚀 VK ИИ ТУРАГЕНТ v8.1")
    
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
        
        text_lower = user_text.lower()
        
        if any(w in text_lower for w in ["привет", "начать", "тур"]):
            state["history"] = []
            send(user_id, "Привет! Куда хочешь поехать?")
            continue
        
        if any(w in text_lower for w in ["созвони", "номер"]):
            send(user_id, "Напиши номер — перезвоню!")
            continue
        
        ai_response = yandexgpt_request(user_text, history)
        msg = f"{random.choice(['Понял.', 'Окей.', 'Хорошо.'])}\n\n{ai_response}"
        send(user_id, msg)
