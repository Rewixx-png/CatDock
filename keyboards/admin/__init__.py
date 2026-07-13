from .common import get_cancel_admin_action_keyboard, get_yes_no_keyboard
from .main import get_admin_main_menu
from .users import (
    get_user_management_keyboard,
    get_delete_user_confirmation_keyboard,
    get_role_selection_keyboard,
    get_user_list_keyboard,
    get_rinfo_main_keyboard,
    get_rinfo_userbots_keyboard
)
from .containers import (
    get_container_list_keyboard,
    get_user_containers_list_keyboard, 
    get_orphaned_containers_keyboard,
    get_checkcont_keyboard,
    get_fixloop_list_keyboard,
    get_admin_container_list_keyboard,
    get_admin_containers_menu_keyboard
)
from .servers import (
    get_server_management_keyboard,
    get_server_for_update_keyboard,
    get_terminal_exit_keyboard,
    get_server_edit_list_keyboard,
    get_server_edit_details_keyboard,
    get_server_delete_keyboard,
    get_server_delete_confirm_keyboard
)
from .give import (
    get_give_confirmation_keyboard,
    get_chat_give_tariff_keyboard,
    get_chat_give_server_keyboard,
    get_chat_give_image_keyboard,
    get_give_admin_server_keyboard,
    get_give_admin_image_keyboard,
    get_give_admin_confirmation_keyboard
)
from .settings import (
    get_bot_settings_keyboard,
    get_broadcast_confirmation_keyboard
)

get_admin_promo_menu_keyboard = None  # removed
from .support import (
    get_admin_ticket_keyboard,
    get_admin_answer_confirm_keyboard
)
from .htop import get_htop_server_keyboard, get_htop_refresh_keyboard
from .drestart import get_drestart_server_keyboard
from .dstats import get_dstats_server_keyboard, get_dstats_refresh_keyboard
