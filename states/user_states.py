from .finance import *
from .userbot import *
from .profile import *
from .tools import *
from .admin_common import *
from .admin_users import *
from .admin_containers import *
from .admin_system import *
from aiogram.fsm.state import State, StatesGroup

class BroadcastState(StatesGroup):
    waiting_for_text = State()
    waiting_for_media = State()
    waiting_for_media_q = State()
    waiting_for_button_q = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    confirming_broadcast = State()
