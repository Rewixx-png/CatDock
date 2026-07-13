from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from lexicon import LEXICON
from config import CARD_PAYMENT_DETAILS, SUBSCRIPTION_PLANS, SERVERS, WEB_APP_URL

def get_profile_keyboard(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(text=lex.get('deposit_button', 'deposit_button'), callback_data="add_balance"),
        types.InlineKeyboardButton(text=lex.get('withdraw_button', 'withdraw_button'), callback_data="withdraw")
    )

    builder.row(
        
        types.InlineKeyboardButton(text=lex.get('ref_system_button', 'ref_system_button'), callback_data="ref_system")
    )

    builder.row(
        types.InlineKeyboardButton(text=lex.get('string_session_button', '📝 Сессии'), callback_data="string_session_menu")
    )

    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_main_menu_button', 'back_to_main_menu_button'), callback_data="back_to_main_menu"))
    return builder.as_markup()

def get_deposit_hub_keyboard(language_code: str, selection_data: dict) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    selected_method = selection_data.get('method_id')
    selected_amount = selection_data.get('amount')

    method_text = f"✅ Метод: {selected_method}" if selected_method else lex.get('method_select', '💳 Выбрать метод')
    amount_text = f"✅ {selected_amount} RUB" if selected_amount else lex.get('amount_select', '💵 Сумма')

    builder.row(
        types.InlineKeyboardButton(text=method_text, callback_data="deposit_select:method"),
        types.InlineKeyboardButton(text=amount_text, callback_data="deposit_select:amount")
    )

    if selected_method and selected_amount:
        builder.row(types.InlineKeyboardButton(text=lex.get('deposit_confirm', '🚀 Перейти к оплате'), callback_data="deposit_hub:confirm"))
    else:
        builder.row(types.InlineKeyboardButton(text=lex.get('hub_not_ready', '⏳ Заполните данные'), callback_data="deposit_hub:incomplete"))

    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_profile_button', 'back_to_profile_button'), callback_data="profile"))
    return builder.as_markup()

def get_payment_methods_keyboard(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    builder.row(
        types.InlineKeyboardButton(text=lex.get('crypto_pay_button', '💎 Crypto Pay'), callback_data="deposit_set_method:crypto"),
        types.InlineKeyboardButton(text=lex.get('stars_button', '⭐ Stars'), callback_data="deposit_set_method:stars")
    )

    builder.row(
        types.InlineKeyboardButton(text=lex.get('sbp_button', 'sbp_button'), callback_data="deposit_set_method:sbp"),
        types.InlineKeyboardButton(text=lex.get('cards_button', 'cards_button'), callback_data="deposit_set_method:cards")
    )

    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="deposit_hub:back"))
    return builder.as_markup()

def get_country_selection_keyboard(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text=lex.get('russian_cards', "🇷🇺 РФ"), callback_data="select_country:ru"),
        types.InlineKeyboardButton(text=lex.get('ukrainian_cards', "🇺🇦 Украина"), callback_data="select_country:ua")
    )
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="deposit_hub:back"))
    return builder.as_markup()

def get_card_selection_keyboard(country_code: str, language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    cards = CARD_PAYMENT_DETAILS.get(country_code, [])
    for idx, card in enumerate(cards):
        builder.row(types.InlineKeyboardButton(text=f"🏦 {card['bank']}", callback_data=f"select_card:{country_code}:{idx}"))

    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_country_select', '⬅️ Назад'), callback_data="deposit_select:country_bank"))
    return builder.as_markup()

def get_session_management_keyboard(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=lex.get('session_generate_new', '➕ Создать'), callback_data="session_generate"))
    builder.row(types.InlineKeyboardButton(text=lex.get('session_view_saved', '📄 Мои сессии'), callback_data="session_view"))
    builder.row(types.InlineKeyboardButton(text=lex.get('session_download_all', '📥 Скачать'), callback_data="session_download"))
    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_profile_button', 'back_to_profile_button'), callback_data="profile"))
    return builder.as_markup()

def get_card_payment_confirmation_keyboard(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=lex.get('i_paid_button', 'i_paid_button'), callback_data="card_payment_confirmed"))
    builder.row(types.InlineKeyboardButton(text=lex.get('cancel_button', 'cancel_button'), callback_data="cancel_payment"))
    return builder.as_markup()

def get_referral_menu_keyboard(has_advanced: bool, language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    if not has_advanced:
        builder.row(types.InlineKeyboardButton(text=lex.get('upgrade_referral_button', '🚀 Upgrade').format(price=75), callback_data="upgrade_referral_confirm"))
    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_profile_button', 'back_to_profile_button'), callback_data="profile"))
    return builder.as_markup()

def get_bonus_container_selection_keyboard(containers: list, language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for c in containers:
        builder.row(types.InlineKeyboardButton(text=f"📦 {c['container_name']}", callback_data=f"bonus_container:{c['id']}"))
    builder.row(types.InlineKeyboardButton(text=lex.get('back_to_profile_button', 'back_to_profile_button'), callback_data="profile"))
    return builder.as_markup()

def get_settings_menu_keyboard(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=lex.get('profile_settings_button', '🎨 Вид профиля'), callback_data="profile_settings"))
    builder.row(types.InlineKeyboardButton(text=lex.get('change_lang_button', 'change_lang_button'), callback_data="change_lang"))
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'Назад'), callback_data="misc_menu"))
    return builder.as_markup()

def get_profile_settings_keyboard(settings: dict, language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    toggles = {
        'show_id': 'ID',
        'show_name': 'Имя',
        'show_username': 'Username',
        'show_role': 'Роль',
        'show_userbots': 'UserBots',
        'show_main_balance': 'Осн. баланс',
        'show_ref_balance': 'Реф. баланс',
    }

    buttons_row1 = []
    buttons_row2 = []

    for key, text in toggles.items():
        if key in ['use_custom_photo', 'use_old_banners']: continue
        state = "✅" if settings.get(key) else "❌"
        label = text 
        button = types.InlineKeyboardButton(text=f"{label}: {state}", callback_data=f"toggle_profile_setting:{key}")
        if len(buttons_row1) < 3:
            buttons_row1.append(button)
        else:
            buttons_row2.append(button)

    builder.row(*buttons_row1)
    if buttons_row2:
        builder.row(*buttons_row2)

    photo_icon = "✅" if settings.get('use_custom_photo') else "❌"
    builder.row(types.InlineKeyboardButton(
        text=lex.get('custom_photo_button', f"Кастомное фото {photo_icon}"),
        callback_data="toggle_profile_setting:use_custom_photo"
    ))

    style_text = "Старые (JPEG)" if settings.get('use_old_banners') else "Новые (PNG)"
    builder.row(types.InlineKeyboardButton(
        text=f"🖼 Баннеры: {style_text}",
        callback_data="toggle_profile_setting:use_old_banners"
    ))

    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="settings_menu"))
    return builder.as_markup()

def get_ticket_rating_keyboard(ticket_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.add(types.InlineKeyboardButton(text=f"{i} ⭐", callback_data=f"rate_ticket:{ticket_id}:{i}"))
    return builder.as_markup()

def get_session_view_keyboard(sessions: list, language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for s in sessions:
        builder.row(types.InlineKeyboardButton(text=f"📄 {s.get('comment', 'Session')}", callback_data="none"),
                    types.InlineKeyboardButton(text="🗑️", callback_data=f"session_delete:{s['id']}"))
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'Назад'), callback_data="string_session_menu"))
    return builder.as_markup()

def get_skip_comment_keyboard(language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=lex.get('session_skip_comment_button', '⏩ Пропустить'), callback_data="session_skip_comment"))
    return builder.as_markup()
