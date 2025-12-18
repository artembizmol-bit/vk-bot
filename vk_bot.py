#!/usr/bin/env python3
"""
VK Турбот v8.1 — DEBUG 401 + Render Background Worker
"""

import os
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
import requests
import base64
import json
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ENV
VK_TOKEN = os.getenv("VK_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

print("🤖 VK Турбот v8.1 — DEBUG 401")
print(f"VK: {'✅' if VK_TOKEN else '❌'}")
print(f"ID: {'✅' if CLIENT_ID else '❌'}")
print(f"SECRET: {'✅' if CLIENT_SECRET else '❌'}")

if not all([VK_TOKEN, CLIENT_ID, CLIENT_SECRET]):
    print("❌ ENV неполные!")
    exit(1)

class GigaChatFix:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.get_token_debug()
    
    def get_token_debug(self):
        """DEBUG: Полный лог получения токена"""
        print("\n🔄 DEBUG: Получаю GigaChat токен...")
        
        # 2 ВАРИАНТА SCOPE
        scopes = ['GIGACHAT_API_PERS', 'GIGACHAT_API_B2B']
        
        for i, scope in enumerate(scopes, 1):
            print(f"🔄 Попытка {i}: scope={scope}")
            
            auth_string = f"{self.client_id}:{self.client_secret}"
            authorization = base64.b64encode(auth_string.encode()).decode()
            
            url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
            payload = {'scope': scope}
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'RqUID': self.client_secret,
                'Authorization': f'Basic {authorization}'
            }
            
            try:
                resp = requests.post(url, headers=headers, data=payload, timeout=30, verify=False)
                print(f"📊 Status: {resp.status_code}")
                
                if resp.status_code == 200:
                    self.token = resp.json().get('access_token')
                    print(f"✅ ТОКЕН: {self.token[:30]}... (scope={scope})")
                    return
                else:
                    print(f"❌ Ответ: {resp.text[:100]}")
                    
            except Exception as e:
                print(f"💥 {e}")
        
        print("❌ ВСЕ SCOPE провалены!")
    
    def test_token(self):
        """Тест токена"""
        if not self.token:
            return False
        
        url = "https://gigachat.api.sber.ru/chat/completions"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        data = {
            "model": "GigaChat-Pro",
            "messages": [{"role": "user", "text": "Тест"}],
            "stream": False
        }
        
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=15, verify=False)
            print(f"🔍 GigaChat тест: {resp.status_code}")
            if resp.status_code == 200:
                print("✅ GigaChat РАБОТАЕТ!")
                return True
            print(f"❌ GigaChat: {resp.status_code} - {resp.text[:100]}")
        except Exception as e:
            print(f"💥 GigaChat: {e}")
        return False
    
    def ask(self, question):
        if not self.token:
            return "❌ GigaChat: Проверь CLIENT_ID/CLIENT_SECRET в Render"
        
        url = "https://gigachat.api.sber.ru/chat/completions"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        data = {
            "model": "GigaChat-Pro",
            "messages": [
                {"role": "system", "text": "Ты турагент. Кратко. Бюджетные туры из России."},
                {"role": "user", "text": question}
            ],
            "stream": False,
            "temperature": 0.7
        }
        
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=20, verify=False)
            if resp.status_code == 200:
                return resp.json()['choices'][0]['message']['content'].strip()
            elif resp.status_code == 401:
                return "🔄 GigaChat 401. Перезапуск через 30 сек..."
        except:
            pass
        return "🔄 Ищу лучшие туры..."

# MAIN
def main():
    giga = GigaChatFix(CLIENT_ID, CLIENT_SECRET)
    
    # ТЕСТ ТОКЕНА
    if giga.test_token():
        print("✅ GigaChat готов!")
    else:
        print("⚠️ GigaChat недоступен (но бот работает)")
    
    vk_session = vk_api.VkApi(token=VK_TOKEN)
    longpoll = VkLongPoll(vk_session)
    
    print("🚀 VK Bot запущен! (Background Worker)")
    
    while True:
        try:
            for event in longpoll.check():
                if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                    user_id = event.user_id
                    text = event.text.lower()
                    print(f"\n👤 {user_id}: {text}")
                    
                    if any(word in text for word in ['египет', 'турция', 'море', 'отдых']):
                        answer = giga.ask(f"Бюджетный тур: {text}")
                    else:
                        answer = giga.ask(text)
                    
                    vk_session.method("messages.send", {
                        "user_id": user_id,
                        "message": answer,
                        "random_id": 0
                    })
                    print(f"🤖 {answer[:50]}...")
        except Exception as e:
            print(f"❌ {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
