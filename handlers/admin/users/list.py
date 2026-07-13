import math
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

import database as db
from utils.filters import IsAdmin
from keyboards.admin import get_user_list_keyboard, get_cancel_admin_action_keyboard
from states.user_states import AdminUserState
from lexicon import LEXICON
from roles import UserRole
from ..main_menu import send_admin_panel_menu
from .profile import show_user_profile

router = Router()
router.message.filter(IsAdmin(min_level=UserRole.ADMIN))
router.callback_query.filter(IsAdmin(min_level=UserRole.ADMIN))

async def get_users_page(page: int, message: types.Message | types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminUserState.managing_user)
    language_code = await db.get_user_language(message.from_user.id) or 'ru'
    lex = LEXICON[language_code]
    users, total_count = await db.get_all_users_paginated(page, page_size=5)
    total_pages = math.ceil(total_count / 5)

    text = lex.get('user_list_title', "👤 <b>Список пользователей</b> (Стр. {page}/{total_pages})\n\nВыберите пользователя или воспользуйтесь поиском.").format(page=page + 1, total_pages=total_pages)

    await send_admin_panel_menu(
        message, text, get_user_list_keyboard(users, page, total_pages, language_code)
    )

@router.callback_query(F.data == "manage_users")
async def manage_users_menu(callback: types.CallbackQuery, state: FSMContext):
    await get_users_page(0, callback, state)

@router.callback_query(F.data.startswith("users_page:"))
async def users_page_handler(callback: types.CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":")[1])
    await get_users_page(page, callback, state)
    await callback.answer()

@router.callback_query(F.data == "admin_search_user", IsAdmin(min_level=UserRole.SENIOR_ADMIN))
async def search_user_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminUserState.waiting_for_input)
    await send_admin_panel_menu(
        callback, "👤 <b>Поиск пользователя</b>\n\nОтправьте ID или @username для поиска.",
        get_cancel_admin_action_keyboard("manage_users", "ru")
    )

@router.message(AdminUserState.waiting_for_input, IsAdmin(min_level=UserRole.SENIOR_ADMIN))
async def process_user_search(message: types.Message, state: FSMContext):
    user_data = await db.find_user(message.text)
    if not user_data:
        await message.answer("❌ Пользователь не найден. Попробуйте снова.")
        return
    await show_user_profile(message, state, user_data['user_id'])
