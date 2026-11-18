import os
bind='0.0.0.0:'+os.environ.get('PORT','10000')
# A single process keeps sessions and reviewed import previews consistent.
workers=1
worker_class='gthread'
threads=4
timeout=180
graceful_timeout=30
accesslog=None
errorlog='-'
capture_output=True
