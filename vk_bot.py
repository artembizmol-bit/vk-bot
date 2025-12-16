import os
import time
import random
import json
import logging
import requests

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

def human_delay(min_s=2, max_s=4):
    time.sleep(random.uniform(min_s, max_s))

def typing(user_id):
    try:
        vk.messages.setActivity(user_id=user_id, type="typing")
    except:
        pass

def get_yandexgpt_next_question(user_text, history_context):
    """🤖 ЧИСТЫЙ ИИ ТУРАГЕНТ"""
    if not YANDEX_FOLDER_ID or not YANDEX_IAM_TOKEN:
        return "Расскажите подробнее о поездке: куда, когда, с кем?"
    
    try:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
            "x-folder-id": YANDEX_FOLDER_ID,
            "Content-Type": "application/json"
        }
        
        context_summary = "\n".join([f"Клиент: {h['text']}" for h in history_context[-8:]])
        
        messages = [
            {
                "role": "system",
                "text": """Ты живой турагент с 10-летним опытом. 
                
ПРАВИЛА:
1. НИКОГДА не называй цены, отели, рейсы, ссылки
2. Задавай ТОЛЬКО ОДИН логичный следующий вопрос
3. Говори естественно: "Понял", "Окей", "Смотри"
4. Анализируй ВЕСЬ контекст диалога
5. Если конкретику просят — предлагай созвон
6. НЕ повторяй один и тот же вопрос
7. НИКОГДА не предлагай кнопки

Стиль: спокойный профессионал, который сначала понимает клиента."""
            },
            {
                "role": "user",
                "text": f"""Полный контекст диалога:
{context_summary}

Последний ответ клиента: "{user_text}"

Задай один естественный следующий вопрос (только текст, без кнопок)."""
            }
        ]
        
        data = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite:latest",
            "completionOptions
