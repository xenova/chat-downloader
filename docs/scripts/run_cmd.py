import subprocess
import re


def run_cmd(cmd):
    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()[0].decode()


def cmd_output(cmd, padding=' '*4):
    text = run_cmd(cmd)
    return '.. code:: console\n\n' + ''.join(map(lambda x: padding + x, text.splitlines(True)))


def replace_cmd_output(f):

    file_data = open(f).read()
    cmd_regex = r'(\.+\s+program-output::\s+(.+)\s+:shell:)'

    return re.sub(cmd_regex, lambda x: cmd_output(x.group(2)), file_data)
