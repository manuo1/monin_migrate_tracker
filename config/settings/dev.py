from .base import *

DEBUG = env.bool("DEBUG", default=True)

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
