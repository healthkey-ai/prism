"""
`migrate`, able to run for the first time on a database PRomop already owns.

PRism and PRomop share one database. PRomop's own `migrate` records
`admin.0001_initial`, and in PRism that migration depends on the first
migration of the app holding AUTH_USER_MODEL — `accounts.0001`, which PRomop
has never heard of. Django's migrate checks the recorded history before doing
anything, sees an applied migration whose dependency is not, and stops with
InconsistentMigrationHistory. `--fake` and app/target arguments go through the
same check, so there is no flag that gets past it.

`accounts.0001` is safe to apply there for real: it is `CREATE ... IF NOT
EXISTS` over PRomop's tables plus state-only operations. So before handing
over to Django's migrate, apply that one migration through the executor, which
does not run the history check. Only in exactly that state: anything else that
is inconsistent still fails the way Django reports it.
"""
from django.core.management.commands.migrate import Command as DjangoMigrateCommand
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.state import ProjectState

ACCOUNTS_INITIAL = ("accounts", "0001_create_identity_table")


def needs_shared_db_bootstrap(loader):
    """True when an applied migration depends on an unapplied `accounts.0001`."""
    applied = loader.applied_migrations
    if ACCOUNTS_INITIAL in applied:
        return False
    return any(
        ACCOUNTS_INITIAL in loader.graph.node_map[key].parents
        for key in applied
        if key in loader.graph.node_map
    )


def bootstrap_shared_db(connection, stdout=None):
    """Apply `accounts.0001` on a PRomop-owned database. Returns whether it ran."""
    executor = MigrationExecutor(connection)
    if not needs_shared_db_bootstrap(executor.loader):
        return False
    if stdout is not None:
        stdout.write(
            "Database already has migrations recorded by PRomop; "
            f"applying {ACCOUNTS_INITIAL[0]}.{ACCOUNTS_INITIAL[1]} first."
        )
    executor.migrate([ACCOUNTS_INITIAL], state=_state_before(executor, ACCOUNTS_INITIAL))
    return True


def _state_before(executor, target):
    """Project state from the target's applied ancestors only.

    The executor's default starting state replays every recorded migration,
    and `admin.0001` declares LogEntry.user against `accounts.Identity`, which
    is what this run is about to create, so that state cannot be rendered.
    """
    loader = executor.loader
    ancestors = set(loader.graph.forwards_plan(target)) - {target}
    state = ProjectState(real_apps=loader.unmigrated_apps)
    for key in loader.graph.forwards_plan(target):
        if key in ancestors and key in loader.applied_migrations:
            loader.graph.nodes[key].mutate_state(state, preserve=False)
    return state


class Command(DjangoMigrateCommand):
    def handle(self, *args, **options):
        # --plan and --check promise not to touch the database.
        if not (options.get("plan") or options.get("check_unapplied")):
            connection = connections[options.get("database") or DEFAULT_DB_ALIAS]
            bootstrap_shared_db(connection, self.stdout)
        return super().handle(*args, **options)
