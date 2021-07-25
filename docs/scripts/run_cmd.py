import subprocess
import re


def run_cmd(cmd):
    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True).communicate()[0].decode()


def cmd_output(cmd, padding=' '*4):
    text = run_cmd(cmd)
    return '.. code:: console\n\n' + ''.join(map(lambda x: padding + x, text.splitlines(True)))


def replace_cmd_output(f):

    file_data = open(f).read()
    cmd_regex = r'(?:\.+\s+program-output::\s+(.+)\s+:shell:)'

    def run(x):
        return cmd_output(x.group(1))

    return re.sub(cmd_regex, run, file_data)
