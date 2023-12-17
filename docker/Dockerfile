FROM python:3.12
LABEL maintainer="lauwarm@mailbox.org"

WORKDIR /app

RUN apt-get update && apt-get install gosu -y

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

RUN  echo 'export PATH="${HOME}/.local/bin:${PATH}"'

COPY . /app

RUN mkdir /home/download
RUN mkdir /home/script

COPY ./entrypoint.sh /home/script/

RUN ["chmod", "+x", "/home/script/entrypoint.sh"]

ENTRYPOINT [ "/home/script/entrypoint.sh" ]

CMD python download_chat.py ${channelURL} ${channelName}