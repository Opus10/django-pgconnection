import logging

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
import pytest

import pgconnection


def test_route_source_destination_same():
    """
    Tests pgplus.connection.route when the source and destination database
    are the same
    """
    with pytest.raises(ValueError):
        with pgconnection.route(settings.DATABASES['default']):
            pass


@pytest.mark.django_db
def test_route_guard(mocker):
    """
    Tests pgplus.connection.route and verify the guard does not allow
    access on the routed database
    """
    # Disable the check so that we can route the current database to
    # itself
    mocker.patch(
        'pgconnection.core._check_source_is_not_destination', autospec=True
    )

    # Even when we route the database to itself (and bypass the default check),
    # a pgplus cursor will protect the source database from being queried
    with pytest.raises(RuntimeError):
        with pgconnection.route(settings.DATABASES['default']):
            list(User.objects.all())


@pytest.mark.django_db
def test_route(mocker):
    """
    Tests pgplus.connection.route when successfully routing the database.
    NOTE(@wesleykendall) - This test is fairly limited since it simply
    routes the source database to itself, and it is mostly intended as a
    unittest to make sure that connection patching works. This test will
    eventually be updated so that it creates a separate database for routing.
    """
    # Disable the checks and guards so that we can route the source
    # database to itself
    mocker.patch(
        'pgconnection.core._check_source_is_not_destination', autospec=True
    )
    mocker.patch(
        'pgconnection.core._guard_source_database_access',
        autospec=True,
        return_value=None,
    )

    user_count = User.objects.count()
    with pgconnection.route(settings.DATABASES['default']):
        assert User.objects.count() == user_count

    assert User.objects.count() == user_count


@pytest.mark.django_db
def test_pre_executed_logging_hook(caplog):
    """Registers a pre_execute hook that logs SQL and verifies it works"""
    caplog.set_level(logging.INFO)

    def logging_hook(sql, sql_vars, cursor):
        logging.info(sql)

    # These queries should not be logged
    list(User.objects.filter(id=1))

    # These queries should be logged
    with pgconnection.pre_execute_hook(logging_hook):
        list(Group.objects.values_list('id'))
        list(User.objects.values_list('id'))

    # These queries should not be logged
    list(Group.objects.filter(id=1))

    assert caplog.record_tuples == [
        ('root', logging.INFO, 'SELECT "auth_group"."id" FROM "auth_group"'),
        ('root', logging.INFO, 'SELECT "auth_user"."id" FROM "auth_user"'),
    ]


@pytest.mark.django_db
def test_pre_executed_modify_sql():
    """Registers a pre_execute hook that modifies the SQL"""

    def modify_sql_hook(sql, sql_vars, cursor):
        sql = f'--- Hello World\n{sql}'
        return sql, sql_vars

    with CaptureQueriesContext(connection) as queries:
        with pgconnection.pre_execute_hook(modify_sql_hook):
            list(User.objects.filter(id=1))

        assert queries[0]['sql'].startswith('--- Hello World\n')
