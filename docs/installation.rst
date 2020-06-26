.. _installation:

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
