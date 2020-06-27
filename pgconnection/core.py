import collections.abc
import contextlib
import copy
import logging
import threading

from django.conf import settings
from django.db import connections
import psycopg2
import psycopg2.extensions

import pgconnection


# Thread local that maintains the cursor hooks currently registered
# to each database
_hooks = threading.local()

LOGGER = logging.getLogger(__name__)


class _Databases(collections.abc.MutableMapping):
    """
    A dict-like object that must be used by the ``settings.DATABASES``
    Django setting in order to use pgconnection.

    This dictionary is thread safe. All updates to the dictionary only
    appear for each thread, allowing pgconnection to safely and dynamically
    patch out database configuration
    """

    def _initialize_databases(self):
        if not hasattr(self._databases, 'val'):
            self._databases.val = copy.deepcopy(self._initial_databases)

    def __init__(self, databases):
        self._initial_databases = copy.deepcopy(databases)
        self._databases = threading.local()
        self._initialize_databases()

    def __getitem__(self, key):
        self._initialize_databases()
        return self._databases.val[key]

    def __setitem__(self, key, value):
        self._initialize_databases()
        self._databases.val[key] = value

    def __delitem__(self, key):  # pragma: no cover
        self._initialize_databases()
        del self._databases.val[key]

    def __iter__(self):
        self._initialize_databases()
        return iter(self._databases.val)

    def __len__(self):  # pragma: no cover
        return len(self._databases.val)


class _Cursor(psycopg2.extensions.cursor):
    """
    A custom database cursor that provides the ability
    to hook into the SQL execution step.

    Hooks allow users to modify SQL and SQL parameters
    dynamically before execution.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uri = _make_uri_from_dsn(self.connection.dsn)

    def execute(self, sql, args=None):
        """
        Runs pre_execute hooks before the execution of SQL
        """
        hooks = _get_hooks()

        for hook in hooks.pre_execute[self.uri]:
            ret = hook(sql, args, self)
            if ret:
                sql, args = ret

        return super().execute(sql, args)


def _cursor_factory(*args, **kwargs):
    """
    When psycopg2 creates a connection, it can be passed
    a cursor_factory so that a custom cursor object
    is created.

    This function provides a factory so that a cursor is
    created with the proper django database alias attached.
    Doing this allows us to register hooks for particular
    databases.
    """
    return _Cursor(*args, **kwargs)


def configure(databases):
    """
    Given a database configuration dictionary, return a copy that
    is configured to use the pgconnection database cursor.

    Args:
        databases (Dict[dict]): A dictionary of database configurations
            (e.g. settings.DATABASES)

    Returns:
        Dict[dict]: A copy of the dictionary of databases configured to
            use the pgconnection cursor.
    """
    databases = copy.deepcopy(databases)

    for config in databases.values():  # pragma: no cover
        # Safeguard against the user not passing in a database config
        if not isinstance(config, dict):
            raise ValueError(
                'Must pass a database configuration'
                ' (e.g. settings.DATABASES["default"]) to'
                ' pgconnection.configure()'
            )

        if config.get('ENGINE') in (
            'django.db.backends.postgresql',
            'django.db.backends.postgresql_psycopg2',
            'django.contrib.gis.db.backends.postgis',
        ):
            if 'OPTIONS' not in config:
                config['OPTIONS'] = {}

            config['OPTIONS']['cursor_factory'] = _cursor_factory

    return _Databases(databases)


def check():  # pragma: no cover
    """
    Raises RuntimeError if pgconnection is not configured correctly
    """
    # Nest the settings import since cursor configuration has to happen
    # before settings and other things are loaded
    from django.conf import settings
    from django.db import connections

    if not isinstance(settings.DATABASES, _Databases) or not isinstance(
        connections.databases, _Databases
    ):
        raise RuntimeError(
            'Must use pgconnection.databases() when configuring'
            ' settings.DATABASES'
        )

    for alias, config in settings.DATABASES.items():
        if config['ENGINE'] in (
            'django.db.backends.postgresql',
            'django.contrib.gis.db.backends.postgis',
        ):
            cursor_factory = config.get('OPTIONS', {}).get('cursor_factory')
            if cursor_factory != _cursor_factory:
                raise RuntimeError(
                    f'database "{alias}" is not configured to use'
                    ' pgconnection. Generate a proper configuration in your'
                    ' settings with pgconnection.configure'
                )


def _make_uri(*, user, host, port, dbname):
    user = user or '<none>'
    host = host or '<none>'
    port = port or '<none>'
    dbname = dbname or '<none>'
    return (
        f'postgres://{user.strip()}@{host.strip()}'
        f':{str(port).strip()}/{dbname.strip()}'
    )


def _make_uri_from_dsn(dsn):
    """
    Makes a postgres database URI from a DSN string. Used for purposes
    of uniquely identifying databases. This is not used to establish
    connections.
    """
    parsed_dsn = psycopg2.extensions.parse_dsn(dsn)
    return _make_uri(
        user=parsed_dsn.get('user'),
        host=parsed_dsn.get('host'),
        port=parsed_dsn.get('port'),
        dbname=parsed_dsn.get('dbname'),
    )


def _make_uri_from_config(config):
    """
    Make a URI string from a django DB config.
    Used for purposed of uniquely identifying databases. This is not
    used to establish connections.
    """
    return _make_uri(
        user=config.get('USER'),
        host=config.get('HOST'),
        port=config.get('PORT'),
        dbname=config.get('NAME'),
    )


def _get_hooks():
    """
    Get the _hooks thread local variable.

    Ensure that the proper attributes are instantiate for the thread local
    if they have not already been instantiated.

    NOTE (@wesleykendall) - Instantiation of the thread local attributes has
    to happen during runtime in a function like this as opposed to doing
    it globally at the top of the file. This is because threads are spawned
    after the code is loaded.
    """
    global _hooks

    if not hasattr(_hooks, 'pre_execute'):
        _hooks.pre_execute = collections.defaultdict(list)

    return _hooks


def connect_pre_execute_hook(hook_func, using='default'):
    """
    Connects a hook function that will be executed
    before any SQL

    Args:
        hook_func (func): The hook function that takes the SQL,
            its variables, and the cursor as arguments. It must return a
            tuple of the modified SQL and vars or None.
        using (str, default='default'): The alias of the database. Must be
            present in settings.DATABASES
    """
    check()
    hooks = _get_hooks()
    uri = _make_uri_from_config(settings.DATABASES[using])

    if hook_func not in hooks.pre_execute[uri]:  # pragma: no branch
        hooks.pre_execute[uri].append(hook_func)


def disconnect_pre_execute_hook(hook_func, using='default'):
    """
    Disconnects a hook function that will be executed
    before any SQL

    Args:
        hook_func (func): The hook function that takes the SQL,
            its variables, and the cursor as arguments. It must return a
            tuple of the modified SQL and vars.
        using (str, default='default'): The alias of the database. Must be
            present in settings.DATABASES
    """
    check()
    hooks = _get_hooks()
    uri = _make_uri_from_config(settings.DATABASES[using])

    if hook_func not in hooks.pre_execute[uri]:  # pragma: no cover
        raise ValueError(
            f'pre_execute hook function not found for database "{using}"'
        )

    hooks.pre_execute[uri].remove(hook_func)


@contextlib.contextmanager
def pre_execute_hook(hook_func, using='default'):
    """
    A context manager to run code with a connected pre_execute hook.
    See connect_pre_execute_hook for more information about the arguments.
    """
    connect_pre_execute_hook(hook_func, using=using)

    try:
        yield
    finally:
        disconnect_pre_execute_hook(hook_func, using=using)


def _check_source_is_not_destination(source, destination):
    """Verify source and destination database configurations aren't equal"""
    source_uri = _make_uri_from_config(source)
    destination_uri = _make_uri_from_config(destination)
    if source_uri == destination_uri:  # pragma: no cover
        raise ValueError(
            'Source and destination databases cannot be the same when routing'
        )


def _guard_source_database_access(sql, args, cursor):
    """A pgconnection hook that guards source database access while routing"""
    raise RuntimeError(
        'Cannot execute queries on the source database'
        ' during pgconnection routing'
    )


@contextlib.contextmanager
def route(destination, using='default'):
    """
    Route connections to another database.

    If the source database is configured to use pgconnection cursors,
    an additional hook is provisioned to ensure that no queries happen
    on the source database

    Args:
        destination (dict): Database configuration dictionary to be routed.
        using (str, default='default'): The source database to use when
            routing to another database. Defaults to the default database.
    """
    pgconnection.check()
    if (
        not isinstance(destination, dict) or 'ENGINE' not in destination
    ):  # pragma: no cover
        raise ValueError(
            'Destination database must be a configuration dictionary in the'
            ' same format as databases from settings.DATABASES.'
        )

    _check_source_is_not_destination(settings.DATABASES[using], destination)

    with pgconnection.pre_execute_hook(
        _guard_source_database_access, using=using
    ):
        # Store the original source database and connection so that the
        # destination can be put it its place
        source_connection = connections[using]
        source = connections.databases[using]

        # When the connection is deleted, Django will re-establish it
        # from the config in connections.databases. Since
        # connections.databases is a pgconnection.core._Databases object, it
        # is safe for us to patch it
        del connections[using]
        connections.databases[using] = destination

        try:
            yield
        finally:
            # Close out the patched connection and remove it
            connections[using].close()
            del connections[using]

            # Revert the patched connection back to the source
            connections.databases[using] = source
            connections[using] = source_connection
