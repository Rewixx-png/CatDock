# 🛠 Руководство по установке CatDock

В этом документе описаны способы развертывания платформы:
1. **Автоматический (Рекомендуется):** Скрипт сделает всё сам.
2. **Ручной (Для экспертов):** Пошаговая настройка окружения.

---

## 📋 Требования

*   **ОС:** Ubuntu 20.04, 22.04 или 24.04 (LTS).
*   **Права:** `root` доступ.
*   **Ресурсы:** Минимум 1GB RAM, 1 vCPU.
*   **Порты:** 80, 443 (для Nginx), 8082 (API), 22 (SSH).

---

## 🚀 Способ 1: Автоматическая установка (One-Click)

Скрипт сам установит Docker, Node.js, Python, PostgreSQL, настроит конфиги и запустит бота вместе с воркером.

1. **Подключитесь к серверу** по SSH.
2. **Скачайте и запустите установщик:**

```bash
# Клонирование репозитория
git clone https://github.com/Rewixx-png/CatDock.git
cd CatDock

# Запуск мастера установки
chmod +x install.sh
./install.sh
```

3. **Следуйте инструкциям на экране.** Мастер попросит ввести:
   *   Токен бота (@BotFather).
   *   Ваш Telegram ID.
   *   Данные для базы данных (или сгенерирует их сам).

После завершения бот и воркер (RewWorker) запустятся автоматически.

---

## 🛠 Способ 2: Ручная установка

Если вы хотите контролировать каждый шаг или у вас нестандартное окружение.

### 1. Подготовка системы
Обновите пакеты и установите зависимости:

```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-dev git curl nodejs npm postgresql-client build-essential libpq-dev
```

### 2. Установка Docker
Если Docker еще не установлен:

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
rm get-docker.sh
```

### 3. Установка PM2 (Process Manager)
Нужен для фоновой работы бота.

```bash
npm install pm2 -g
```

### 4. Клонирование и Python-зависимости

```bash
git clone https://github.com/Rewixx-png/CatDock.git /root/Bots/CatDock
cd /root/Bots/CatDock

# Установка библиотек
pip3 install -r requirements.txt
```

### 5. Настройка конфигурации
Создайте файл `.env` на основе примера:

```bash
cp .env.example .env
nano .env
```
Заполните обязательные поля: `TELEGRAM_BOT_TOKEN`, `OWNER_IDS`, `PG_PASS`.

### 6. Запуск Базы Данных
Мы используем Docker Compose для PostgreSQL.

```bash
# Генерация docker-compose.yml (если его нет, или используйте готовый)
# Убедитесь, что пароль в .env совпадает с docker-compose.yml!

docker compose up -d
```

### 7. Применение миграций
Создайте таблицы в базе данных:

```bash
alembic upgrade head
```

### 8. Запуск бота и воркера
Используйте PM2 для управления процессами. Нам нужно два процесса: основной бот и TaskIQ воркер для фоновых задач.

```bash
# Запуск бота
pm2 start bot.py --name CatDock --interpreter python3

# Запуск воркера (обязательно!)
pm2 start "taskiq worker broker:broker" --name RewWorker --interpreter python3

# Сохранение списка процессов для автозапуска
pm2 save
pm2 startup
```

### 9. Создание CLI алиаса (Опционально)
Чтобы работала команда `RH`, добавьте алиас или создайте скрипт в `/usr/local/bin/RH`.
Пример см. в конце файла `install.sh`.

---

## 🕹 Управление (CLI)

После установки (любым способом) вам доступна команда `RH` (или `CatDock`).

| Команда | Описание |
| :--- | :--- |
| `RH logs` | **Живые логи.** Показывает логи бота и воркера. |
| `RH restart` | Перезагрузить всех (Бот + Воркер). |
| `RH stop` | Остановить всё. |
| `RH start` | Запустить всё. |
| `RH update` | **Авто-обновление.** `git pull` + миграции + рестарт всего. |
| `RH status` | Показать статус процессов в PM2. |