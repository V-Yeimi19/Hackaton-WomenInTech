"""Billeteras con nombre, datos de constancia en operaciones y login por teléfono.

- `wallets`: billeteras visibles; cada una apunta a su cuenta del libro.
  Principal -> HOUSEHOLD_DIGITAL, negocio -> BUSINESS_DIGITAL y el resto -> WALLET.
- `accounts`: nuevo kind WALLET (varias por negocio); las cuentas fijas siguen
  siendo únicas por negocio mediante un índice parcial.
- `transactions`: número de operación, contraparte, mensaje, categoría y código
  de seguridad para constancias; nuevos tipos de operación personales.
- `user_phones`: teléfono cifrado + hash de búsqueda para "mismo número, misma cuenta".

La migración es idempotente: 0001 crea las tablas desde los modelos actuales,
así que en una base nueva parte de este esquema ya existe; en una base que
venía de 0004 se aplica completo.

Revision ID: 0005_wallets_phone_login
Revises: 0004_transaction_immutability
"""

from alembic import op

revision = "0005_wallets_phone_login"
down_revision = "0004_transaction_immutability"
branch_labels = None
depends_on = None

OLD_KINDS = (
    "'SALE', 'BUSINESS_PAYMENT', 'HOUSEHOLD_WITHDRAWAL', 'OWNER_CONTRIBUTION', "
    "'UNKNOWN_OUTFLOW', 'OPENING_BALANCE', 'CLASSIFICATION_ADJUSTMENT', 'REVERSAL'"
)
NEW_KINDS = OLD_KINDS + ", 'PERSONAL_PAYMENT', 'PERSONAL_INCOME', 'WALLET_TRANSFER'"


def upgrade():
    # Cuentas: varias billeteras WALLET por negocio.
    op.execute(f"""
        ALTER TABLE accounts DROP CONSTRAINT IF EXISTS ck_accounts_kind;
        ALTER TABLE accounts ADD CONSTRAINT ck_accounts_kind CHECK (kind IN (
            'BUSINESS_DIGITAL', 'HOUSEHOLD_DIGITAL', 'CASH_DECLARED', 'EXTERNAL_CLEARING', 'WALLET'));
        ALTER TABLE accounts DROP CONSTRAINT IF EXISTS uq_accounts_business_kind;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_accounts_business_kind_fixed
            ON accounts (business_id, kind) WHERE kind <> 'WALLET';

        CREATE TABLE IF NOT EXISTS wallets (
            id uuid PRIMARY KEY,
            business_id uuid NOT NULL REFERENCES businesses(id),
            account_id uuid NOT NULL UNIQUE,
            name varchar(40) NOT NULL,
            role varchar(16) NOT NULL,
            purpose varchar(16) NOT NULL,
            icon varchar(24),
            color varchar(16),
            status varchar(12) NOT NULL DEFAULT 'ACTIVE',
            position integer NOT NULL DEFAULT 0,
            created_at timestamptz NOT NULL,
            archived_at timestamptz,
            CONSTRAINT ck_wallets_role CHECK (role IN ('PRINCIPAL', 'BUSINESS', 'SAVINGS', 'CUSTOM')),
            CONSTRAINT ck_wallets_purpose CHECK (purpose IN ('PERSONAL', 'BUSINESS', 'SAVINGS')),
            CONSTRAINT ck_wallets_status CHECK (status IN ('ACTIVE', 'ARCHIVED'))
        );
        CREATE INDEX IF NOT EXISTS ix_wallets_business ON wallets (business_id);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_wallets_business_name_active
            ON wallets (business_id, lower(name)) WHERE status = 'ACTIVE';
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_wallets_account_business') THEN
                ALTER TABLE wallets ADD CONSTRAINT fk_wallets_account_business
                    FOREIGN KEY (business_id, account_id) REFERENCES accounts (business_id, id);
            END IF;
        END $$;

        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS operation_number bigint;
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS counterparty_name varchar(120);
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS counterparty_phone_masked varchar(20);
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS note varchar(40);
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS category varchar(24);
        ALTER TABLE transactions ADD COLUMN IF NOT EXISTS security_code varchar(3);
        ALTER TABLE transactions DROP CONSTRAINT IF EXISTS ck_transactions_category;
        ALTER TABLE transactions ADD CONSTRAINT ck_transactions_category CHECK (
            category IS NULL OR category IN ('RESTOCK', 'LOCAL_SERVICES', 'FAMILY'));
        CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_operation_number
            ON transactions (environment, operation_number) WHERE operation_number IS NOT NULL;
        ALTER TABLE transactions DROP CONSTRAINT IF EXISTS ck_transactions_kind;
        ALTER TABLE transactions ADD CONSTRAINT ck_transactions_kind CHECK (kind IN ({NEW_KINDS}));

        CREATE TABLE IF NOT EXISTS user_phones (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL UNIQUE REFERENCES users(id),
            environment varchar(10) NOT NULL DEFAULT 'DEMO',
            phone_encrypted varchar(512) NOT NULL,
            phone_lookup_hash varchar(64) NOT NULL,
            created_at timestamptz NOT NULL,
            CONSTRAINT uq_user_phones_lookup_env UNIQUE (phone_lookup_hash, environment),
            CONSTRAINT ck_user_phones_environment CHECK (environment IN ('DEMO', 'LIVE'))
        );
    """)


def downgrade():
    op.execute(f"""
        DROP TABLE IF EXISTS user_phones;
        ALTER TABLE transactions DROP CONSTRAINT IF EXISTS ck_transactions_kind;
        ALTER TABLE transactions ADD CONSTRAINT ck_transactions_kind CHECK (kind IN ({OLD_KINDS}));
        DROP INDEX IF EXISTS uq_transactions_operation_number;
        ALTER TABLE transactions DROP CONSTRAINT IF EXISTS ck_transactions_category;
        ALTER TABLE transactions DROP COLUMN IF EXISTS security_code;
        ALTER TABLE transactions DROP COLUMN IF EXISTS category;
        ALTER TABLE transactions DROP COLUMN IF EXISTS note;
        ALTER TABLE transactions DROP COLUMN IF EXISTS counterparty_phone_masked;
        ALTER TABLE transactions DROP COLUMN IF EXISTS counterparty_name;
        ALTER TABLE transactions DROP COLUMN IF EXISTS operation_number;
        DROP TABLE IF EXISTS wallets;
        DROP INDEX IF EXISTS uq_accounts_business_kind_fixed;
        ALTER TABLE accounts ADD CONSTRAINT uq_accounts_business_kind UNIQUE (business_id, kind);
        ALTER TABLE accounts DROP CONSTRAINT IF EXISTS ck_accounts_kind;
        ALTER TABLE accounts ADD CONSTRAINT ck_accounts_kind CHECK (kind IN (
            'BUSINESS_DIGITAL', 'HOUSEHOLD_DIGITAL', 'CASH_DECLARED', 'EXTERNAL_CLEARING'));
    """)
