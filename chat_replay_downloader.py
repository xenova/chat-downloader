import requests, json, datetime, re, argparse, bs4, csv, emoji, time

class NoChatReplay(Exception):
    """Raised when the video does not contain a chat replay"""
    pass

class InvalidURL(Exception):
    """Raised when the url given is invalid (neither YouTube nor Twitch)"""
    pass

class ChatReplayDownloader:
	__HEADERS = {
		'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
		'Accept-Language': 'en-US, en'
		}

	__YT_REGEX = r'(?:/|%3D|v=|vi=)([0-9A-z-_]{11})(?:[%#?&]|$)'
	__YOUTUBE_API_TEMPLATE = 'https://www.youtube.com/{}/{}?continuation={}&playerOffsetMs={}&hidden=false&pbj=1'

	__TWITCH_REGEX = r'(?:/videos/|/v/)(\d+)'
	__TWITCH_CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko' # public client id
	__TWITCH_API_TEMPLATE = 'https://api.twitch.tv/v5/videos/{}/comments?client_id={}'

	def __init__(self):
		self.session = requests.Session()

	def __session_get(self, url):
		return self.session.get(url, headers=self.__HEADERS)

	def __session_get_json(self, url):
		return self.__session_get(url).json()

	# convert timestamp to seconds
	def __time_to_seconds(self, time):
		return sum(abs(int(x)) * 60 ** i for i, x in enumerate(reversed(time.split(':')))) * (-1 if time[0] == '-' else 1)

	# convert seconds to timestamp
	def __seconds_to_time(self, seconds):
		return re.sub(r'^0:0?','',str(datetime.timedelta(0, seconds)))

	def __create_item(self, timestamp,time_text,time_in_seconds,author,message):
		return {
			'timestamp':timestamp,
			'time_text':time_text,
			'time_in_seconds':time_in_seconds,
			'author':author,
			'message':message
		}

	# Ensure printing to standard output can be done (usually issues with printing emojis and non utf-8 characters)
	def __print_item(self,item):
		time = str(item['timestamp']) if item['time_text'] is None else item['time_text']

		# safe for printing to console, especially on windows
		message = emoji.demojize(item['message']).encode('utf-8').decode('utf-8','ignore')
		print('['+time+']',item['author']+':',message)

	# Parse run method - Reads YouTube formatted messages
	def __parse_message_runs(self, runs):
		message_text = ''

		for run in runs:
			if 'text' in run:
				message_text += run['text']
			elif 'emoji' in run:
				message_text += run['emoji']['shortcuts'][0]
			else:
				raise ValueError('Unknown run: {}'.format(run))

		return message_text

	# Get initial video information
	def __get_initial_youtube_info(self, video_id):
		original_url = 'https://www.youtube.com/watch?v={}'.format(video_id)
		html = self.__session_get(original_url)
		soup = bs4.BeautifulSoup(html.text, 'html.parser')
		ytInitialData_script = next(script.string for script in soup.find_all('script') if script.string and 'ytInitialData' in script.string)
		ytInitialData = json.loads(next(line.strip()[len('window["ytInitialData"] = '):-1] for line in ytInitialData_script.splitlines() if 'ytInitialData' in line))

		columns = ytInitialData['contents']['twoColumnWatchNextResults']
		if('conversationBar' not in columns):
			raise NoChatReplay

		livechat_header = columns['conversationBar']['liveChatRenderer']['header']
		viewselector_submenuitems = livechat_header['liveChatHeaderRenderer']['viewSelector']['sortFilterSubMenuRenderer']['subMenuItems']

		continuation_by_title_map = {
			x['title']: x['continuation']['reloadContinuationData']['continuation']
			for x in viewselector_submenuitems
		}

		return continuation_by_title_map

	def __get_info(self, cont,offset_microseconds, is_live):

		chat_url = self.__YOUTUBE_API_TEMPLATE.format(
			'live_chat' if is_live else 'live_chat_replay',
			'get_live_chat' if is_live else 'get_live_chat_replay',
			cont,
			offset_microseconds)

		info = self.__session_get_json(chat_url)
		return info['response']['continuationContents']['liveChatContinuation']

	def __ensure_seconds(self,time, default = 0):
		try:
			return int(time)
		except ValueError:
			return self.__time_to_seconds(time)
		except:
			return default

	def get_youtube_messages(self, video_id, start_time = 0, end_time = None):
		start_time = self.__ensure_seconds(start_time, 0)
		end_time = self.__ensure_seconds(end_time, None)

		messages = []

		offset_milliseconds = start_time * 1000 if start_time > 0 else 0

		continuation_by_title_map = self.__get_initial_youtube_info(video_id)

		if('Live chat replay' in continuation_by_title_map):
			is_live = False
			continuation_title = 'Live chat replay'
		elif('Live chat' in continuation_by_title_map):
			is_live = True
			continuation_title = 'Live chat'
		else:
			raise NoChatReplay

		continuation = continuation_by_title_map[continuation_title]
		# Top chat replay - Some messages, such as potential spam, may not be visible
		# Live chat replay - All messages are visible

		first_time = True
		# addChatItemAction vs replayChatItemAction
		try:
			while True:
				# must run to get first few messages, otherwise might miss some
				if(first_time):
					info = self.__get_info(continuation,0,is_live)
					first_time = False
				else:
					info = self.__get_info(continuation,offset_milliseconds,is_live)

				if('actions' not in info):
					if(is_live):
						continue # may have more messages for live chat
					else:
						break # no more messages for chat replay

				actions = info['actions']

				for action in actions:

					# test if it is not a message
					if(is_live):
						if 'addChatItemAction' not in action:
							continue
						item = action['addChatItemAction']['item']
					else:
						if 'addChatItemAction' not in action['replayChatItemAction']['actions'][0]:
							continue
						item = action['replayChatItemAction']['actions'][0]['addChatItemAction']['item']

					if 'liveChatTextMessageRenderer' not in item:
						continue
					item_info = item['liveChatTextMessageRenderer']

					message = self.__parse_message_runs(item_info['message']['runs'])
					author = item_info['authorName']['simpleText']
					timestampUsec = int(item_info['timestampUsec'])

					if(is_live):
						timestampText = None
						time_in_seconds = None
					else:
						timestampText = item_info['timestampText']['simpleText']
						time_in_seconds = int(self.__time_to_seconds(timestampText))

						if(end_time is not None and time_in_seconds > end_time):
							return messages

					if(is_live or time_in_seconds >= start_time):
						data = self.__create_item(timestampUsec,timestampText,time_in_seconds,author,message)
						messages.append(data)
						self.__print_item(data)

				continuation_info = info['continuations'][0]
				for key in ('invalidationContinuationData','timedContinuationData','liveChatReplayContinuationData'):
					if key in continuation_info:
						continuation = continuation_info[key]['continuation']

				if 'timeoutMs' in continuation_info: # must wait before calling again
					time.sleep(continuation_info['timeoutMs']/1000)

			return messages

		except KeyboardInterrupt:
			return messages

	def get_twitch_messages(self, video_id, start_time = 0, end_time = None):
		start_time = self.__ensure_seconds(start_time, 0)
		end_time = self.__ensure_seconds(end_time, None)

		messages = []
		api_url = self.__TWITCH_API_TEMPLATE.format(video_id,self.__TWITCH_CLIENT_ID)

		cursor = ''
		try:
			while True:
				url = '{}&cursor={}&content_offset_seconds={}'.format(api_url,cursor,start_time)
				info = self.__session_get_json(url)

				for comment in info['comments']:
					time_in_seconds = float(comment['content_offset_seconds'])
					if(time_in_seconds < start_time):
						continue

					if(end_time is not None and time_in_seconds > end_time):
						return messages

					message = comment['message']['body']
					author = comment['commenter']['display_name']
					created_at = comment['created_at']

					timestampUsec = int(datetime.datetime.strptime(created_at, '%Y-%m-%dT%H:%M:%S.%fZ' if '.' in created_at else '%Y-%m-%dT%H:%M:%SZ').timestamp()*1e6)
					timestampText = self.__seconds_to_time(int(time_in_seconds))

					data = self.__create_item(timestampUsec,timestampText,time_in_seconds,author,message)
					messages.append(data)

					self.__print_item(data)

				if '_next' in info:
					cursor = info['_next']
				else:
					return messages
		except KeyboardInterrupt:
			return messages

	def get_chat_replay(self, url, start_time = 0, end_time = None):

		match = re.search(self.__YT_REGEX,url)
		if(match):
			return self.get_youtube_messages(match.group(1), start_time, end_time)

		match = re.search(self.__TWITCH_REGEX,url)
		if(match):
			return self.get_twitch_messages(match.group(1), start_time, end_time)

		raise InvalidURL

chat_downloader = ChatReplayDownloader()

def get_chat_replay(url, start_time = 0, end_time = None):
	return chat_downloader.get_chat_replay(url,start_time,end_time)

def get_youtube_messages(url, start_time = 0, end_time = None):
	return chat_downloader.get_youtube_messages(url,start_time,end_time)

def get_twitch_messages(url, start_time = 0, end_time = None):
	return chat_downloader.get_twitch_messages(url,start_time,end_time)


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Retrieve YouTube/Twitch chat from past broadcasts/VODs.')
	parser.add_argument('url', help='YouTube/Twitch video URL')
	parser.add_argument('-start_time','-from', default=0, help='start time in seconds or hh:mm:ss (default: 0)')
	parser.add_argument('-end_time', '-to', default=None, help='end time in seconds or hh:mm:ss (default: None = until the end)')
	parser.add_argument('-output','-o', default=None, help='output file (default: None = print to standard output)')

	args = parser.parse_args()

	try:

		chat_messages = chat_downloader.get_chat_replay(args.url,start_time=args.start_time, end_time=args.end_time)

		if(args.output != None):
			if(args.output.endswith('.json')):
				with open(args.output, 'w') as fp:
					json.dump(chat_messages, fp)
			elif(args.output.endswith('.csv')):
				with open(args.output, 'w', newline='',encoding='utf-8') as fp:
					if(len(chat_messages)>0):
						fc = csv.DictWriter(fp,fieldnames=chat_messages[0].keys())
						fc.writeheader()
						fc.writerows(chat_messages)
			else:
				f = open(args.output,'w',encoding='utf-8')
				for message in chat_messages:
					print('['+message['time_text']+']',message['author']+':',message['message'],file=f)
				f.close()

			print('Finished writing',len(chat_messages),'messages to',args.output)

	except InvalidURL:
		print('Invalid URL.')
	except NoChatReplay:
		print('Video does not have a chat replay.')
	except KeyboardInterrupt:
		print('Interrupted.')
