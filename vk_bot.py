#!/usr/bin/env python3
"""
VK Турбот с GigaChat — Render + CLIENT_ID/CLIENT_SECRET!
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
# RENDER ENV ПЕРЕМЕННЫЕ (4 штуки!)
# =============================================================================
VK_TOKEN = os.getenv("VK_TOKEN")           # vk.com токен группы
CLIENT_ID = os.getenv("CLIENT_ID")         # developers.sber.ru
CLIENT_SECRET = os.getenv("CLIENT_SECRET") # developers.sber.ru

print("🤖 VK Турбот v7.0 — GigaChat AutoToken!")
print(f"🔑 VK: {VK_TOKEN[:20]}...")
print(f"🆔 ID: {CLIENT_ID[:20]}...")

class GigaChatAuto:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = self._get_token()
    
    def _get_token(self):
        """Автоматически получает токен"""
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
        
        resp = requests.request("POST", url, headers=headers, data=payload, 
                               timeout=30, verify=False)
        
        if resp.status_code == 200:
            return resp.json().get('access_token')
        print(f"❌ GigaChat Token Error: {resp.status_code}")
        return None
    
    def ask(self, question):
        if not self.token:
            return "❌ GigaChat недоступен"
        
        url = "https://gigachat.api.sber.ru/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "GigaChat-Pro",
            "messages": [
                {"role": "system", "text": "Ты профессиональный турагент. Отвечай кратко, по делу. Предлагай бюджетные туры из России."},
                {"role": "user", "text": question}
            ],
            "stream": False,
            "temperature": 0.7,
            "max_tokens": 200
        }
        
        try:
            resp = requests.post(url, headers=headers, json=data, 
                               timeout=20, verify=False)
            if resp.status_code == 200:
                return resp.json()['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"GigaChat Error: {e}")
        
        return "🔄 Ищу лучшие туры... Подожди 10 сек!"

def main():
    if not all([VK_TOKEN, CLIENT_ID, CLIENT_SECRET]):
        print("❌ ENV: VK_TOKEN, CLIENT_ID, CLIENT_SECRET обязательны!")
        return
    
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    longpoll = VkLongPoll(vk_session)
    giga = GigaChatAuto(CLIENT_ID, CLIENT_SECRET)
    
    print("✅ Готов к работе! Пиши в VK группу!")
    
    for event in longpoll.listen():
        if event.type == VkEventType.MESSAGE_NEW and event.to_me:
            user_id = event.user_id
            text = event.text
            
            print(f"👤 {user_id}: {text}")
            
            # Быстрые ответы
            if "египет" in text.lower():
                answer = giga.ask("Бюджетный тур в Египет из Москвы на 7 дней")
            elif "турция" in text.lower():
                answer = giga.ask("Бюджетный тур в Турцию all inclusive")
            elif "отдых" in text.lower() or "отпуск" in text.lower():
                answer = giga.ask("Бюджетный отдых на море из России")
            else:
                answer = giga.ask(text)
            
            vk_session.method("messages.send", {
                "user_id": user_id,
                "message": answer,
                "random_id": 0
            })
            print(f"🤖 {answer[:50]}...")

if __name__ == "__main__":
    main()
