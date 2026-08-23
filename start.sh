#!/bin/sh

# Start the scheduler process in the background
python dyndns_nfsn.py --no-web &

# Start Gunicorn as PID 1 so it receives container signals
exec gunicorn -w 4 -b 0.0.0.0:80 wsgi:app
