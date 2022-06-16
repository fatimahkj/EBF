#!/bin/sh

./cseq.py -D -l fpmatherr -i example-7x12-3x4.c  --unwind 2 --error-f 64 --error-i 31 --error-bound 58 --backend cbmc-ext --no-overflow --no-error-overflow --split-var cnondet__3_4__ --split-offset 0,2,4,6,8,10,12,14,16,18 --cores 1024 --from   0 --to 15

./cseq.py -D -l fpmatherr -i example-7x12-3x4.c  --unwind 2 --error-f 64 --error-i 31 --error-bound 58 --backend cbmc-ext --no-overflow --no-error-overflow --split-var cnondet__3_4__ --split-offset 0,2,4,6,8,10,12,14,16,18 --cores 1024 --from  16 --to 31

./cseq.py -D -l fpmatherr -i example-7x12-3x4.c  --unwind 2 --error-f 64 --error-i 31 --error-bound 58 --backend cbmc-ext --no-overflow --no-error-overflow --split-var cnondet__3_4__ --split-offset 0,2,4,6,8,10,12,14,16,18 --cores 1024 --from  32 --to 47

./cseq.py -D -l fpmatherr -i example-7x12-3x4.c  --unwind 2 --error-f 64 --error-i 31 --error-bound 58 --backend cbmc-ext --no-overflow --no-error-overflow --split-var cnondet__3_4__ --split-offset 0,2,4,6,8,10,12,14,16,18 --cores 1024 --from  48 --to 63

./cseq.py -D -l fpmatherr -i example-7x12-3x4.c  --unwind 2 --error-f 64 --error-i 31 --error-bound 58 --backend cbmc-ext --no-overflow --no-error-overflow --split-var cnondet__3_4__ --split-offset 0,2,4,6,8,10,12,14,16,18 --cores 1024 --from  64 --to 79

./cseq.py -D -l fpmatherr -i example-7x12-3x4.c  --unwind 2 --error-f 64 --error-i 31 --error-bound 58 --backend cbmc-ext --no-overflow --no-error-overflow --split-var cnondet__3_4__ --split-offset 0,2,4,6,8,10,12,14,16,18 --cores 1024 --from  80 --to 95

./cseq.py -D -l fpmatherr -i example-7x12-3x4.c  --unwind 2 --error-f 64 --error-i 31 --error-bound 58 --backend cbmc-ext --no-overflow --no-error-overflow --split-var cnondet__3_4__ --split-offset 0,2,4,6,8,10,12,14,16,18 --cores 1024 --from  96 --to 111

./cseq.py -D -l fpmatherr -i example-7x12-3x4.c  --unwind 2 --error-f 64 --error-i 31 --error-bound 58 --backend cbmc-ext --no-overflow --no-error-overflow --split-var cnondet__3_4__ --split-offset 0,2,4,6,8,10,12,14,16,18 --cores 1024 --from 112 --to 127


