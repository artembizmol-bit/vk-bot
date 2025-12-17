import os
import time
import random
import json
import logging
import requests

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

# ЛОГИ ПОДРОБНЫЕ
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

VK_TOKEN = os.environ.get("VK_TOKEN")
YANDEX_FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "")
YANDEX_IAM_TOKEN = os.environ.get("YANDEX_IAM_TOKEN", "")

print(f"🔍 DEBUG: YANDEX_FOLDER_ID={YANDEX_FOLDER_ID[:10]}...")
print(f"🔍 DEBUG: YANDEX_IAM_TOKEN={YANDEX_IAM_TOKEN[:10]}...")

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

def test_yandexgpt(user_text, history_context):
    """🔍 ОТЛАДКА YANDEXGPT"""
    print(f"🔍 DEBUG: Запрос к YandexGPT...")
    print(f"🔍 DEBUG: Folder ID: {YANDEX_FOLDER_ID}")
    print(f"🔍 DEBUG: IAM Token: {YANDEX_IAM_TOKEN[:20]}...")
    
    if not YANDEX_FOLDER_ID or not YANDEX_IAM_TOKEN:
        print("❌ DEBUG: Ключи YandexGPT отсутствуют!")
        return "🔍 YandexGPT ключи не настроены. Использую fallback."
    
    try:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
            "x-folder-id": YANDEX_FOLDER_ID,
            "Content-Type": "application/json"
        }
        
        context_summary = "\n".join([f"Клиент: {h['text']}" for h in history_context[-4:]])
        
        messages = [
            {
                "role": "system",
                "text": "Ты турагент. Задай один вопрос."
            },
            {
                "role": "user",
                "text": f"Контекст: {context_summary}\nОтвет: {user_text}\nВопрос:"
            }
        ]
        
        data = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,
                "maxTokens": 80
            },
            "messages": messages
        }
        
        print(f"🔍 DEBUG: Отправка запроса...")
        response = requests.post(url, headers=headers, json=data, timeout=15)
        
        print(f"🔍 DEBUG: Status code: {response.status_code}")
        print(f"🔍 DEBUG: Response: {response.text[:200]}...")
        
        if response.status_code == 200:
            result = response.json()
            print(f"🔍 DEBUG: SUCCESS! Ответ ИИ: {result['result']['alternatives'][0]['message']['text'][:100]}")
            return result['result']['alternatives'][0]['message']['text'].strip()
        else:
            print(f"❌ DEBUG: Ошибка {response.status_code}: {response.text}")
            return f"🔍 Ошибка YandexGPT: {response.status_code}"
            
    except Exception as e:
        print(f"❌ DEBUG: Исключение: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"🔍 Ошибка: {str(e)}"

def get_user_state(user_id):
    if user_id not in users:
        users[user_id] = {"history": []}
    return users[user_id]

def send(user_id, text):
    typing(user_id)
    human_delay()
    vk.messages.send(user_id=user_id, message=text, random_id=0)

print("🚀 ОТЛАДОЧНЫЙ ИИ ТУРАГЕНТ vDEBUG")

for event in longpoll.listen():
    if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
        continue

    user_id = event.user_id
    user_text = event.text.strip()
    
    if not user_text:
        continue

    state = get_user_state(user_id)
    history = state["history"]
    
    history.append({"text": user_text, "timestamp": time.time()})
    if len(history) > 15:
        history.pop(0)
    
    print(f"💬 Сообщение от {user_id}: {user_text}")
    
    # Старт
    if user_text.lower() in ["привет", "начать", "тур"]:
        state["history"] = []
        send(user_id, "Привет! Куда хочешь поехать?")
        continue
    
    # ИИ с отладкой
    ai_response = test_yandexgpt(user_text, history)
    
    confirmations = ["Понял.", "Окей.", "Хорошо."]
    msg = f"{random.choice(confirmations)}\n\n{ai_response}"
    send(user_id, msg)
