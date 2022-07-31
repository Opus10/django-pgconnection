import dj_database_url
import pgconnection


SECRET_KEY = 'django-pgconnection'
# Install the tests as an app so that we can make test models
INSTALLED_APPS = [
    'pgconnection',
    'pgconnection.tests',
    # For testing purposes
    'django.contrib.auth',
    'django.contrib.contenttypes',
]
# Database url comes from the DATABASE_URL env var
DATABASES = pgconnection.configure({'default': dj_database_url.config()})

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
