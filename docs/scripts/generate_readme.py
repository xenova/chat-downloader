import re
import os
from run_cmd import replace_cmd_output

# Prepare README.rst for GitHub
# This includes:
#  - Generating command line output
#  - Fixing links

readme_path = 'README.rst'
if not os.path.exists(readme_path):
    print('Error. This must be run from the docs directory')
    exit()

substitution = replace_cmd_output(readme_path)

# Parse Links

relative_link_regex = r'<a class="reference internal" href="(.*)"><span class="std std-ref">(.*)</span></a>'
# Get generated links
readme_html = open('_build/README.html').read()

relative_link_dict = {name: link for link,
                      name in re.findall(relative_link_regex, readme_html)}

BASE_READTHEDOCS_URL = 'https://chat-downloader.readthedocs.io/en/latest/'
# BASE_READTHEDOCS_URL = 'https://chat-downloader.readthedocs.io/en/docs/' # Testing


reference_regex = r':ref:`(.*)`'


def replace_reference_tag(match):
    text = match.group(1)
    url = relative_link_dict.get(text)
    return f'`{text} <{BASE_READTHEDOCS_URL}{url}>`_'


print(re.sub(reference_regex, replace_reference_tag, substitution))
