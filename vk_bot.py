import os
import time
import random
import json
import logging

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

def human_delay(min_s=2, max_s=5):
    time.sleep(random.uniform(min_s, max_s))

def typing(user_id):
    try:
        vk.messages.setActivity(user_id=user_id, type="typing")
    except:
        pass

def get_smart_fallback(user_text, history):
    """УМНЫЕ вопросы по ключевым словам + последовательность"""
    text_lower = user_text.lower()
    
    # Специальные ответы
    if "пляж" in text_lower or "море" in text_lower:
        return "Отлично, пляжный отдых. Из какого города вылетаете?"
    
    if "секс" in text_lower or any(x in text_lower for x in ["взрослые", "тусовк", "ночные", "вечерин"]):
        return "Понял, для взрослых. Турция, Египет или другие варианты рассматриваете?"
    
    if any(word in text_lower for word in ["деньги", "бюджет", "сколько", "руб"]):
        return "Бюджет на человека или общий? Примерно в каких суммах думаете?"
    
    if any(word in text_lower for word in ["отдых", "отпуск", "поездка"]):
        return "Когда примерно планируете вылетать — конкретные даты или месяц?"
    
    # Анализ истории для последовательности вопросов
    recent_texts = [h["text"].lower() for h in history[-5:]]
    
    if any(word in " ".join(recent_texts) for word in ["пляж", "море"]):
        return "С пляжем понятно. Сколько человек поедет?"
    
    if any(word in " ".join(recent_texts) for word in ["турци", "египт", "росси"]):
        return "С направлением разобрались. Когда вылетать удобно?"
    
    if any(word in " ".join(recent_texts) for word in ["москва", "питер", "екатерин"]):
        return "Город вылета понял. Сколько человек и когда примерно?"
    
    # Последовательность стандартных вопросов
    standard_questions = [
        "Сколько человек поедет — взрослые, дети?",
        "Когда примерно планируете поездку?",
        "Какой бюджет ориентировочно?",
        "Что ещё важно: еда, экскурсии, анимация?",
        "Где уже бывали, что понравилось/не понравилось?"
    ]
    
    return random.choice(standard_questions)

def get_yandexgpt_response(user_text, context):
    """YandexGPT + УМНЫЕ FALLBACK'и"""
    if not YANDEX_FOLDER_ID or not YANDEX_IAM_TOKEN:
        return get_smart_fallback(user_text, context["history"])
    
    try:
        import requests
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
            "x-folder-id": YANDEX_FOLDER_ID,
            "Content-Type": "application/json"
        }
        messages = [
            {
                "role": "system", 
                "text": """Ты опытный турагент. Задавай ТОЛЬКО ОДИН следующий вопрос.
ПРАВИЛА:
1. НИКОГДА не называй цены, отели, рейсы
2. НИКОГДА не давай конкретных рекомендаций  
3. Задавай только ВОПРОСЫ для уточнения потребностей
4. Говори естественно, как живой человек"""
            },
            {
                "role": "user", 
                "text": f"Контекст: {context}\nПоследний ответ: {user_text}\n\nЗадай один следующий вопрос:"
            }
        ]
        
        data = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite:latest",
            "completionOptions": {
                "stream": False,
                "temperature": 0.3,
                "maxTokens": 100
            },
            "messages": messages
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            result = response.json()
            ai_text = result['result']['alternatives'][0]['message']['text'].strip()
            if "?" in ai_text and len(ai_text) < 200 and "руб" not in ai_text.lower():
                return ai_text
    except:
        logging.error("YandexGPT error, using fallback")
        pass
    
    return get_smart_fallback(user_text, context["history"])

def needs_call(text):
    call_keywords = ["конкретно", "точно", "билеты", "отель", "рейс", "цена", "купить", "забронировать", "ссылка"]
    return any(keyword in text.lower() for keyword in call_keywords)

def get_user_state(user_id):
    if user_id not in users:
        users[user_id] = {
            "history": [],
            "data": {},
            "ready_for_call": False
        }
    return users[user_id]

def save_lead(user_id):
    state = users[user_id]
    fname = f"lead_{user_id}_{int(time.time())}.json"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        logging.info(f"Lead сохранён: {fname}")
    except:
        pass

def send(user_id, text, keyboard=None):
    typing(user_id)
    human_delay()
    vk.messages.send(
        user_id=user_id,
        message=text,
        keyboard=keyboard,
        random_id=random.randint(1, 1000000)
    )

def main_keyboard():
    kb = VkKeyboard(one_time=False)
    kb.add_button("Продолжить подбор", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("Созвониться сейчас", color=VkKeyboardColor.POSITIVE)
    kb.add_button("Оставить номер", color=VkKeyboardColor.NEGATIVE)
    return kb.get_keyboard()

print("🚀 VK Туристический агент запущен!")

# Основной цикл
for event in longpoll.listen():
    if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
        continue

    user_id = event.user_id
    user_text = event.text.strip()
    
    if not user_text:
        continue

    state = get_user_state(user_id)
    history = state["history"]
    
    # Сохраняем историю
    history.append({"text": user_text, "timestamp": time.time()})
    if len(history) > 20:
        history.pop(0)
    
    # Конкретика → сразу на созвон
    if needs_call(user_text):
        state["ready_for_call"] = True
        msg = (
            "Понимаю, хотите уже конкретику. Давайте лучше созвонимся — так быстрее и точнее всё подберём.\n\n"
            "Оставьте номер и удобное время, или нажмите «Созвониться сейчас»."
        )
        send(user_id, msg, main_keyboard())
        save_lead(user_id)
        continue
    
    # Команды управления
    text_lower = user_text.lower()
    if any(word in text_lower for word in ["созвони", "позвони", "номер", "телефон"]):
        msg = "Отлично! Напишите номер телефона и когда удобно говорить — перезвоню в течение 15 минут."
        send(user_id, msg)
        save_lead(user_id)
        continue
    
    if any(word in text_lower for word in ["начать", "подбор", "тур"]):
        state["history"] = []
        msg = "Давайте разберёмся с поездкой. Куда примерно хотите и когда можете вылетать?"
        send(user_id, msg)
        continue
    
    # Главная логика: AI-анализ или умный fallback
    context_summary = " ".join([h["text"] for h in history[-5:]])
    next_question = get_yandexgpt_response(user_text, context_summary)
    
    # Человеческие подтверждения
    confirmations = [
        "Понял вас.",
        "Окей, принял.",
        "Хорошо, учту.", 
        "Ясно.",
        "Записал.",
        "Понятно."
    ]
    confirmation = random.choice(confirmations)
    
    msg = f"{confirmation}\n\n{next_question}"
    send(user_id, msg)
    
    # Автосейв лидов
    if len(history) % 5 == 0:
        save_lead(user_id)
