"""`migrate` on a database PRomop already owns (issue #64)."""
import pytest
from django.core.management import get_commands
from django.db import connection
from django.db.migrations.exceptions import InconsistentMigrationHistory
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

from accounts.management.commands.migrate import (
    ACCOUNTS_INITIAL,
    bootstrap_shared_db,
    needs_shared_db_bootstrap,
)

pytestmark = pytest.mark.django_db


# PRism's own apps. PRomop's migrate records none of them.
PRISM_APPS = ["accounts", "cohorts", "surveys"]


def _forget_accounts_migrations():
    """Leave django_migrations as PRomop's migrate leaves it: admin, none of PRism's apps.

    Forgetting accounts alone would leave PRism apps recorded whose migrations
    depend on later accounts migrations, a state no real database is in.
    """
    MigrationRecorder(connection).migration_qs.filter(app__in=PRISM_APPS).delete()


def test_migrate_is_the_accounts_override():
    assert get_commands()["migrate"] == "accounts"


def test_fully_migrated_database_needs_no_bootstrap():
    assert not needs_shared_db_bootstrap(MigrationLoader(connection))
    assert bootstrap_shared_db(connection) is False


def test_promop_owned_database_is_detected():
    _forget_accounts_migrations()
    loader = MigrationLoader(connection)

    with pytest.raises(InconsistentMigrationHistory):
        loader.check_consistent_history(connection)
    assert needs_shared_db_bootstrap(loader)


def test_database_where_nothing_depends_on_accounts_needs_no_bootstrap():
    # e.g. a database with only auth/contenttypes/sessions recorded: plain
    # migrate already handles it, so the override stays out of the way.
    MigrationRecorder(connection).migration_qs.exclude(
        app__in=["auth", "contenttypes", "sessions"]
    ).delete()

    assert not needs_shared_db_bootstrap(MigrationLoader(connection))


@pytest.mark.skipif(
    connection.vendor == "sqlite",
    reason="SQLite cannot run schema changes inside the test transaction; CI runs this on Postgres",
)
def test_bootstrap_records_accounts_initial_and_clears_the_inconsistency():
    _forget_accounts_migrations()

    assert bootstrap_shared_db(connection) is True

    loader = MigrationLoader(connection)
    assert ACCOUNTS_INITIAL in loader.applied_migrations
    loader.check_consistent_history(connection)  # no longer raises
    assert not needs_shared_db_bootstrap(loader)


@pytest.mark.parametrize("flag", ["--plan", "--check"])
def test_read_only_migrate_options_do_not_bootstrap(flag):
    from unittest.mock import patch

    from django.core.management import call_command

    with patch("accounts.management.commands.migrate.bootstrap_shared_db") as bootstrap:
        try:
            call_command("migrate", flag, verbosity=0)
        except SystemExit:
            pass  # --check exits non-zero when anything is unapplied
    bootstrap.assert_not_called()


def test_plain_migrate_bootstraps_first():
    from unittest.mock import patch

    from django.core.management import call_command

    with patch("accounts.management.commands.migrate.bootstrap_shared_db") as bootstrap:
        call_command("migrate", verbosity=0)
    bootstrap.assert_called_once()
