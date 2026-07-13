#!/bin/bash

echo "🛠 Генерация свежего токена..."
./scripts/run.sh scripts/tools/create_debug_token.py

if [ ! -f /tmp/catdock_debug_token ]; then
    echo "❌ Не удалось создать токен. Проверь логи выше."
    exit 1
fi

TOKEN=$(cat /tmp/catdock_debug_token)
echo "📡 Проверка API с токеном: $TOKEN"

echo "1. Проверка Python-бэкенда (напрямую 127.0.0.1:8082)..."
RESPONSE_PY=$(curl -s -X GET "http://127.0.0.1:8082/api/v1/user/dashboard" -H "X-Web-Access-Token: $TOKEN")

if [[ $RESPONSE_PY == *"success"* ]]; then
    echo "✅ Python API: РАБОТАЕТ!"
else
    echo "❌ Python API: ОШИБКА!"
    echo "Ответ: $RESPONSE_PY"
    exit 1
fi

echo ""
echo "2. Проверка через Nginx (https://catdock.catdock.io)..."
RESPONSE_NGINX=$(curl -s -X GET "https://catdock.catdock.io/api/v1/user/dashboard" -H "X-Web-Access-Token: $TOKEN")

if [[ $RESPONSE_NGINX == *"success"* ]]; then
    echo "✅ Nginx Proxy: РАБОТАЕТ!"
    echo ""
    echo "🎉 ВСЁ РАБОТАЕТ! Если в браузере ошибка — это 100% кеш браузера."
    echo "👉 РЕШЕНИЕ: Открой сайт, нажми F12 -> Application -> Local Storage -> catdock.catdock.io"
    echo "   Измени значение 'catDockApiKey' на:"
    echo "   $TOKEN"
    echo "   И обнови страницу."
else
    echo "❌ Nginx Proxy: ОШИБКА!"
    echo "Ответ (первые 200 символов): ${RESPONSE_NGINX:0:200}..."
    echo "Возможно, проблема в SSL или конфиге Nginx."
fi
