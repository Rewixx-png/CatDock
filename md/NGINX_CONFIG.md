# 🌐 Настройка Веб-Сервера (Nginx)

В этом документе описана конфигурация продакшен-окружения для CatDock.

### 📂 Структура папок
*   **Репозиторий:** Исходный код фронтенда находится в папке `/web`.
*   **Продакшен (Сервер):** Содержимое папки `/web` должно быть размещено (или слинковано) в `/var/www/CatDock`.

> **Важно:** Nginx отдает статику (HTML, CSS, JS) напрямую из `/var/www/CatDock` для максимальной производительности. Python-бекэнд (Quart) используется только для API и WebSocket.

---

### ⚙️ Конфигурация Nginx
Файл: `/etc/nginx/sites-available/catdock.catdock.io`

Эта конфигурация реализует:
1.  **Clean URLs:** Превращает пути типа `/profile` в реальные файлы `/templates/profile/index.html`.
2.  **Reverse Proxy:** Перенаправляет запросы `/api/` и `/ws/` на локальный порт бота (8082) с поддержкой WebSocket.
3.  **SSL:** Настроены сертификаты Let's Encrypt.
4.  **Assets:** Правильная отдача статики с кэшированием.

```nginx
server {
    server_name catdock.catdock.io;
    
    # Корень проекта (для статики)
    root /var/www/CatDock;
    
    # Логи
    access_log /var/log/nginx/catdock_access.log;
    error_log /var/log/nginx/catdock_error.log;

    # --- ТЮНИНГ (Для стабильности) ---
    client_max_body_size 50M;
    client_body_buffer_size 128k;
    proxy_buffer_size 128k;
    proxy_buffers 8 256k;
    proxy_busy_buffers_size 256k;
    proxy_connect_timeout 300;
    proxy_send_timeout 300;
    proxy_read_timeout 300;
    send_timeout 300;

    # =========================================
    # 1. СТАТИКА (Nginx отдает файлы сам - быстро)
    # =========================================
    # CSS, JS, Картинки интерфейса
    location /assets/ {
        alias /var/www/CatDock/assets/;
        expires 7d;
        add_header Cache-Control "public, no-transform";
        try_files $uri =404;
    }

    # Загрузки (Аватарки и т.д.)
    location /uploads/ {
        alias /var/www/CatDock/web/uploads/; 
        try_files $uri =404;
    }

    # Фавиконка
    location = /favicon.ico {
        log_not_found off;
        access_log off;
    }

    # Файл проверки для SSL (Certbot)
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # =========================================
    # 2. PROXY PASS (Всё остальное летит в Python)
    # =========================================
    # Этот блок ловит ВСЕ страницы: /, /login, /profile, /admin, /games...
    location / {
        proxy_pass http://127.0.0.1:8082;
        
        # Заголовки для правильной работы IP и HTTPS внутри Python
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # =========================================
    # 3. WEBSOCKET (Терминал, Игры - старый путь)
    # =========================================
    location /ws/ {
        proxy_pass http://127.0.0.1:8082;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # =========================================
    # 4. API & DOCS (ИСПРАВЛЕНО: Добавлены WS заголовки)
    # =========================================
    # Это чинит ошибку 426 для /api/v1/games/durak/ws/...
    location /api/ {
        proxy_pass http://127.0.0.1:8082;

        # --- ВАЖНО ДЛЯ WEBSOCKET ---
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        # ---------------------------

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SSL НАСТРОЙКИ
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/catdock.catdock.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/catdock.catdock.io/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

# РЕДИРЕКТ HTTP -> HTTPS
server {
    if ($host = catdock.catdock.io) { return 301 https://$host$request_uri; }
    listen 80;
    server_name catdock.catdock.io;
    return 404;
}