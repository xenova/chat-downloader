import requests
import json
import datetime
import re
import argparse
import bs4
import csv
import emoji
import time


class NoChatReplay(Exception):
	"""Raised when the video does not contain a chat replay"""
	pass


class InvalidURL(Exception):
	"""Raised when the url given is invalid (neither YouTube nor Twitch)"""
	pass


class NoContinuation(Exception):
	"""Raised when there are no more messages to retrieve (in a live stream)"""
	pass


class ChatReplayDownloader:
	__HEADERS = {
		'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
		'Accept-Language': 'en-US, en'
	}

	__YT_REGEX = r'(?:/|%3D|v=|vi=)([0-9A-z-_]{11})(?:[%#?&]|$)'
	__YOUTUBE_API_BASE_TEMPLATE = 'https://www.youtube.com/{}/{}?continuation={}&pbj=1&hidden=false'
	__YOUTUBE_API_PARAMETERS_TEMPLATE = '&playerOffsetMs={}'

	__TWITCH_REGEX = r'(?:/videos/|/v/)(\d+)'
	__TWITCH_CLIENT_ID = 'kimne78kx3ncx6brgo4mv6wki5h1ko'  # public client id
	__TWITCH_API_TEMPLATE = 'https://api.twitch.tv/v5/videos/{}/comments?client_id={}'

	__TYPES_OF_MESSAGES = {
		'ignore': [
			# message saying Live Chat replay is on
			'liveChatViewerEngagementMessageRenderer',
			'liveChatPlaceholderItemRenderer',  # placeholder
			'liveChatModeChangeMessageRenderer'  # e.g. slow mode enabled
		],
		'message': [
			'liveChatTextMessageRenderer'  # normal message
		],
		'superchat_message': [  # superchat messages which appear in chat
			'liveChatMembershipItemRenderer',
			'liveChatPaidMessageRenderer',
			'liveChatPaidStickerRenderer'
		],
		'superchat_ticker': [  # superchat messages which appear ticker (at the top)
			'liveChatTickerPaidStickerItemRenderer',
			'liveChatTickerPaidMessageItemRenderer',
			'liveChatTickerSponsorItemRenderer',
		]
	}

	# used for debugging
	__TYPES_OF_KNOWN_MESSAGES = []
	for key in __TYPES_OF_MESSAGES:
		__TYPES_OF_KNOWN_MESSAGES.extend(__TYPES_OF_MESSAGES[key])

	__IMPORTANT_KEYS_AND_REMAPPINGS = {
		'timestampUsec': 'timestamp',
		'authorName': 'author',
		'purchaseAmountText': 'amount',
		'message': 'message',
		'headerBackgroundColor': 'header_color',
		'bodyBackgroundColor': 'body_color',
		'timestampText': 'time_text',
		'amount': 'amount',
		'startBackgroundColor': 'body_color',
		'durationSec': 'ticker_duration',
		'detailText': 'message',
		'headerSubtext': 'message',  # equivalent to message - get runs
		'backgroundColor': 'body_color'
	}

	def __init__(self):
		self.session = requests.Session()

	def __session_get(self, url):
		return self.session.get(url, headers=self.__HEADERS)

	def __session_get_json(self, url):
		return self.__session_get(url).json()

	# convert timestamp to seconds
	def __time_to_seconds(self, time):
		return sum(abs(int(x)) * 60 ** i for i, x in enumerate(reversed(time.replace(',','').split(':')))) * (-1 if time[0] == '-' else 1)

	# convert seconds to timestamp
	def __seconds_to_time(self, seconds):
		return re.sub(r'^0:0?', '', str(datetime.timedelta(0, seconds)))

	# convert argb integer to rgba array
	def __arbg_int_to_rgba(self, argb_int):
		red = (argb_int >> 16) & 255
		green = (argb_int >> 8) & 255
		blue = argb_int & 255
		alpha = (argb_int >> 24) & 255
		return [red, green, blue, alpha]

	# convert rgba colours to hex
	def __rgba_to_hex(self, colours):
		return '#{:02x}{:02x}{:02x}{:02x}'.format(*colours)

	def __get_colours(self, argb_int):
		rgba_colour = self.__arbg_int_to_rgba(argb_int)
		hex_colour = self.__rgba_to_hex(rgba_colour)
		return {
			'rgba': rgba_colour,
			'hex': hex_colour
		}

	def message_to_string(self, item):
		return '[{}] {}{}: {}'.format(
			item['time_text'] or str(item['timestamp']),
			'*{}* '.format(item['amount']) if 'amount' in item else '',
			item['author'],
			item['message'] or ''
		)

	# Ensure printing to standard output can be done
	# (usually issues with printing emojis and non utf-8 characters)
	# safe for printing to console, especially on windows
	def __print_item(self, item):
		message = self.message_to_string(item)
		safe_string = emoji.demojize(message).encode(
			'utf-8').decode('utf-8', 'ignore')
		print(safe_string)

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
		ytInitialData_script = next(script.string for script in soup.find_all(
			'script') if script.string and 'ytInitialData' in script.string)
		ytInitialData = json.loads(next(line.strip()[len('window["ytInitialData"] = '):-1]
										for line in ytInitialData_script.splitlines() if 'ytInitialData' in line))

		columns = ytInitialData['contents']['twoColumnWatchNextResults']
		if('conversationBar' not in columns or 'liveChatRenderer' not in columns['conversationBar']):
			raise NoChatReplay

		livechat_header = columns['conversationBar']['liveChatRenderer']['header']
		viewselector_submenuitems = livechat_header['liveChatHeaderRenderer'][
			'viewSelector']['sortFilterSubMenuRenderer']['subMenuItems']

		continuation_by_title_map = {
			x['title']: x['continuation']['reloadContinuationData']['continuation']
			for x in viewselector_submenuitems
		}

		return continuation_by_title_map

	def __get_replay_info(self, continuation, offset_microseconds):
		url = self.__YOUTUBE_API_BASE_TEMPLATE.format(
			'live_chat_replay', 'get_live_chat_replay', continuation) + self.__YOUTUBE_API_PARAMETERS_TEMPLATE.format(offset_microseconds)
		return self.__get_continuation_info(url)

	def __get_live_info(self, continuation):
		url = self.__YOUTUBE_API_BASE_TEMPLATE.format(
			'live_chat', 'get_live_chat', continuation)
		return(self.__get_continuation_info(url))

	def __get_continuation_info(self, url):
		info = self.__session_get_json(url)
		if('continuationContents' in info['response']):
			return info['response']['continuationContents']['liveChatContinuation']
		else:
			raise NoContinuation

	def __ensure_seconds(self, time, default=0):
		try:
			return int(time)
		except ValueError:
			return self.__time_to_seconds(time)
		except:
			return default

	def __parse_item(self, item):
		data = {}
		index = list(item.keys())[0]
		item_info = item[index]

		# Never before seen index, may cause error (used for debugging)
		if(index not in self.__TYPES_OF_KNOWN_MESSAGES):
			pass

		important_item_info = {key: value for key, value in item_info.items(
		) if key in self.__IMPORTANT_KEYS_AND_REMAPPINGS}

		data.update(important_item_info)

		for key in important_item_info:
			new_key = self.__IMPORTANT_KEYS_AND_REMAPPINGS[key]
			data[new_key] = data.pop(key)

			# get simpleText if it exists
			if(type(data[new_key]) is dict and 'simpleText' in data[new_key]):
				data[new_key] = data[new_key]['simpleText']

		if('showItemEndpoint' in item_info):  # has additional information
			data.update(self.__parse_item(
				item_info['showItemEndpoint']['showLiveChatItemEndpoint']['renderer']))
			return data

		data['message'] = self.__parse_message_runs(
			data['message']['runs']) if 'message' in data else None

		if('timestamp' in data):
			data['timestamp'] = int(data['timestamp'])
			data['time_in_seconds'] = int(
				self.__time_to_seconds(data['time_text']))
		else:
			data['timestamp'] = None
			data['time_in_seconds'] = None

		for colour_key in ('header_color', 'body_color'):
			if(colour_key in data):
				data[colour_key] = self.__get_colours(data[colour_key])

		return data

	def get_youtube_messages(self, video_id, start_time=0, end_time=None, message_type='messages'):
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

		# Top chat replay - Some messages, such as potential spam, may not be visible
		# Live chat replay - All messages are visible
		continuation = continuation_by_title_map[continuation_title]

		first_time = True
		try:
			while True:
				try:
					if(is_live):
						info = self.__get_live_info(continuation)

						if('actions' not in info):
							continuation_info = info['continuations'][0]['timedContinuationData']
							if 'timeoutMs' in continuation_info:
								# must wait before calling again
								# prevents 429 errors (too many requests)
								time.sleep(continuation_info['timeoutMs']/1000)

							continue  # may have more messages for live chat

					else:

						# must run to get first few messages, otherwise might miss some
						if(first_time):
							info = self.__get_replay_info(continuation, 0)
							first_time = False
						else:
							info = self.__get_replay_info(
								continuation, offset_milliseconds)

						if('actions' not in info):
							break  # no more messages for chat replay

				except NoContinuation:
					print('No continuation found, stream may have ended.')
					break

				actions = info['actions']

				for action in actions:
					if('replayChatItemAction' in action):
						action = action['replayChatItemAction']['actions'][0]

					action_name = list(action.keys())[0]
					if('item' not in action[action_name]):
						# not a valid item to display (usually message deleted)
						continue

					item = action[action_name]['item']
					index = list(item.keys())[0]

					if(index in self.__TYPES_OF_MESSAGES['ignore']):
						# can ignore message (not a chat message)
						continue

					# user wants everything, keep going
					if(message_type == 'all'):
						pass

					# user does not want superchat + message is superchat
					elif(message_type != 'superchat' and index in self.__TYPES_OF_MESSAGES['superchat_message'] + self.__TYPES_OF_MESSAGES['superchat_ticker']):
						continue

					# user does not want normal messages + message is normal
					elif(message_type != 'messages' and index in self.__TYPES_OF_MESSAGES['message']):
						continue

					data = self.__parse_item(item)

					time_in_seconds = data['time_in_seconds']
					if(end_time is not None and time_in_seconds > end_time):
						return messages

					if(is_live or time_in_seconds >= start_time):
						messages.append(data)

						# print if it is not a ticker message (prevents duplicates)
						if(index not in self.__TYPES_OF_MESSAGES['superchat_ticker']):
							self.__print_item(data)

				continuation_info = info['continuations'][0]
				for key in ('invalidationContinuationData', 'timedContinuationData', 'liveChatReplayContinuationData'):
					if key in continuation_info:
						continuation = continuation_info[key]['continuation']

			return messages

		except KeyboardInterrupt:
			return messages

	def get_twitch_messages(self, video_id, start_time=0, end_time=None):
		start_time = self.__ensure_seconds(start_time, 0)
		end_time = self.__ensure_seconds(end_time, None)

		messages = []
		api_url = self.__TWITCH_API_TEMPLATE.format(
			video_id, self.__TWITCH_CLIENT_ID)

		cursor = ''
		try:
			while True:
				url = '{}&cursor={}&content_offset_seconds={}'.format(
					api_url, cursor, start_time)
				info = self.__session_get_json(url)

				for comment in info['comments']:
					time_in_seconds = float(comment['content_offset_seconds'])
					if(time_in_seconds < start_time):
						continue

					if(end_time is not None and time_in_seconds > end_time):
						return messages

					created_at = comment['created_at']

					data = {
						'timestamp': int(datetime.datetime.strptime(
							created_at, '%Y-%m-%dT%H:%M:%S.%fZ' if '.' in created_at else '%Y-%m-%dT%H:%M:%SZ').timestamp()*1e6),
						'time_text': self.__seconds_to_time(int(time_in_seconds)),
						'time_in_seconds': time_in_seconds,
						'author': comment['commenter']['display_name'],
						'message': comment['message']['body']
					}

					messages.append(data)

					self.__print_item(data)

				if '_next' in info:
					cursor = info['_next']
				else:
					return messages
		except KeyboardInterrupt:
			return messages

	def get_chat_replay(self, url, start_time=0, end_time=None, message_type='messages'):

		match = re.search(self.__YT_REGEX, url)
		if(match):
			return self.get_youtube_messages(match.group(1), start_time, end_time, message_type)

		match = re.search(self.__TWITCH_REGEX, url)
		if(match):
			return self.get_twitch_messages(match.group(1), start_time, end_time)

		raise InvalidURL


chat_downloader = ChatReplayDownloader()


def get_chat_replay(url, start_time=0, end_time=None, message_type='messages'):
	return chat_downloader.get_chat_replay(url, start_time, end_time, message_type)


def get_youtube_messages(url, start_time=0, end_time=None, message_type='messages'):
	return chat_downloader.get_youtube_messages(url, start_time, end_time, message_type)


def get_twitch_messages(url, start_time=0, end_time=None):
	return chat_downloader.get_twitch_messages(url, start_time, end_time)


if __name__ == '__main__':
	parser = argparse.ArgumentParser(
		description='Retrieve YouTube/Twitch chat from past broadcasts/VODs.',
		formatter_class=argparse.RawTextHelpFormatter)

	parser.add_argument('url', help='YouTube/Twitch video URL')

	parser.add_argument('-start_time', '-from', default=0,
						help='start time in seconds or hh:mm:ss\n(default: %(default)s)')
	parser.add_argument('-end_time', '-to', default=None,
						help='end time in seconds or hh:mm:ss\n(default: %(default)s = until the end)')

	parser.add_argument('-message_type', choices=['messages', 'superchat', 'all'], default='messages',
						help='types of messages to include [YouTube only]\n(default: %(default)s)')

	parser.add_argument('-output', '-o', default=None,
						help='name of output file\n(default: %(default)s = print to standard output)')

	args = parser.parse_args()

	try:
		chat_messages = chat_downloader.get_chat_replay(
			args.url, start_time=args.start_time, end_time=args.end_time, message_type=args.message_type)

		if(args.output != None):
			num_of_messages = len(chat_messages)
			if(args.output.endswith('.json')):
				with open(args.output, 'w') as fp:
					json.dump(chat_messages, fp)
			elif(args.output.endswith('.csv')):
				with open(args.output, 'w', newline='', encoding='utf-8') as fp:

					fieldnames = []
					for message in chat_messages:
						fieldnames+=message.keys()

					if(num_of_messages > 0):
						fc = csv.DictWriter(fp,fieldnames=list(set(fieldnames)))
						fc.writeheader()
						fc.writerows(chat_messages)
			else:
				f = open(args.output, 'w', encoding='utf-8')
				num_of_messages = 0 # reset count
				for message in chat_messages:
					if('ticker_duration' not in message): # needed for duplicates
						num_of_messages += 1
						print(chat_downloader.message_to_string(message), file=f)
				f.close()

			print('Finished writing', num_of_messages,
				  'messages to', args.output)

	except InvalidURL:
		print('Invalid URL.')
	except NoChatReplay:
		print('Video does not have a chat replay.')
	except KeyboardInterrupt:
		print('Interrupted.')
