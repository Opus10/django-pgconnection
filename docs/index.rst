django-pgconnection
===================

``django-pgconnection`` provides primitives for overriding Postgres
connection and cursor objects, making it possible to do the following:

1. Hook into SQL generation. For example, it is not possible to log
   every time a SQL statement is executed in Django or annotate SQL
   with comments so that additional metadata is logged when executing
   queries. The `pgconnection.pre_execute_hook` context manager allows
   one to hook into SQL before it is executed.
2. Route database traffic to a different database. Although Django provides
   the ability to construct custom database routers, routing to a different
   database has to be instrumented throughout code and can be tedious
   and error prone. The `pgconnection.route` context manager can route
   any database operations to a different database, even if it's an external
   management command that has not been instrumented to use a different
   database.

We'll go over some examples of how to use the functions in
``django-pgconnection``.

Configuring a hook that will log SQL statements
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to use pgconnection functions, be sure to configure
``settings.DATABASES`` like the following:

.. code-block:: python

    import pgconnection


    DATABASES = pgconnection.configure({
        'default': {
            'HOST': '...'
        }
    })


This is an example of a hook function that logs every SQL statement:

.. code-block:: python

    def logging_hook(sql, sql_vars, cursor):
        # Every hook is passed the raw SQL about to be executed,
        # the variables for the SQL string, and the cursor object

        # A hook can either return nothing or return a (sql, sql_vars)
        # tuple to modify the SQL that will be executed
        # Log the unformatted SQL
        logging.INFO(sql)


    with pgconnection.pre_execute_hook(logging_hook):
        # Only log queries inside the context manager
        User.objects.all()

    # To use the hook for all queries, do
    pgconnection.connect_pre_execute_hook(logging_hook)


As shown in the docs of the hook, one has the ability to also return
a tuple of the SQL and the SQL variables in order to dynamically modify
the SQL before execution

Routing a database connection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Do the following to route any Django queries, regardless of their origin,
to a destination database:

.. code-block:: python

    import pgconnection


    # Create a destination database configuration in the same format
    # as databases in settings.DATABASES
    destination = {
        'NAME': 'database_name',
        'HOST': 'database_host'
    }

    with pgconnection.route(destination):
        # Any queries will go to the destination database
        print(User.objects.all())
