from io import StringIO
import pandas as pd
import typer 
from pathlib import Path

def process(filename: Path):
    logfile = open(filename, 'r')
    lines = logfile.readlines()

    filtered_lines = [line.split('>')[-1] for line in lines if 'FAIL' in line and not 'FAILED' in line]

    s = StringIO('\n'.join(filtered_lines))
    df = pd.read_csv(s, names=['stop', 'number', 'status', 'time', 'memory', 'verdict', 'filename', 'time2', 'memory2', 'witness'])

    df.to_csv(filename.with_suffix('.csv'), columns=['number', 'filename', 'verdict', 'time', 'memory'], index=None)

def main(filename : Path) -> None:
    process(filename)

if __name__ == '__main__':
    typer.run(main)