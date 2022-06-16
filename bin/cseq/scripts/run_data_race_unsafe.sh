LOG_NAME=data-race-$(date +%y-%m-%d_%H%M).log
nohup python3 sv-comp--test-parallel.py --races --unsafe-only -p concurrency > $LOG_NAME &
echo "Writing to" $LOG_NAME
