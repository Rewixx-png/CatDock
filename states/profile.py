from aiogram.fsm.state import State, StatesGroup

class ProfileSettingsState(StatesGroup):
    viewing = State()

class SupportState(StatesGroup):
    waiting_for_question = State()

class CosmeticState(StatesGroup):
    choosing_container_for_icon = State()
