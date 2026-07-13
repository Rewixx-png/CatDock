# 🔌 API Documentation (Internal V1)

Base URL: `https://catdock.catdock.io/api/v1`
Auth Header: `X-Web-Access-Token: <TOKEN>`

## 🔐 Auth (Публичные)
Эти методы не требуют токена.

*   `GET /auth/generate-token` — Создает временный токен для входа (DeepLink).
*   `GET /auth/check-token/<token>` — Проверяет статус токена (ожидает подтверждения в ТГ).
*   `GET /public/server_status` — Получить кешированный статус серверов (CPU/RAM/Load).

## 👤 User (Приватные)
Требуют `X-Web-Access-Token`.

*   `GET /user/dashboard` — **Главный метод.** Возвращает профиль, список контейнеров, баланс.
*   `GET /user/containers` — Список контейнеров.
*   `GET /user/container/<id>` — Детали контейнера (включая live-статистику Docker).
*   `POST /user/container/<id>/action` — Управление.
    *   Body: `{"action": "start" | "stop" | "restart"}`
*   `GET /user/container/<id>/logs` — Получить логи.
    *   Query: `?lines=100`

## 🛠 Admin (Приватные + Роль)
Требуют роль `ADMIN` и выше.

*   `GET /admin/users` — Список пользователей (пагинация).
*   `GET /admin/user/<id>` — Детали юзера.
*   `POST /admin/user/<id>/balance` — Изменить баланс.
    *   Body: `{"amount": 100}`
*   `POST /admin/user/<id>/give-container` — Выдать контейнер вручную.

---

## ⚡️ WebSockets
URL: `wss://catdock.catdock.io/ws/terminal?token=<TOKEN>`

Используется для веб-терминала к серверам нод. Доступно только `CO_OWNER`.