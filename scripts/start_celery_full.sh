#!/bin/bash

echo '========== CHANGE TO API DIR'
cd pcts_crawlers_api

echo '========== START CELERY WORKER + SCHEDULER + WEBVIEW FLOWER'
celery worker --app=pcts_crawlers_api --loglevel=INFO --beat
# celery worker --app=pcts_crawlers_api --loglevel=INFO --beat & celery flower --app=pcts_crawlers_api --loglevel=ERROR --persistent=True
