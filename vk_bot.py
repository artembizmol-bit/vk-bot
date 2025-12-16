import vk_api
import os
import json
import time
import random
import requests
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import logging

logging.basicConfig(level=logging.INFO)

VK_TOKEN = os.environ.get('VK_TOKEN')
PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY', '')  # Опционально

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

user_states = {}
tours_db = {
    "russia": {"name": "Туры по России", "desc": "Сочи, Калининград, Алтай, Карелия"},
    "turkey": {"name": "Турция", "desc": "Анталия, Алания, Бодрум, Мармарис"},
    "egypt": {"name": "Египет", "desc": "Хургада, Шарм-эль-Шейх"}
}

def create_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📋 Туры по России", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🇹🇷 Турция", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("🇪🇬 Египет", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("📝 Оставить заявку", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("❓ Задать вопрос", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button("📞 Позвонить", color=VkKeyboardColor.NEGATIVE)
    return keyboard.get_keyboard()

def create_question_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("✅ Готово", color=VkKeyboardColor.PRIMARY)
    return keyboard.get_keyboard()

def get_perplexity_answer(question):
    """AI ответ через Perplexity (если ключ есть)"""
    if not PERPLEXITY_API_KEY:
        return None
    
    try:
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {"role": "system", "content": "Ты эксперт по туризму. Отвечай кратко, дружелюбно, на русском. Только туризм!"},
                {"role": "user", "content": question}
            ],
            "max_tokens": 150
        }
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
    except:
        pass
    return None

def is_tour_question(text):
    """Проверяет, вопрос про туризм или нет"""
    tour_keywords = ['тур', 'отдых', 'поездка', 'вылет', 'отель', 'авиа', 'виза', 'страна', 'море', 'горы']
    return any(word in text.lower() for word in tour_keywords)

def save_application(user_id, data):
    try:
        with open(f"app_{user_id}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"Заявка: app_{user_id}.json")
    except:
        pass

def send_typing_status(user_id):
    """Показывает 'печатает...'"""
    vk.messages.setActivity(user_id=user_id, type="typing")

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_id = event.user_id
        text = event.text.strip()
        text_lower = text.lower()
        
        # Задержка 1-3 секунды (человечность)
        time.sleep(random.uniform(1, 3))
        
        if user_id not in user_states:
            user_states[user_id] = {"step": "main", "data": {}}
        
        state = user_states[user_id]
        
        # Главное меню
        if state["step"] == "main":
            if any(word in text_lower for word in ["тур", "куда", "направление", "отдых"]):
                vk.messages.send(
                    user_id=user_id,
                    message="🌍 Выберите направление или напишите страну:",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
            
            elif "по росси" in text_lower or "россия" in text_lower:
                info = tours_db["russia"]
                vk.messages.send(
                    user_id=user_id,
                    message=f"🇷🇺 {info['name']}\n{info['desc']}\n\n📝 Оставить заявку?",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
            
            elif "турци" in text_lower:
                info = tours_db["turkey"]
                vk.messages.send(
                    user_id=user_id,
                    message=f"🇹🇷 {info['name']}\n{info['desc']}\n\n📝 Оставить заявку?",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
            
            elif "египт" in text_lower:
                info = tours_db["egypt"]
                vk.messages.send(
                    user_id=user_id,
                    message=f"🇪🇬 {info['name']}\n{info['desc']}\n\n📝 Оставить заявку?",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
            
            elif "заявк" in text_lower or "📝 оставить заявку" in text:
                state["step"] = "name"
                state["data"] = {}
                send_typing_status(user_id)
                vk.messages.send(
                    user_id=user_id,
                    message="📝 **Заполните анкету**\n\n👤 Как вас зовут?",
                    keyboard=create_question_keyboard(),
                    random_id=0
                )
            
            elif "❓ задать вопрос" in text or "вопрос" in text_lower:
                state["step"] = "question"
                vk.messages.send(
                    user_id=user_id,
                    message="❓ Задайте вопрос по туризму, помогу! 🌴",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
            
            elif "позвони" in text_lower or "телефон" in text_lower or "📞" in text:
                vk.messages.send(
                    user_id=user_id,
                    message="📞 Связь с менеджером:\n+7 (999) 123-45-67\n\nИли оставьте заявку!",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
            
            # Перплексити для общих вопросов про туризм
            elif is_tour_question(text_lower):
                send_typing_status(user_id)
                ai_answer = get_perplexity_answer(text)
                if ai_answer:
                    vk.messages.send(
                        user_id=user_id,
                        message=f"🤖 {ai_answer}\n\n📝 Нужна заявка?",
                        keyboard=create_main_keyboard(),
                        random_id=0
                    )
                else:
                    vk.messages.send(
                        user_id=user_id,
                        message="Напишите 'ТУР' или выберите направление! 🌍",
                        keyboard=create_main_keyboard(),
                        random_id=0
                    )
            
            else:
                vk.messages.send(
                    user_id=user_id,
                    message="👋 Выберите кнопку или напишите 'ТУР':",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
        
        # Анкета (без изменений)
        elif state["step"] == "name":
            state["data"]["name"] = text
            state["step"] = "phone"
            send_typing_status(user_id)
            vk.messages.send(user_id=user_id, message="📱 Номер телефона:", keyboard=create_question_keyboard(), random_id=0)
        
        elif state["step"] == "phone":
            state["data"]["phone"] = text
            state["step"] = "direction"
            send_typing_status(user_id)
            vk.messages.send(user_id=user_id, message="🌍 Куда хотите? (страна/город)", keyboard=create_question_keyboard(), random_id=0)
        
        elif state["step"] == "direction":
            state["data"]["direction"] = text
            state["step"] = "done"
            save_application(user_id, state["data"])
            
            # Твой ID (замени!)
            manager_id = 156166343 
            summary = f"🆕 ЗАЯВКА!\n👤 {state['data']['name']}\n📱 {state['data']['phone']}\n🌍 {state['data']['direction']}"
            
            try:
                vk.messages.send(user_id=manager_id, message=summary, random_id=0)
            except:
                pass
            
            vk.messages.send(
                user_id=user_id,
                message="✅ Заявка отправлена! Менеджер свяжется с вами в ближайшее время ⏰",
                keyboard=create_main_keyboard(),
                random_id=0
            )
            state["step"] = "main"
