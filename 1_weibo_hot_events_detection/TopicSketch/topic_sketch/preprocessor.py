__author__ = 'Wei Xie'
__email__ = 'linegroup3@gmail.com'
__affiliation__ = 'Pinnacle Lab for Analytics, Singapore Management University'
__website__ = 'http://mysmu.edu/phdis2012/wei.xie.2012'

from string import punctuation
import re
from collections import deque

import twokenize

import stop_words
import stream
import experiment.exp_config as config
import clean_wb

_PUN_PATTERN = re.compile('^[' + punctuation + ']+$')

_SPACE_PATTERN = re.compile('^\s+')

_HTTP_PATTERN = 'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

_FILTERED_USERS = set(['@girlposts', '@FreddyAmazin', '@ChelseaFC', '@ComedyPosts', '@13elieveSG', '@ComedyTruth', '@ComedyPics'])

_ACTIVE_WINDOW_SIZE = eval(config.get('sketch', 'active_window_size'))

class ActiveTermMaintainer:

    def __init__(self):
        self.active_terms = deque([])

    def add(self, item):
        self.active_terms.append(item)

        while len(self.active_terms) > 0:
            term = self.active_terms[0]
            if term.timestamp < item.timestamp - _ACTIVE_WINDOW_SIZE * 60:
                self.active_terms.popleft()
            else:
                break

    def relevant_tweets(self, keywords):
        ret = list()
        for term in self.active_terms:
            intersection = keywords.intersection(term.tokens)
            if len(intersection) >= 2:
                ret.append(term)

        return ret

active_term_maintainer = ActiveTermMaintainer()

class Preprocessor(stream.ItemStream):

    def __init__(self, _tw_stream):
        self.tw_stream = _tw_stream
        self.wb_cleaner = clean_wb.Clean_Wb();

    def next(self):
        tweet = self.tw_stream.next()

        if tweet is stream.End_Of_Stream:
            return stream.End_Of_Stream

        if tweet is None:
            return None

        if tweet.is_retweet():
            user = tweet.who_is_retweeted()
            if user:
                if user in _FILTERED_USERS:
                    return None

        t = tweet.timestamp
        uid = tweet.uid
        txt = tweet.str

        # clean txt
        try:
            txt = self.wb_cleaner.clean_wb(txt)
        except:
            return None

        # remove all urls
        urls = re.findall(_HTTP_PATTERN, txt)
        for url in urls:
            txt = txt.replace(url, ' ')

        # lower case
        txt = txt.lower()

        # tokenize
        try:
            tokens = twokenize.tokenizeRawTweetText(txt)
        except:
            return None

        # filter
        tokens = filter(lambda x: (not stop_words.contains(x)) and (not _PUN_PATTERN.match(x)) and (len(x) <= 32), tokens)
        # space filter
        tokens = filter(lambda x: not _SPACE_PATTERN.match(x), tokens)

        # to ascii
        #tokens = map(lambda x: x.encode('ascii','ignore'), tokens)
        #tokens = filter(lambda x: len(x) > 0, tokens)
        ret = stream.PreprocessedTweetItem(t, uid, tokens, tweet)
        active_term_maintainer.add(ret)

        return ret