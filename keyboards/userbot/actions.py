from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from lexicon import LEXICON
from config import SERVERS, IMAGES, SUBSCRIPTION_PLANS, CPU_UPGRADE_PRICE, RAM_UPGRADE_PRICE
from utils import bot_state

def get_change_image_keyboard(language_code: str, current_image_id: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for image_id, image_info in IMAGES.items():
        if image_id != current_image_id:
            
            builder.row(types.InlineKeyboardButton(
                text=f"{lex.get('install_button', 'Установить')} {image_info['name']}", 
                callback_data=f"change_image_select:{image_id}"
            ))
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="cancel_change"))
    return builder.as_markup()

def get_change_server_keyboard(language_code: str, current_server_id: str, tariff_id: str, admin_mode: bool = False) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    callback_prefix = "admin_select_new_server" if admin_mode else "change_server_select"

    for server_id, server_info in SERVERS.items():
        if not bot_state.server_states.get(server_id, True) and not admin_mode:
            continue

        if server_id != current_server_id:
            
            text = f"{server_info['name']}"
            if admin_mode and not bot_state.server_states.get(server_id, True):
                text += " 🔴"
            builder.row(types.InlineKeyboardButton(text=text, callback_data=f"{callback_prefix}:{server_id}"))

    cancel_callback = "cancel_admin_action" if admin_mode else "cancel_change"
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data=cancel_callback))
    return builder.as_markup()

def get_extend_options_keyboard(container_id: int, tariff_price: float, cpu_monthly_cost: float, ram_monthly_cost: float, language_code: str) -> InlineKeyboardMarkup:
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()

    total_monthly_price = tariff_price + cpu_monthly_cost + ram_monthly_cost

    for plan in SUBSCRIPTION_PLANS:
        months = plan['months']
        discount = plan['discount_percent']
        base_price = total_monthly_price * months
        final_price = base_price * (1 - discount / 100)
        
        text = lex.get('extend_plan_button', "{months} мес. за {price:.0f}₽ {discount}").format(
            months=months, price=final_price, discount=f"(-{discount}%)" if discount > 0 else ""
        )
        
        builder.row(types.InlineKeyboardButton(text=f"📅 {text}", callback_data=f"extend_confirm:{container_id}:{months}"))

    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="cancel_change"))
    return builder.as_markup()

def get_cpu_upgrade_keyboard(container_id, current_limit_cores, language_code):
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for percent in [10, 20, 50, 100]:
         cost = (percent / 10.0) * CPU_UPGRADE_PRICE
         builder.add(types.InlineKeyboardButton(text=f"⚡ +{percent}% ({cost:.0f}₽)", callback_data=f"upgrade_cpu_for:{container_id}:{percent}"))
    builder.adjust(2)
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="cancel_change"))
    return builder.as_markup()

def get_ram_upgrade_keyboard(container_id, current_ram, language_code):
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    for mb in [100, 300, 500, 1000]:
         cost = (mb / 100.0) * RAM_UPGRADE_PRICE
         builder.add(types.InlineKeyboardButton(text=f"🧠 +{mb}MB ({cost:.0f}₽)", callback_data=f"upgrade_ram_for:{container_id}:{mb}"))
    builder.adjust(2)
    builder.row(types.InlineKeyboardButton(text=lex.get('back_button', 'back_button'), callback_data="cancel_change"))
    return builder.as_markup()

def get_transfer_confirmation_keyboard(language_code, container_id):
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=lex.get('transfer_confirm_button', 'transfer_confirm_button'), callback_data=f"confirm_transfer:{container_id}"))
    builder.row(types.InlineKeyboardButton(text=lex.get('cancel_button', 'cancel_button'), callback_data="cancel_change"))
    return builder.as_markup()

def get_delete_confirm_step1_keyboard(language_code, container_id):
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=lex.get('delete_agree_button', 'Да'), callback_data=f"delete_confirm_step2:{container_id}"))
    builder.row(types.InlineKeyboardButton(text=lex.get('cancel_button', 'cancel_button'), callback_data="cancel_change"))
    return builder.as_markup()

def get_delete_confirm_step2_keyboard(language_code, container_id):
    lex = LEXICON.get(language_code, LEXICON['ru'])
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=lex.get('delete_final_confirm_button', 'УДАЛИТЬ'), callback_data=f"delete_bot_final:{container_id}"))
    builder.row(types.InlineKeyboardButton(text=lex.get('cancel_button', 'cancel_button'), callback_data="cancel_change"))
    return builder.as_markup()
