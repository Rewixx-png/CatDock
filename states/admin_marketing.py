from aiogram.fsm.state import State, StatesGroup

class BroadcastState(StatesGroup):
    waiting_for_text = State()
    waiting_for_media_q = State()
    waiting_for_media = State()
    waiting_for_button_q = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    confirming_broadcast = State()

class AdminNewsState(StatesGroup):
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_buttons = State()
    confirming = State()
