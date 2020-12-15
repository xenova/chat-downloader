class ItemFormatter:

    _DEFAULT_FORMAT = {
        #'normal': {
        'text_message': {
            'template': '{time_text|timestamp} {badges} {author}: {message}',
            'keys': {
                'time_text': {
                    'prefix': '[',
                    'suffix': ']',
                    #'hide_on_empty': False (default True)
                },
                'timestamp': {
                    'prefix': '[',
                    'format': 'd/M/Y hh:mm:ss',
                    'suffix': ']'
                },
                'badges': {
                    'prefix': '(',
                    'function':'join'
                    'suffix': ')'
                },
            },
        }
        #}
    }

    def __init__():
        pass

    @staticmethod
