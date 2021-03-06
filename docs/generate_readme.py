import re
import os
import subprocess

# Prepare README.rst for GitHub
# This includes:
#  - Generating command line output
#  - Fixing links

readme_path = 'README.rst'
if not os.path.exists(readme_path):
    print('Error. This must be run from the docs directory')
    exit()

readme = open(readme_path).read()
cmd_regex = r'(\.+\s+program-output::\s+(.+)\s+:shell:)'
padding = ' '*4
def replace_cmd_output(match):
    cmd = match.group(2)
    output = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()
    text = output[0].decode()


    return '.. code:: console\n' + ''.join(map(lambda x: padding + x, text.splitlines(True)))

substitution = re.sub(cmd_regex, replace_cmd_output, readme)


relative_link_regex = r'<a class="reference internal" href="(.*)"><span class="std std-ref">(.*)</span></a>'
# Get generated links
readme_html = open('_build/README.html').read()

relative_link_dict = {name: link for link, name in re.findall(relative_link_regex, readme_html)}

BASE_READTHEDOCS_URL = 'https://chat-downloader.readthedocs.io/en/latest/'
BASE_READTHEDOCS_URL = 'https://chat-downloader.readthedocs.io/en/docs/' # Testing


reference_regex = r':ref:`(.*)`'
def replace_reference_tag(match):
    text = match.group(1)
    url = relative_link_dict.get(text)
    return '`{} <{}{}>`_'.format(text, BASE_READTHEDOCS_URL, url)

substitution = re.sub(reference_regex, replace_reference_tag, substitution)

print(substitution)
