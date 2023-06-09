*Note* - This repository is archived. All of the functionality previously offered by django-pgconnection is now available in Django's connection hooks

django-pgconnection
###################

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

The `documentation <https://django-pgconnection.readthedocs.io/>`_ has
examples of how to use ``django-pgconnection``.

Documentation
=============

`View the django-pgconnection docs here
<https://django-pgconnection.readthedocs.io/>`_.

Installation
============

Install django-pgconnection with::

    pip3 install django-pgconnection

After this, add ``pgconnection`` to the ``INSTALLED_APPS``
setting of your Django project.

In order to use connection routing and hooks, one must configure
the ``DATABASES`` setting in ``settings.py`` like so::

    DATABASES = pgconnection.configure({
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': 'mydatabase',
        }
    })

Contributing Guide
==================

For information on setting up django-pgconnection for development and
contributing changes, view `CONTRIBUTING.rst <CONTRIBUTING.rst>`_.

Primary Authors
===============

- @wesleykendall (Wes Kendall)
