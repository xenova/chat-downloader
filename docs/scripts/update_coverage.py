import re
import os
import json
from run_cmd import run_cmd

coverage_path = 'docs/_dynamic/coverage.json'

command_output = run_cmd('make coverage-report')
coverage = re.search(
    r'TOTAL\s+\d+\s+\d+\s+([\d\.]+%)', command_output)


if coverage is not None:
    coverage = coverage.group(1)
    coverage_amount = float(coverage.rstrip('%'))

    colour_dict = {
        60: 'red',  # 0 <= x < 60
        70: 'orange',  # 60 <= x < 70
        80: 'yellow',  # 70 <= x < 80
        90: 'yellowgreen',  # 80 <= x < 90
        99: 'green',  # 90 <= x < 100
        100: 'brightgreen'  # 99 < x <= 100
    }

    colour_label = 'red'
    for key, colour in colour_dict.items():
        if coverage_amount < key:
            colour_label = colour
            break

    with open(coverage_path, 'w') as fp:
        json.dump({
            'schemaVersion': 1,
            'label': 'coverage',
            'message': coverage,
            'color': colour_label
        }, fp)
else:
    print(command_output)
