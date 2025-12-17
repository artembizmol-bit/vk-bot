import os
import time
import random
import requests
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

VK_TOKEN = os.environ.get("VK_TOKEN")
YANDEX_FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID", "")
YANDEX_IAM_TOKEN = os.environ.get("YANDEX_IAM_TOKEN", "")

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

users = {}

def delay():
    time.sleep(random.uniform(2, 4))

def typing(user_id):
    try:
        vk.messages.setActivity(user_id=user_id, type="typing")
    except: pass

def ai_question(user_text, history):
    if not YANDEX_FOLDER_ID or not YANDEX_IAM_TOKEN:
        return "Куда хочешь поехать?"
    
    try:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {"Authorization": f"Bearer {YANDEX_IAM_TOKEN}", "x-folder-id": YANDEX_FOLDER_ID, "Content-Type": "application/json"}
        
        context = "\n".join([f"Клиент: {h['text']}" for h in history[-5:]])
        
        data = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite:latest",
            "completionOptions": {"stream": False, "temperature": 0.5, "maxTokens": 100},
            "messages": [
                {"role": "system", "text": "Ты турагент. Задавай один вопрос по контексту. Без цен/отелей."},
                {"role": "user", "text": f"{context}\nПоследний: {user_text}\nВопрос:"}
            ]
        }
        
        r = requests.post(url, headers=headers, json=data, timeout=10)
        if r.status_code == 200:
            text = r.json()['result']['alternatives'][0]['message']['text'].strip()
            if "?" in text and len(text) < 200:
                return text
    except: pass
    
    return "Когда планируешь?"

def get_state(user_id):
    if user_id not in users:
        users[user_id] = {"history": []}
    return users[user_id]

def send(user_id, text):
    typing(user_id)
    delay()
    vk.messages.send(user_id=user_id, message=text, random_id=0)

print("🤖 ИИ турагент")

for event in longpoll.listen():
    if event.type != VkEventType.MESSAGE_NEW or not event.to_me: continue
    
    uid = event.user_id
    text = event.text.strip()
    if not text: continue
    
    state = get_state(uid)
    history = state["history"]
    
    history.append({"text": text, "time": time.time()})
    if len(history) > 15: history.pop(0)
    
    if any(w in text.lower() for w in ["привет", "тур", "поезд"]):
        state["history"] = []
        send(uid, "Куда хочешь поехать?")
        continue
    
    q = ai_question(text, history)
    send(uid, f"{random.choice(['Понял.', 'Ок.', 'Хорошо.'])}\n\n{q}")
