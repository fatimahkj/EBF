LOG_NAME=reach-$(date +%y-%m-%d_%H%M).log
nohup python3 sv-comp--test-parallel.py --reach --unsafe-only -p concurrency > $LOG_NAME &
echo "Writing to" $LOG_NAME
