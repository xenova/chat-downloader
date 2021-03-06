import re
import os
import subprocess

# Generate command line output

readme_path = 'README.rst'
if not os.path.exists(readme_path):
    print('Error. This must be run from the docs directory')
    exit()

readme = open(readme_path).read()
cmd_regex = r'(\.+\s+program-output::\s+(.+)\s+:shell:)'

def replace(match):
    cmd = match.group(2)
    output = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()
    return output[0].decode()

substitution = re.sub(cmd_regex, replace, readme)

print(substitution)
