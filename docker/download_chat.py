import subprocess, sys
from datetime import datetime

channel_url = sys.argv[1]
channel_name = sys.argv[2]

now = datetime.now()
d1 = now.strftime("%Y%m%d-%H%M%S")

subprocess.run(['chat_downloader', channel_url, '--output', "/home/download/"+channel_name+"-"+d1+'.json'])