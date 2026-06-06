"""
Creates the `identity` table if it doesn't already exist.

In production, this table is owned by ctomop which runs first. This migration
is a no-op in that case (CREATE TABLE IF NOT EXISTS). In standalone/dev
environments where ctomop hasn't run yet, it creates the table so analytics
can work independently.
"""
from django.db import migrations


CREATE_IDENTITY = """
CREATE TABLE IF NOT EXISTS identity (
    id          bigserial PRIMARY KEY,
    password    varchar(128)  NOT NULL,
    last_login  timestamptz,
    is_superuser boolean NOT NULL DEFAULT false,
    issuer      varchar(255)  NOT NULL,
    sub         varchar(255)  NOT NULL,
    uid         varchar(512)  NOT NULL,
    email       varchar(254)  NOT NULL,
    name        varchar(255)  NOT NULL DEFAULT '',
    is_active   boolean       NOT NULL DEFAULT true,
    is_staff    boolean       NOT NULL DEFAULT false,
    created_at  timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT identity_uid_key UNIQUE (uid)
);
"""

CREATE_IDENTITY_GROUPS = """
CREATE TABLE IF NOT EXISTS accounts_identity_groups (
    id          bigserial PRIMARY KEY,
    identity_id bigint NOT NULL REFERENCES identity(id) ON DELETE CASCADE,
    group_id    integer NOT NULL REFERENCES auth_group(id) ON DELETE CASCADE,
    CONSTRAINT accounts_identity_groups_identity_id_group_id_key UNIQUE (identity_id, group_id)
);
"""

CREATE_IDENTITY_USER_PERMISSIONS = """
CREATE TABLE IF NOT EXISTS accounts_identity_user_permissions (
    id              bigserial PRIMARY KEY,
    identity_id     bigint NOT NULL REFERENCES identity(id) ON DELETE CASCADE,
    permission_id   integer NOT NULL REFERENCES auth_permission(id) ON DELETE CASCADE,
    CONSTRAINT accounts_identity_user_permissions_identity_id_permission_id_key
        UNIQUE (identity_id, permission_id)
);
"""


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunSQL(CREATE_IDENTITY, reverse_sql="DROP TABLE IF EXISTS identity CASCADE;"),
        migrations.RunSQL(CREATE_IDENTITY_GROUPS, reverse_sql="DROP TABLE IF EXISTS accounts_identity_groups;"),
        migrations.RunSQL(CREATE_IDENTITY_USER_PERMISSIONS, reverse_sql="DROP TABLE IF EXISTS accounts_identity_user_permissions;"),
    ]
