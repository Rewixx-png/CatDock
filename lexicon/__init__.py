import json
import os
import logging
import aiohttp
from config import PROJECT_ROOT
import settings

FACTORY_LOCALES_DIR = os.path.join(PROJECT_ROOT, 'locales') 
CACHE_LOCALES_DIR = settings.LOCALES_CACHE_DIR            

_FALLBACK: dict[str, str] = {
    # Common navigation and main flow.
    'welcome_text': 'Привет, {first_name}! Добро пожаловать в CatDock.',
    'welcome_text_new_user': 'Привет, {first_name}! Добро пожаловать в CatDock. Здесь можно создать и управлять UserBot.',
    'invalid_referral': '❌ Реферальная ссылка недействительна.',
    'unhandled_message': 'Не удалось распознать команду. Используйте меню или /help.',
    'action_canceled': '❌ Действие отменено.',
    'action_triggered': '✅ Действие запущено.',
    'loading_state_text': '⏳ Загружаю: {menu_name}…',
    'my_userbots_button': '🤖 Мои UserBot',
    'tariffs_button': '📦 Тарифы',
    'profile_button': '👤 Профиль',
    'deposit_button': '💰 Пополнить',
    'referral_button': '👥 Рефералы',
    'finance_button': '💳 Финансы',
    'admin_button': '⚙️ Админ',
    'admin_panel_button': '👑 Админ-панель',
    'support_button': '🎫 Поддержка',
    'back_button': '⬅️ Назад',
    'back_to_main_menu_button': '🏠 В главное меню',
    'back_to_admin_panel_button': '⬅️ В админ-панель',
    'back_to_containers_list_button': '⬅️ К списку контейнеров',
    'back_to_my_userbots_button': '⬅️ К моим UserBot',
    'back_to_profile_button': '⬅️ В профиль',
    'back_to_rinfo_button': '⬅️ К информации',
    'back_to_user_search_button': '⬅️ К поиску пользователей',
    'back_to_country_select': '⬅️ К выбору страны',
    'main_menu_button': '🏠 Главное меню',
    'cancel_button': '❌ Отмена',
    'confirm_button': '✅ Подтвердить',
    'no_back_button': '❌ Нет, назад',
    'yes_button': '✅ Да',
    'no_button': '❌ Нет',
    'refresh_button': '🔄 Обновить',
    'server_status_button': '📊 Статус серверов',
    'support_chat_button': '💬 Чат сообщества',
    'support_account_button': '👨‍💻 Поддержка',
    'support_welcome_message': '👋 Добро пожаловать в поддержку CatDock.',
    'support_prompt_question': 'Опишите проблему или вопрос одним сообщением.',
    'misc_menu_button': '🗂️ Меню',
    'ref_system_button': '👥 Рефералы',
    'settings_button': '⚙️ Настройки',
    'logout_button': '🚪 Выйти',

    # Container list and management.
    'my_userbots_title': '🤖 <b>Мои UserBot</b>',
    'my_userbots_select_bot': 'Выберите UserBot для управления:',
    'my_userbots_no_bots': 'У вас пока нет UserBot.',
    'turn_on_button': '▶️ Запустить',
    'turn_off_button': '⏹️ Остановить',
    'restart_button': '🔄 Перезапустить',
    'freeze_button': '❄️ Заморозить',
    'unfreeze_button': '☀️ Разморозить',
    'delete_button': '🗑️ Удалить',
    'get_logs_button': '📋 Логи и терминал',
    'login_button': '🖥️ CatDock Terminal',
    'interactive_login_button': '💬 Интерактивный вход',
    'change_name_button': '📝 Сменить имя',
    'change_image_button': '🖼️ Сменить образ',
    'change_server_button': '🌍 Сменить сервер',
    'admin_change_server_button': '⇄ Сменить сервер (админ)',
    'change_time_button': '⏳ Изменить время',
    'reinstall_button': '♻️ Переустановить',
    'extend_button': '⏳ Продлить',
    'upgrade_cpu_button': '⚡ Увеличить CPU',
    'upgrade_ram_button': '🧠 Увеличить RAM',
    'transfer_bot_button': '🎁 Передать контейнер',
    'status_blocked': '⛔ Заблокирован',
    'status_running': '🟢 Работает',
    'status_exited': '🔴 Остановлен',
    'status_restarting': '🟡 Перезапускается',
    'status_not_found': '⚫ Не найден',
    'status_error': '❌ Ошибка',
    'status_frozen': '❄️ Заморожен',
    'status_loading': '⏳ Загружается',
    'session_status_active': '✅ Сессия найдена',
    'session_status_not_found': '⚠️ Сессия не найдена',
    'session_status_error': '❌ Ошибка проверки сессии',
    'transfer_status_active': '✅ Доступен',
    'transfer_status_pending': '⏳ Ожидает передачи',
    'not_found_explanation': '\n⚠️ Контейнер отсутствует на сервере. Обратитесь в поддержку.',
    'orphaned_container_warning': '\n⚠️ Сервер «{server_name}» недоступен или удалён из конфигурации.',
    'cpu_status_normal': '✅ Норма',
    'cpu_status_high': '⚠️ Высокая нагрузка',
    'cpu_stats_format': 'CPU: {usage:.2f}% / {limit:.2f}% — {status}',
    'container_stats_text': '{cpu_stats}\nRAM: {ram_stats}',
    'manage_userbot_info': (
        '🤖 <b>{container_name}</b> (ID: <code>{container_id}</code>)\n'
        '🌍 Сервер: {server_name}\n📦 Тариф: {tariff_name}\n🧠 RAM: {actual_ram_mb} MB\n'
        '🖼️ Образ: {image_name}\n⚙️ Статус: {status_text}\n🎁 Передача: {transfer_status}\n'
        '⏳ Осталось: {remaining_time}\n🔐 Сессия: {session_status_text}'
    ),
    'delete_confirm_step1_text': '⚠️ Вы действительно хотите удалить этот UserBot?',
    'delete_confirm_step2_text': '🚨 Это действие необратимо. Подтвердите окончательное удаление.',
    'delete_agree_button': 'Да, удалить',
    'delete_final_confirm_button': '🗑️ Удалить навсегда',
    'reinstall_confirm_text': '♻️ Переустановка удалит текущие данные контейнера. Продолжить?',
    'change_name_prompt': 'Введите новое имя контейнера (4–29 символов: латиница, цифры, ., _ или -).',
    'change_name_error_length': '❌ Имя должно содержать от 4 до 29 символов.',
    'change_name_error_chars': '❌ Используйте только латиницу, цифры, точку, дефис и подчёркивание.',
    'change_name_error_taken': '❌ Такое имя уже занято.',
    'change_name_error_generic': '❌ Не удалось изменить имя контейнера.',
    'change_name_success': '✅ Имя контейнера изменено.',
    'change_image_prompt': 'Выберите новый образ UserBot:',
    'confirm_image_change_prompt': 'Сменить образ на {image_name}?',
    'change_server_prompt': 'Выберите новый сервер:',
    'confirm_server_change_prompt': 'Перенести контейнер на сервер {server_name}?',
    'free_action_note': 'Это действие бесплатно.',

    # Container creation.
    'hub_tariff_select': '📦 Выбрать тариф',
    'hub_image_select': '🖼️ Выбрать образ',
    'hub_manual_server': '🌍 Выбрать сервер вручную',
    'hub_ready_create': '✅ Перейти к созданию',
    'hub_not_ready': '⚠️ Сначала выберите тариф и образ',
    'confirm_creation_button': '🚀 Создать UserBot',
    'tariffs_step4_prompt_title': '<b>Шаг 4/4:</b> Проверьте параметры заказа.\n\n',
    'tariffs_step4_prompt_footer': '\n\nПодтвердите создание UserBot.',
    'free_tariff_days': 'Бесплатно (2 дня)',
    'install_button': '📥 Установить',

    # Extension and upgrades.
    'extend_prompt': '⏳ <b>Продление UserBot</b>\nВыберите срок продления:',
    'extend_plan_button': '{months} мес. — {price:.2f} ₽ (скидка {discount}%)',
    'extend_free_not_allowed': 'Бесплатный контейнер нельзя продлить.',
    'extend_cpu_surcharge_info': '\n⚡ Доплата за CPU {cpu_percent}%: {cpu_cost:.2f} ₽',
    'extend_ram_surcharge_info': '\n🧠 Доплата за RAM {actual_ram} MB: {ram_cost:.2f} ₽',
    'extend_insufficient_funds': '❌ Недостаточно средств. Нужно {cost:.2f} ₽, на балансе {balance:.2f} ₽.',
    'extend_success': '✅ Срок работы UserBot успешно продлён.',
    'upgrade_cpu_prompt': 'Введите новый лимит CPU для контейнера:',
    'admin_upgrade_cpu_prompt_id': 'Введите ID контейнера для изменения CPU:',

    # Transfers.
    'transfer_confirm_text': 'Передать этот контейнер другому пользователю?',
    'transfer_confirm_button': '✅ Создать ссылку передачи',
    'transfer_link_btn': '🔗 Ссылка на передачу',
    'transfer_cancel_btn': '❌ Отменить передачу',
    'transfer_link_message': '🎁 Ссылка для передачи создана. Отправьте её новому владельцу.',
    'transfer_canceled': '✅ Передача контейнера отменена.',
    'transfer_free_error': 'Бесплатный контейнер нельзя передать.',
    'transfer_token_not_found': '❌ Ссылка передачи недействительна или устарела.',
    'transfer_self_claim': '❌ Нельзя передать контейнер самому себе.',
    'transfer_claim_success_new_owner': '✅ Контейнер {container_name} теперь принадлежит вам.',
    'transfer_claim_success_old_owner': '✅ Контейнер {container_name} передан пользователю {new_owner_name}.',

    # Profile, referral and settings.
    'profile_text': (
        '👤 <b>Профиль</b>\n\nID: <code>{user_id}</code>\nИмя: {first_name}\n'
        'Username: @{username}\nРоль: {role}\nБаланс: {balance:.2f} ₽\n'
        'Реферальный баланс: {ref_balance:.2f} ₽\nДата регистрации: {reg_date}'
    ),
    'error_profile_not_found': '❌ Профиль пользователя не найден.',
    'profile_settings_button': '⚙️ Настройки профиля',
    'change_lang_button': '🌐 Сменить язык',
    'custom_photo_button': '🖼️ Пользовательская фотография',
    'referral_text': (
        '👥 <b>Реферальная программа</b>\n\nВаша ставка: {ref_percent}%\n'
        'Приглашено: {ref_count}\n{referrer_info}\n\nСсылка: {ref_link}'
    ),
    'referrer_info_who': 'Вас пригласил: {referrer_name}',
    'referrer_info_self': 'Вы зарегистрировались самостоятельно.',
    'referral_upgrade_promo': 'Улучшите реферальную программу и получайте 40% навсегда.',
    'upgrade_referral_button': '⬆️ Улучшить за {price} ₽',
    'referral_confirm_upgrade_text': 'Улучшить реферальную программу за {price} ₽?',
    'insufficient_funds_for_upgrade': '❌ Недостаточно средств для улучшения.',
    'referral_upgrade_success': '✅ Реферальная программа улучшена.',
    'bonuses_header': '\n\n<b>✨ Активные бонусы:</b>',
    'bonus_row_discount': '\n📉 Скидка: <b>{percent}%</b> (код {code})',
    'bonus_row_deposit': '\n💰 Бонус к пополнению: <b>+{percent}%</b> (код {code})',
    'bonus_row_free_cont': '\n📦 Бесплатный контейнер (код {code})',

    # Deposit and withdrawal.
    'withdraw_button': '💸 Вывести',
    'method_select': '💳 Выбрать способ',
    'amount_select': '💰 Указать сумму',
    'deposit_confirm': '✅ Подтвердить пополнение',
    'cards_button': '💳 Банковская карта',
    'sbp_button': '📱 СБП',
    'stars_button': '⭐ Telegram Stars',
    'crypto_pay_button': '💎 Crypto Pay',
    'russian_cards': '🇷🇺 Российские карты',
    'ukrainian_cards': '🇺🇦 Украинские карты',
    'choose_country_prompt': 'Выберите страну карты:',
    'choose_bank_prompt': 'Выберите банк:',
    'enter_bank_name': 'Введите название банка:',
    'enter_star_amount_prompt': 'Введите количество Telegram Stars для оплаты:',
    'enter_crypto_amount_prompt': 'Введите сумму пополнения в рублях через Crypto Pay:',
    'i_paid_button': '✅ Я оплатил',
    'go_to_payment_button': '💳 Перейти к оплате',
    'check_payment_button': '🔄 Проверить оплату',
    'sbp_payment_instruction': (
        'Переведите <b>{amount:.2f} ₽</b> по СБП на номер <code>{phone_number}</code>, '
        'затем нажмите «{paid_button_text}».'
    ),
    'card_payment_instruction': (
        'Переведите <b>{amount:.2f} ₽</b> в банк {bank_name} на карту '
        '<code>{card_number}</code>, затем нажмите «{paid_button_text}».'
    ),
    'deposit_request_accepted': '✅ Заявка на пополнение принята и отправлена администратору.',
    'crypto_invoice_created': '✅ Счёт создан. Оплатите его и нажмите кнопку проверки.',
    'crypto_api_error': '❌ Не удалось создать счёт Crypto Pay.',
    'star_invoice_title': 'Пополнение CatDock',
    'star_invoice_description': 'Пополнение на {rub_equivalent:.2f} ₽ ({star_amount} Stars).',
    'admin_approve': '✅ Одобрить',
    'admin_decline': '❌ Отклонить',
    'admin_approve_withdrawal': '✅ Одобрить вывод',
    'admin_decline_withdrawal': '❌ Отклонить вывод',

    # Telegram session generator.
    'string_session_button': '🔐 StringSession',
    'session_menu_title': '🔐 <b>Управление Telegram-сессиями</b>',
    'session_generate_new': '➕ Создать сессию',
    'session_view_saved': '📂 Сохранённые сессии',
    'session_download_all': '📥 Скачать все',
    'session_skip_comment_button': '⏭️ Пропустить комментарий',
    'session_enter_api_id': 'Введите Telegram API ID:',
    'session_invalid_api_id': '❌ API ID должен быть положительным числом.',
    'session_enter_api_hash': 'Введите Telegram API Hash:',
    'session_enter_phone': 'Введите номер телефона в международном формате:',
    'session_sending_code': '⏳ Отправляю код подтверждения…',
    'session_enter_code': 'Введите код из Telegram:',
    'session_enter_password': 'Введите пароль двухэтапной аутентификации:',
    'session_success_title': '✅ Авторизация успешна.',
    'session_enter_comment_prompt': 'Добавьте комментарий к сессии или пропустите шаг.',
    'session_saved_success': '✅ Сессия сохранена.',
    'session_string_is': 'Строка сессии:',
    'session_list_title': '📂 <b>Сохранённые сессии</b>',
    'session_no_saved_sessions': 'У вас нет сохранённых сессий.',
    'session_deleted_success': '✅ Сессия удалена.',
    'session_download_caption': 'Архив ваших Telegram-сессий.',
    'session_generic_error': '❌ Ошибка Telegram: {error}',

    # Inline mode.
    'inline_action_description': 'Выполнить действие для {name}',
    'inline_bot_selected_text': 'Выбран UserBot: {name}',
    'inline_create_bot_button': '➕ Создать UserBot',
    'inline_no_bots_title': 'UserBot не найдены',
    'inline_no_bots_description': 'Откройте CatDock и создайте первый UserBot.',
    'inline_select_bot_button': '🤖 Выбрать UserBot',

    # Admin navigation and settings.
    'manage_users_button': '👥 Пользователи',
    'manage_containers_button': '📦 Контейнеры',
    'bot_settings_button': '⚙️ Настройки бота',
    'mailing_button': '📣 Рассылка',
    'news_button_title': '📰 Новости',
    'bot_settings_title': '⚙️ <b>Настройки бота</b>',
    'toggle_maintenance_button': '🛠️ Режим обслуживания',
    'toggle_raid_button': '🛡️ Антирейд',
    'clear_cache_button': '🧹 Очистить кэш',
    'maintenance_mode_on': '✅ Режим обслуживания включён.',
    'maintenance_mode_off': '✅ Режим обслуживания выключен.',
    'raid_mode_on': '✅ Антирейд включён.',
    'raid_mode_off': '✅ Антирейд выключен.',
    'cache_cleared_notification': '✅ Кэш очищен.',
    'restart_confirmation_text': 'Перезапустить CatDock?',
    'restart_initiated_alert': '🔄 Перезапуск запущен.',
    'roles_info_text': '👑 <b>Роли администрации</b>\nРоли определяют доступ к разделам управления.',
    'terminal_exit_button': '🚪 Выйти из терминала',

    # Broadcasts.
    'broadcast_prompt_text': 'Введите текст рассылки:',
    'broadcast_prompt_media_q': 'Добавить медиафайл?',
    'broadcast_prompt_media_send': 'Отправьте фото, видео или документ.',
    'broadcast_prompt_button_q': 'Добавить кнопку-ссылку?',
    'broadcast_prompt_button_text': 'Введите текст кнопки:',
    'broadcast_prompt_button_url': 'Введите URL кнопки:',
    'broadcast_invalid_url': '❌ Некорректный URL.',
    'broadcast_confirmation_title': '📣 <b>Подтверждение рассылки</b>',
    'broadcast_preview_label': 'Предпросмотр сообщения:',
    'confirm_broadcast_button': '✅ Запустить рассылку',
    'broadcast_start_message': '🚀 Рассылка запущена.',
    'broadcast_progress_update': '📨 Отправлено {sent} из {total}.',
    'broadcast_finish_message': '✅ Рассылка завершена. Отправлено: {sent}, ошибок: {failed}.',

    # Admin users.
    'search_by_id_button': '🔎 Поиск по ID',
    'user_list_title': '👤 <b>Список пользователей</b> — страница {page}/{total_pages}',
    'show_userbots_button': '🤖 Показать UserBot',
    'change_balance_button': '💰 Изменить баланс',
    'give_container_button': '📦 Выдать контейнер',
    'change_role_button': '👑 Изменить роль',
    'block_user_button': '🚫 Заблокировать',
    'unblock_user_button': '✅ Разблокировать',
    'delete_user_fully_button': '🗑️ Удалить пользователя',
    'delete_user_confirm_button': '🗑️ Подтвердить удаление',
    'delete_user_confirm_text': 'Удалить пользователя {name} (ID {id}) и все его данные?',
    'user_deleted_success': '✅ Пользователь {user_id} удалён.',
    'user_is_blocked_status': 'ЗАБЛОКИРОВАН 🚫',
    'user_is_not_blocked_status': 'Активен ✅',
    'error_cannot_block_admin': 'Нельзя блокировать администратора равной или более высокой роли.',
    'error_cannot_assign_equal_or_higher': 'Нельзя назначить роль, равную или выше вашей.',
    'error_cannot_demote_equal_or_higher': 'Нельзя изменить пользователя равной или более высокой роли.',
    'error_co_owner_permission_denied': 'Только владелец может управлять совладельцами.',
    'change_role_prompt': 'Выберите новую роль:',
    'role_changed_message': '✅ Роль изменена на {role_name}.',
    'admin_changed_role_notification': 'Ваша роль в CatDock изменена на {role_name}.',
    'admin_changed_balance_notification': 'Баланс изменён на {amount:+.2f} ₽. Новый баланс: {new_balance:.2f} ₽.',
    'user_was_blocked_message': '✅ Пользователь заблокирован.',
    'user_was_unblocked_message': '✅ Пользователь разблокирован.',
    'user_blocked_notification': '🚫 Ваш аккаунт CatDock заблокирован администратором.',

    # Admin containers.
    'admin_container_list_button': '📋 Список контейнеров',
    'give_admin_container_button': '🎁 Выдать админ-контейнер',
    'admin_containers_menu_title': '📦 <b>Управление контейнерами</b>',
    'admin_container_list_title': '📋 <b>Список контейнеров</b>',
    'admin_containers_not_found': 'Контейнеры не найдены.',
    'sort_by_time_button': '⏳ По времени',
    'sort_by_ram_button': '🧠 По RAM',
    'sort_by_price_button': '💰 По тарифу',
    'prev_page_button': '⬅️ Назад',
    'next_page_button': 'Вперёд ➡️',
    'search_container_by_id_button': '🔎 Поиск по ID',
    'search_by_name': '🔎 Поиск по имени',
    'admin_prompt_container_id': 'Введите ID контейнера:',
    'admin_container_not_found': '❌ Контейнер с ID {container_id} не найден.',
    'admin_changed_container_time_notification': 'Срок контейнера {container_name} изменён на {days} дн.',
    'admin_upgrade_cpu_prompt_id': 'Введите ID контейнера для изменения CPU:',
    'admin_change_server_prompt': 'Выберите новый сервер для контейнера:',
    'admin_confirm_server_change_prompt': 'Перенести контейнер на сервер {server_name}?',
    'admin_move_success_user_notification': 'Ваш контейнер {container_name} перенесён на другой сервер.',
    'admin_gave_container_notification': 'Вам выдан контейнер {container_name} на сервере {server_name}.',
    'give_admin_container_prompt_user': 'Введите ID или username пользователя:',
    'give_admin_container_user_not_found': '❌ Пользователь не найден.',
    'give_admin_container_prompt_server': 'Выберите сервер:',
    'give_admin_container_prompt_image': 'Выберите образ:',
    'give_admin_container_confirm_text': (
        'Выдать админ-контейнер пользователю {user_name} (ID {user_id})?\n'
        'Сервер: {server_name}\nОбраз: {image_name}'
    ),
    'confirm_give_button': '✅ Выдать',
    'admin_container_issued_success': '✅ Контейнер {container_name} выдан пользователю {user_id}.',
    'admin_container_issued_notification': 'Вам выдан админ-контейнер {container_name}.',

    # Server management.
    'server_add': '➕ Добавить сервер',
    'server_edit': '✏️ Изменить сервер',
    'server_delete': '🗑️ Удалить сервер',
    'server_edit_name': '📝 Изменить имя',
    'server_edit_ip': '🌐 Изменить IP',
    'server_edit_pass': '🔑 Изменить пароль',
    'server_edit_port': '🔌 Изменить порт',
    'server_back_select': '⬅️ К выбору сервера',
    'server_delete_confirm': '⚠️ Подтвердить удаление сервера',

    # Orphan/restart-loop tools.
    'orphans_not_found': '✅ Потерянные контейнеры не найдены.',
    'orphans_found_text': '⚠️ Найдено потерянных контейнеров: {count}.',
    'orphans_delete_button': '🗑️ Удалить найденные ({count})',
    'orphans_confirm_deletion': 'Удалить записи потерянных контейнеров?',
    'fixloop_scan_start': '🔎 Проверяю контейнеры в цикле перезапуска…',
    'fixloop_scan_no_results': '✅ Контейнеры в цикле перезапуска не найдены.',
    'fixloop_scan_results_title': '⚠️ Найдено проблемных контейнеров: {count}.',
    'fixloop_confirm_deletion': 'Удалить проблемный контейнер {container_name}?',
    'fixloop_deleted_success': '✅ Проблемный контейнер удалён.',
    'fixloop_deleted_error': '❌ Не удалось удалить проблемный контейнер.',
    'fixloop_user_notification': 'Ваш контейнер {container_name} удалён из-за бесконечного цикла перезапуска.',
    'admin_unfreeze_all_confirm': 'Разморозить все контейнеры ({count})?',
    'admin_unfreeze_all_reason_prompt': 'Укажите причину массовой разморозки:',
    'admin_unfreeze_all_started': '🚀 Запущена разморозка {count} контейнеров.',
    'admin_unfreeze_all_progress': '⏳ Обработано {processed} из {total}.',
    'admin_unfreeze_all_finished': '✅ Разморожено: {unfrozen_count}, ошибок: {error_count}.',
    'user_mass_unfreeze_notification': 'Контейнер {container_name} разморожен администратором. Причина: {reason}',

    # Admin diagnostics and support.
    'image_update_select_server': 'Выберите сервер для обновления образов:',
    'image_update_confirm': 'Обновить образы на сервере {server_name}?',
    'admin_take_ticket': '🙋 Взять обращение',
    'admin_send_answer': '📨 Отправить ответ',
    'admin_edit_answer': '✏️ Изменить ответ',
    'error_insufficient_permissions': '❌ Недостаточно прав для этого действия.',
    'error_unhandled_notification': 'Произошла непредвиденная ошибка. Данные уже записаны в лог.',
    'rinfo_header': '👤 <b>Информация о пользователе</b>',
    'rinfo_no_userbots': 'У пользователя нет UserBot.',
    'rinfo_user_not_in_db': 'Пользователь не найден в базе CatDock.',
}


class _LocaleDict(dict[str, str]):
    """Locale mapping that cannot raise KeyError for a missing text key."""

    def __missing__(self, key: str) -> str:
        value = _FALLBACK.get(key, f'⚠️ Перевод «{key}» временно недоступен')
        self[key] = value
        return value


class _LexiconRegistry(dict[str, _LocaleDict]):
    """Unknown language codes safely fall back to Russian."""

    def __missing__(self, key: str) -> _LocaleDict:
        logging.warning("Unsupported locale %r; falling back to ru", key)
        return self['ru']


LEXICON: _LexiconRegistry = _LexiconRegistry({
    lang: _LocaleDict(_FALLBACK)
    for lang in settings.SUPPORTED_LANGUAGES
})

def _load_from_dir(directory: str):
    """Читает JSON-файлы из указанной директории и обновляет LEXICON."""
    global LEXICON
    if not os.path.exists(directory):
        return

    for lang in settings.SUPPORTED_LANGUAGES:
        lang_path = os.path.join(directory, lang)

        if os.path.isdir(lang_path):
            for filename in os.listdir(lang_path):
                if filename.endswith(".json"):
                    file_path = os.path.join(lang_path, filename)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            LEXICON[lang].update(data)
                    except Exception as e:
                        logging.error(f"❌ Failed to load locale {lang}/{filename}: {e}")

        elif os.path.exists(lang_path + ".json"):
            try:
                with open(lang_path + ".json", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    LEXICON[lang].update(data)
            except Exception as e:
                logging.error(f"❌ Failed to load legacy locale {lang}.json: {e}")

def load_lexicon():
    """
    Загружает лексикон.
    Приоритет:
    1. Кэш (storage/locales) - самые свежие файлы.
    2. Заводские (locales/) - если кэша нет или ключи отсутствуют.
    """
    
    _load_from_dir(FACTORY_LOCALES_DIR)

    _load_from_dir(CACHE_LOCALES_DIR)

    logging.info(f"📚 Lexicon loaded. RU keys: {len(LEXICON['ru'])}, EN: {len(LEXICON['en'])}")

async def sync_lexicon():
    """
    Асинхронно скачивает актуальные файлы переводов с GitHub
    и сохраняет их в storage/locales.
    """
    if not settings.LOCALES_REPO_URL:
        logging.info("ℹ️ Remote locale sync disabled; bundled fallback is active.")
        return

    logging.info("🌍 Syncing lexicon from GitHub...")
    os.makedirs(CACHE_LOCALES_DIR, exist_ok=True)
    
    updated_count = 0
    errors_count = 0

    async with aiohttp.ClientSession() as session:
        for lang in settings.SUPPORTED_LANGUAGES:
            lang_dir = os.path.join(CACHE_LOCALES_DIR, lang)
            os.makedirs(lang_dir, exist_ok=True)

            for filename in settings.LOCALE_FILES:
                url = f"{settings.LOCALES_REPO_URL}/{lang}/{filename}.json"
                target_path = os.path.join(lang_dir, f"{filename}.json")
                
                try:
                    async with session.get(url) as response:
                        if response.status == 200:
                            content = await response.read()
                            
                            try:
                                json.loads(content)
                                with open(target_path, "wb") as f:
                                    f.write(content)
                                updated_count += 1
                            except json.JSONDecodeError:
                                logging.error(f"⚠️ Invalid JSON from GitHub: {url}")
                                errors_count += 1
                        else:
                            
                            pass
                except Exception as e:
                    logging.warning(f"Failed to download {url}: {e}")
                    errors_count += 1
    
    if updated_count > 0:
        logging.info(f"✅ Lexicon updated: {updated_count} files downloaded. Reloading...")
        load_lexicon()
    else:
        logging.info("ℹ️ Lexicon sync finished (no new files or error).")

load_lexicon()
