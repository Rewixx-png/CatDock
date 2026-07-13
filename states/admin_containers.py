from aiogram.fsm.state import State, StatesGroup

class AdminContainersState(StatesGroup):
    viewing_list = State()
    waiting_for_id = State()
    waiting_for_name = State()

class AdminGiveContainerState(StatesGroup):
    choosing_server = State()
    choosing_tariff = State()
    choosing_image = State()
    waiting_for_reason = State()
    confirming_give = State()

class AdminManageContainerState(StatesGroup):
    changing_time = State()

class AdminUpgradeCpuState(StatesGroup):
    waiting_for_container_id = State()
    choosing_option = State()
    confirming_upgrade = State()

class AdminChatGiveContainerState(StatesGroup):
    choosing_tariff = State()
    waiting_for_days = State()
    choosing_server = State()
    choosing_image = State()
    waiting_for_reason = State()

class AdminGiveAdminContainerState(StatesGroup):
    waiting_for_user_id = State()
    choosing_server = State()
    choosing_image = State()
    confirming_give = State()

class AdminChangeServerState(StatesGroup):
    choosing_server = State()
    confirming_change = State()
