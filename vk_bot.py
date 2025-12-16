import vk_api
import os
import json
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен из переменной окружения
VK_TOKEN = os.environ.get('VK_TOKEN')
if not VK_TOKEN:
    logging.error("VK_TOKEN не найден!")
    exit(1)

vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

# Хранение состояний пользователей (в памяти)
user_states = {}
tours_db = {
    "russia": {"name": "Туры по России", "price": "от 25 000₽"},
    "turkey": {"name": "Турция", "price": "от 45 000₽"},
    "egypt": {"name": "Египет", "price": "от 55 000₽"}
}

def create_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button("📋 Туры по России", color=VkKeyboardColor.PRIMARY)
    keyboard.add_button("🇹🇷 Турция", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button("🇪🇬 Египет", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button("💰 Цены", color=VkKeyboardColor.SECONDARY)
    keyboard.add_button("📞 Позвонить", color=VkKeyboardColor.NEGATIVE)
    keyboard.add_line()
    keyboard.add_button("📝 Оставить заявку", color=VkKeyboardColor.PRIMARY)
    return keyboard.get_keyboard()

def create_question_keyboard(question):
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button("✅ Готово", color=VkKeyboardColor.PRIMARY)
    return keyboard.get_keyboard()

def save_application(user_id, data):
    """Сохраняет заявку в JSON файл"""
    try:
        with open(f"app_{user_id}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"Заявка сохранена: app_{user_id}.json")
    except Exception as e:
        logging.error(f"Ошибка сохранения: {e}")

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me:
        user_id = event.user_id
        text = event.text.lower().strip()
        
        # Инициализация состояния пользователя
        if user_id not in user_states:
            user_states[user_id] = {"step": "main", "data": {}}
        
        state = user_states[user_id]
        
        # Главное меню
        if state["step"] == "main":
            if any(word in text for word in ["тур", "куда", "направление"]):
                vk.messages.send(
                    user_id=user_id,
                    message="🌍 Выберите направление:",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
            elif "по росси" in text or "россия" in text:
                vk.messages.send(
                    user_id=user_id,
                    message="🇷🇺 Туры по России\n💰 Цена: от 25 000₽\n📅 Даты: круглый год\n\nХотите оставить заявку?",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
            elif "турци" in text:
                vk.messages.send(
                    user_id=user_id,
                    message="🇹🇷 Турция\n💰 Цена: от 45 000₽\n📅 Сезон: круглый год\n✈️ Вылет: из Москвы\n\n📝 Оставить заявку?",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
            elif "египт" in text:
                vk.messages.send(
                    user_id=user_id,
                    message="🇪🇬 Египет\n💰 Цена: от 55 000₽\n📅 Сезон: круглый год\n🏖️ All Inclusive\n\n📞 Оставить заявку?",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
            elif "цена" in text or "сколько" in text:
                msg = "💰 Цены на туры:\n\n"
                for country, info in tours_db.items():
                    msg += f"• {info['name']}: {info['price']}\n"
                msg += "\n📝 Хотите подобрать тур?"
                vk.messages.send(
                    user_id=user_id,
                    message=msg,
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
            elif "позвони" in text or "телефон" in text:
                vk.messages.send(
                    user_id=user_id,
                    message="📞 Позвонить менеджеру:\n+7 (999) 123-45-67\n\nИли нажмите '📝 Оставить заявку'",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
            elif "заявк" in text:
                state["step"] = "name"
                state["data"] = {}
                vk.messages.send(
                    user_id=user_id,
                    message="📝 **Заполните анкету**\n\n👤 Как вас зовут?",
                    keyboard=create_question_keyboard(""),
                    random_id=0
                )
            else:
                vk.messages.send(
                    user_id=user_id,
                    message="👋 Привет! Напишите 'ТУР', 'КУДА', 'ЦЕНА' или выберите кнопку:",
                    keyboard=create_main_keyboard(),
                    random_id=0
                )
        
        # Сбор анкеты
        elif state["step"] == "name":
            state["data"]["name"] = text
            state["step"] = "phone"
            vk.messages.send(
                user_id=user_id,
                message="📱 Номер телефона (для связи):",
                keyboard=create_question_keyboard(""),
                random_id=0
            )
        
        elif state["step"] == "phone":
            state["data"]["phone"] = text
            state["step"] = "direction"
            vk.messages.send(
                user_id=user_id,
                message="🌍 Куда хотите поехать?\n(напишите страну/город)",
                keyboard=create_question_keyboard(""),
                random_id=0
            )
        
        elif state["step"] == "direction":
            state["data"]["direction"] = text
            state["step"] = "budget"
            vk.messages.send(
                user_id=user_id,
                message="💰 Бюджет на человека (руб):",
                keyboard=create_question_keyboard(""),
                random_id=0
            )
        
        elif state["step"] == "budget":
            state["data"]["budget"] = text
            state["step"] = "done"
            
            # Сохраняем заявку
            save_application(user_id, state["data"])
            
            # Отправляем тебе заявку (замени YOUR_MANAGER_ID на свой user_id)
            manager_id = 123456789  # ← ТВОЙ VK ID!
            summary = (
                f"🆕 НОВАЯ ЗАЯВКА!\n\n"
                f"👤 {state['data']['name']}\n"
                f"📱 {state['data']['phone']}\n"
                f"🌍 {state['data']['direction']}\n"
                f"💰 {state['data']['budget']}\n\n"
                f"⏰ {vk.users.get(user_ids=user_id)[0]['first_name']} {vk.users.get(user_ids=user_id)[0]['last_name']}"
            )
            
            try:
                vk.messages.send(user_id=manager_id, message=summary, random_id=0)
            except:
                pass  # Если не удалось - сохранили в файл
            
            vk.messages.send(
                user_id=user_id,
                message=(
                    "✅ Заявка отправлена!\n\n"
                    f"👤 {state['data']['name']}\n"
                    f"📱 {state['data']['phone']}\n"
                    f"🌍 {state['data']['direction']}\n"
                    f"💰 {state['data']['budget']}\n\n"
                    "📞 Менеджер свяжется в течение 15 минут!"
                ),
                keyboard=create_main_keyboard(),
                random_id=0
            )
            state["step"] = "main"  # Возврат в главное меню
