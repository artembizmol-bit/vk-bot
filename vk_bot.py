import os
from vk_api import VkApi
from vk_api.longpoll import VkLongPoll, VkEventType
import random
import time

# Токен из переменных окружения
GROUP_TOKEN = os.getenv('VK_TOKEN')

vk_session = VkApi(token=GROUP_TOKEN)
longpoll = VkLongPoll(vk_session)
vk = vk_session.get_api()

print("🤖 VK Бот запущен!")

while True:
    try:
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                user_id = event.user_id
                text = event.text.lower()
                
                print(f"Сообщение от {user_id}: {text}")
                
                if 'тур' in text or 'куда' in text:
                    vk.messages.send(
                        user_id=user_id,
                        message="✈️ **Туры от 45 000₽**\n🇹🇷 Турция | 🇪🇬 Египет\n📞 +7(XXX)XXX-XX-XX",
                        random_id=random.randint(1, 100000)
                    )
                elif 'цена' in text or 'стоимость' in text:
                    vk.messages.send(
                        user_id=user_id,
                        message="💰 **Цены:** Турция 45к₽, Египет 55к₽\n✅ Рассрочка 0%\n📲 Напиши 'ТУР'!",
                        random_id=random.randint(1, 100000)
                    )
                else:
                    vk.messages.send(
                        user_id=user_id,
                        message="💬 Напиши 'ТУР', 'КУДА' или 'ЦЕНА'",
                        random_id=random.randint(1, 100000)
                    )
    except Exception as e:
        print(f"Ошибка: {e}")
        time.sleep(5)
