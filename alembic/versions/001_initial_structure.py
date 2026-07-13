from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT NOT NULL,
            balance DOUBLE PRECISION DEFAULT 0.0,
            reg_date TIMESTAMP DEFAULT NOW(),
            referrer_id BIGINT,
            ref_balance DOUBLE PRECISION DEFAULT 0.0,
            role TEXT DEFAULT 'PARTICIPANT',
            language_code TEXT DEFAULT 'ru',
            has_used_free_tariff BOOLEAN DEFAULT FALSE,
            is_blocked BOOLEAN DEFAULT FALSE,
            last_verified_ip TEXT,
            active_discount_percent INTEGER DEFAULT 0,
            active_discount_code TEXT,
            active_deposit_bonus_percent INTEGER DEFAULT 0,
            active_deposit_bonus_code TEXT,
            has_free_container_promo BOOLEAN DEFAULT FALSE,
            free_container_promo_code TEXT,
            has_free_server_change BOOLEAN DEFAULT FALSE,
            free_server_change_code TEXT,
            last_bonus_claim_ts BIGINT DEFAULT 0,
            cashback_percent INTEGER DEFAULT 5,
            has_advanced_referral BOOLEAN DEFAULT FALSE,
            custom_avatar_url TEXT,
            warn_count INTEGER DEFAULT 0 NOT NULL,
            log_topic_id BIGINT,
            roulette_spins_total INTEGER DEFAULT 0 NOT NULL,
            last_weekly_roulette_ts BIGINT DEFAULT 0 NOT NULL,
            free_spins INTEGER DEFAULT 0 NOT NULL,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            game_checks INTEGER DEFAULT 0 NOT NULL,
            device_info JSONB DEFAULT '{}'::jsonb,
            last_ip TEXT,
            country_code TEXT
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS servers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            ip TEXT NOT NULL,
            proxy_ip TEXT,
            ssh_user TEXT NOT NULL,
            password TEXT,
            key_path TEXT,
            key_pass TEXT,
            check_port INTEGER DEFAULT 22,
            is_active BOOLEAN DEFAULT TRUE,
            is_local BOOLEAN DEFAULT FALSE,
            domain_script_path TEXT,
            limits JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS user_containers (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            server_id TEXT NOT NULL,
            container_name TEXT NOT NULL,
            image_id TEXT NOT NULL,
            tariff_id TEXT NOT NULL,
            external_port INTEGER NOT NULL,
            creation_date TIMESTAMP DEFAULT NOW(),
            remaining_seconds BIGINT DEFAULT 2592000,
            is_frozen BOOLEAN DEFAULT FALSE,
            is_login_pending BOOLEAN DEFAULT FALSE,
            is_blocked BOOLEAN DEFAULT FALSE,
            is_web_loading BOOLEAN DEFAULT FALSE,
            login_url TEXT,
            cpu_limit DOUBLE PRECISION,
            ram_mb INTEGER,
            last_notification_days INTEGER DEFAULT 0,
            cosmetic_icon TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_user_containers_user_id ON user_containers (user_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS promo_codes (
            id SERIAL PRIMARY KEY,
            code_text TEXT UNIQUE NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            creator_id BIGINT NOT NULL,
            creation_date TIMESTAMP DEFAULT NOW(),
            activator_id BIGINT,
            activation_date TIMESTAMP,
            FOREIGN KEY (creator_id) REFERENCES users (user_id),
            FOREIGN KEY (activator_id) REFERENCES users (user_id)
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS global_promo_codes (
            id SERIAL PRIMARY KEY,
            code TEXT UNIQUE NOT NULL,
            promo_type TEXT NOT NULL,
            value DOUBLE PRECISION NOT NULL,
            message_id BIGINT NOT NULL,
            creation_date TIMESTAMP DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE,
            activator_id BIGINT,
            activation_date TIMESTAMP,
            FOREIGN KEY (activator_id) REFERENCES users (user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_global_promo_codes_code ON global_promo_codes (code);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS verification_tokens (
            token TEXT PRIMARY KEY,
            user_id BIGINT NOT NULL,
            creation_date TIMESTAMP DEFAULT NOW(),
            is_used BOOLEAN DEFAULT FALSE,
            server_id TEXT,
            image_id TEXT,
            tariff_id TEXT,
            username TEXT,
            message_id BIGINT,
            chat_id BIGINT,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS web_access_tokens (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            creation_date TIMESTAMP DEFAULT NOW(),
            last_used_date TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_web_tokens_token ON web_access_tokens (token);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            username TEXT,
            subject TEXT DEFAULT 'Без темы',
            question_text TEXT NOT NULL,
            answer_text TEXT,
            status TEXT DEFAULT 'open',
            assigned_admin_id BIGINT,
            rating INTEGER,
            creation_date TIMESTAMP DEFAULT NOW(),
            close_date TIMESTAMP,
            last_message_time TIMESTAMP,
            last_message_text TEXT,
            user_has_unread BOOLEAN DEFAULT TRUE,
            admin_has_unread BOOLEAN DEFAULT TRUE,
            hidden_by_user BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (assigned_admin_id) REFERENCES users (user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_support_tickets_user_id_status ON support_tickets (user_id, status);
        CREATE INDEX IF NOT EXISTS idx_support_tickets_user_hidden ON support_tickets (user_id, hidden_by_user);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id SERIAL PRIMARY KEY,
            ticket_id INTEGER NOT NULL,
            sender_id BIGINT NOT NULL,
            sender_name TEXT NOT NULL,
            message_text TEXT NOT NULL,
            is_admin_message BOOLEAN DEFAULT FALSE,
            timestamp TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (ticket_id) REFERENCES support_tickets (id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_support_messages_ticket_id ON support_messages (ticket_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id BIGINT PRIMARY KEY,
            show_id BOOLEAN DEFAULT TRUE,
            show_name BOOLEAN DEFAULT TRUE,
            show_username BOOLEAN DEFAULT TRUE,
            show_role BOOLEAN DEFAULT TRUE,
            show_userbots BOOLEAN DEFAULT TRUE,
            show_main_balance BOOLEAN DEFAULT TRUE,
            show_ref_balance BOOLEAN DEFAULT TRUE,
            show_rewcoin BOOLEAN DEFAULT TRUE,
            use_custom_photo BOOLEAN DEFAULT FALSE,
            use_old_banners BOOLEAN DEFAULT FALSE, 
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            text TEXT NOT NULL,
            link TEXT,
            is_read BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications (user_id, is_read);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS auth_tokens (
            token TEXT PRIMARY KEY,
            status TEXT DEFAULT 'pending' NOT NULL,
            api_key TEXT,
            user_id BIGINT,
            created_ts BIGINT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_auth_tokens_created_ts ON auth_tokens (created_ts);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS game_history (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            game_type TEXT NOT NULL,
            bet_amount DOUBLE PRECISION NOT NULL,
            result TEXT NOT NULL,
            prize_type TEXT,
            prize_value TEXT,
            timestamp TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_game_history_user_id ON game_history (user_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS active_games (
            user_id BIGINT PRIMARY KEY,
            game_type TEXT NOT NULL,
            bet_amount DOUBLE PRECISION NOT NULL,
            state JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS login_codes (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            code TEXT NOT NULL UNIQUE,
            created_ts BIGINT NOT NULL,
            is_used INTEGER DEFAULT 0 NOT NULL,
            is_qr BOOLEAN DEFAULT FALSE NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_login_codes_code ON login_codes (code);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS star_payments (
            id SERIAL PRIMARY KEY,
            telegram_payment_charge_id TEXT UNIQUE NOT NULL,
            user_id BIGINT NOT NULL,
            star_amount INTEGER NOT NULL,
            rub_amount DOUBLE PRECISION NOT NULL,
            creation_date TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_star_payments_user_id ON star_payments (user_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS crypto_payments (
            id SERIAL PRIMARY KEY,
            invoice_id BIGINT UNIQUE NOT NULL,
            user_id BIGINT NOT NULL,
            fiat_amount DOUBLE PRECISION NOT NULL,
            fiat_currency TEXT NOT NULL,
            paid_asset TEXT,
            paid_amount DOUBLE PRECISION,
            creation_date TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_crypto_payments_user_id ON crypto_payments (user_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS container_transfer_tokens (
            token TEXT PRIMARY KEY,
            container_id INTEGER NOT NULL UNIQUE,
            creator_user_id BIGINT NOT NULL,
            created_ts BIGINT NOT NULL,
            FOREIGN KEY (container_id) REFERENCES user_containers (id) ON DELETE CASCADE,
            FOREIGN KEY (creator_user_id) REFERENCES users (user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_transfer_tokens_container_id ON container_transfer_tokens (container_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            comment TEXT,
            session_string TEXT NOT NULL,
            creation_date TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions (user_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS log_access_tokens (
            token TEXT PRIMARY KEY,
            container_id INTEGER NOT NULL,
            created_ts BIGINT NOT NULL,
            FOREIGN KEY (container_id) REFERENCES user_containers (id) ON DELETE CASCADE
        );
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS system_logs (
            id SERIAL PRIMARY KEY,
            actor_id BIGINT NOT NULL,
            target_id BIGINT,
            action_type TEXT NOT NULL,
            message TEXT NOT NULL,
            is_admin_action BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_system_logs_actor ON system_logs (actor_id);
        CREATE INDEX IF NOT EXISTS idx_system_logs_target ON system_logs (target_id);
        CREATE INDEX IF NOT EXISTS idx_system_logs_type ON system_logs (action_type);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS crash_history (
            id SERIAL PRIMARY KEY,
            crash_point DOUBLE PRECISION NOT NULL,
            secret TEXT NOT NULL,
            hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

def downgrade() -> None:
    pass
