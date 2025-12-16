import os
import time
import random
import json
import logging
import requests

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

logging.basicConfig(level=logging.INFO)

VK_TOKEN = os.environ.get("VK_TOKEN")
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")

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

def get_perplexity_analysis(user_id, user_text, context):
    """Анализирует ответ пользователя и предлагает следующий шаг"""
    if not PERPLEXITY_API_KEY:
        return generate_fallback_response(user_text, context)
    
    try:
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        prompt = f"""
Ты опытный турагент. Проанализируй ответ клиента и предложи ЕДИНСТВЕННЫЙ следующий вопрос.

ПРАВИЛА:
1. НИКОГДА не давай конкретные отели/цены/рейсы/ссылки
2. НИКОГДА не галлюцинируй факты о странах/отелях
3. Задавай ТОЛЬКО один вопрос за раз
4. Если клиент хочет конкретику — предлагай созвон
5. Вопрос должен быть естественным, как у живого человека

Контекст диалога: {context}
Последний ответ клиента: "{user_text}"

Ответь ТОЛЬКО одним вопросом (максимум 2 предложения).
        """
        
        data = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_text}
            ],
            "max_tokens": 100,
            "temperature": 0.3
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            ai_response = response.json()['choices'][0]['message']['content'].strip()
            # Фильтр на галлюцинации
            if len(ai_response) < 500 and "?" in ai_response and "отель" not in ai_response.lower() and "цена" not in ai_response.lower():
                return ai_response
    except:
        pass
    
    return generate_fallback_response(user_text, context)

def generate_fallback_response(user_text, context):
    """Резервные вопросы без ИИ"""
    text_lower = user_text.lower()
    
    if any(word in text_lower for word in ["не знаю", "подскажи", "что посоветуешь"]):
        return "Давайте начнём с самого простого: куда примерно тянет или какие направления вообще рассматриваете?"
    
    if "деньги" in text_lower or "бюджет" in text_lower:
        return "По деньгам удобнее говорить сумму на человека или общий бюджет поездки?"
    
    if any(word in text_lower for word in ["море", "пляж", "отдых"]):
        return "А как вы любите проводить время на отдыхе — больше лежать у моря или всё-таки гулять/экскурсии?"
    
    return "Расскажите чуть подробнее, что вам важно в этой поездке?"

def needs_call(text):
    """Определяет, когда нужно увести на созвон"""
    call_keywords = [
        "конкретно", "точно", "билеты", "отель", "рейс", "цена", "стоимость", 
        "купить", "забронировать", "ссылка", "сайт"
    ]
    return any(keyword in text.lower() for keyword in call_keywords)

def get_user_state(user_id):
    if user_id not in users:
        users[user_id] = {
            "stage": "discovery",
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
        return True
    except:
        return False

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
    data = state["data"]
    
    # Сохраняем историю
    history.append({"text": user_text, "timestamp": time.time()})
    if len(history) > 20:  # Ограничиваем память
        history.pop(0)
    
    # Если хочет конкретику — сразу на созвон
    if needs_call(user_text):
        state["ready_for_call"] = True
        msg = (
            "Понимаю, что хотите уже конкретику. Давайте лучше созвонимся — так быстрее и точнее всё подберём.\n\n"
            "Оставьте номер и когда вам удобно говорить, или нажмите «Созвониться сейчас»."
        )
        send(user_id, msg, main_keyboard())
        save_lead(user_id)
        continue
    
    # Команды управления
    text_lower = user_text.lower()
    if "созвони" in text_lower or "позвони" in text_lower or "номер" in text_lower:
        msg = (
            "Отлично, давайте созвонимся. Напишите номер телефона и когда вам удобно — "
            "перезвоню в течение 15 минут."
        )
        send(user_id, msg)
        save_lead(user_id)
        continue
    
    if "начать" in text_lower or "подбор" in text_lower:
        state["stage"] = "discovery"
        state["history"] = []
        msg = (
            "Давайте разберёмся, что вам нужно. Начнём с самого простого:\n\n"
            "Куда примерно хотите поехать и когда примерно можете вылетать?"
        )
        send(user_id, msg)
        continue
    
    # Главная логика: AI-анализ предыдущего контекста
    context_summary = " ".join([h["text"] for h in history[-5:]])  # Последние 5 сообщений
    
    next_question = get_perplexity_analysis(user_id, user_text, context_summary)
    
    # Подтверждение понимания + следующий вопрос
    confirmations = [
        "Понял вас.",
        "Окей, принял.",
        "Хорошо, учту.",
        "Ясно.",
        "Записал."
    ]
    
    confirmation = random.choice(confirmations)
    
    msg = f"{confirmation}\n\n{next_question}"
    
    send(user_id, msg)
    
    # Сохраняем лид каждые 5 сообщений (на случай потери)
    if len(history) % 5 == 0:
        save_lead(user_id)
