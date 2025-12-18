#!/usr/bin/env python3
"""
VK Турбот v7.1 — ФИКС NoneType + Проверки ENV
"""

import os
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
import requests
import base64
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================================================
# RENDER ENV — С ПРОВЕРКАМИ
# =============================================================================
VK_TOKEN = os.getenv("VK_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

print("🤖 VK Турбот v7.1 — START")
print(f"🔑 VK_TOKEN: {'✅' if VK_TOKEN else '❌'}")
print(f"🆔 CLIENT_ID: {'✅' if CLIENT_ID else '❌'}")
print(f"🔐 CLIENT_SECRET: {'✅' if CLIENT_SECRET else '❌'}")

# ✅ ПРОВЕРКА ВСЕХ 3 ПЕРЕМЕННЫХ
if not all([VK_TOKEN, CLIENT_ID, CLIENT_SECRET]):
    print("❌ ОШИБКА: Добавь в Render Environment Variables:")
    print("   VK_TOKEN = vk1.a.твой_токен")
    print("   CLIENT_ID = 019b3087-4a28-...")
    print("   CLIENT_SECRET = 1f702d3a-3cb...")
    print("Render → Environment → Add Environment Variable")
    exit(1)

print("✅ ВСЕ ENV OK!")

class GigaChatAuto:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = self._get_token()
        print(f"🔑 GigaChat Token: {'✅' if self.token else '❌'}")
    
    def _get_token(self):
        auth_string = f"{self.client_id}:{self.client_secret}"
        authorization = base64.b64encode(auth_string.encode()).decode()
        
        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        payload = {'scope': 'GIGACHAT_API_PERS'}
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': self.client_secret,
            'Authorization': f'Basic {authorization}'
        }
        
        try:
            resp = requests.request("POST", url, headers=headers, data=payload, 
                                   timeout=30, verify=False)
            if resp.status_code == 200:
                return resp.json().get('access_token')
        except:
            pass
        return None
    
    def ask(self, question):
        if not self.token:
            return "🔄 GigaChat подключается... (1 минута)"
        
        url = "https://gigachat.api.sber.ru/chat/completions"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        data = {
            "model": "GigaChat-Pro",
            "messages": [
                {"role": "system", "text": "Ты турагент. Кратко. Бюджетные туры."},
                {"role": "user", "text": question}
            ],
            "stream": False,
            "temperature": 0.7
        }
        
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=20, verify=False)
            if resp.status_code == 200:
                return resp.json()['choices'][0]['message']['content'].strip()
        except:
            pass
        return "🔄 Ищу туры..."

def main():
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    longpoll = VkLongPoll(vk_session)
    giga = GigaChatAuto(CLIENT_ID, CLIENT_SECRET)
    
    print("🚀 Бот готов! Пиши в VK группу!")
    
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            text = event.text
            
            print(f"👤 {user_id}: {text}")
            
            if any(word in text.lower() for word in ['египет', 'турция', 'отдых']):
                answer = giga.ask(f"Бюджетный тур: {text}")
            else:
                answer = giga.ask(text)
            
            vk_session.method("messages.send", {
                "user_id": user_id,
                "message": answer,
                "random_id": 0
            })
            print(f"🤖 Отправлено: {answer[:50]}...")

if __name__ == "__main__":
    main()
