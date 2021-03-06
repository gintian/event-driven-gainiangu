__author__ = 'Wei Xie'
__email__ = 'linegroup3@gmail.com'
__affiliation__ = 'Pinnacle Lab for Analytics, Singapore Management University'
__website__ = 'http://mysmu.edu/phdis2012/wei.xie.2012'


import topic_sketch.stream as stream

from topic_sketch import preprocessor

import calendar



class TweetStreamFromFile(stream.ItemStream):

    def __init__(self, end):
        self.end = calendar.timegm(end.timetuple())
        self.f = open('/media/sf_share/tweets2.txt', 'r')
        print self.f.next()

    def next(self):
        _t = None
        _user = None
        _tweet = None

        while True:
            try:
                line = self.f.next()
                if line.startswith('content: '):
                    _tweet = line.split('content: ')[1]

                if line.startswith('userId: '):
                    _user = eval(line.split('userId: ')[1])

                if line.startswith('publishedTimeGmt: '):
                    _t = eval(line.split('publishedTimeGmt: ')[1]) / 1000
                    _t += 8*60*60# 8 hours

                    if _t > self.end:
                        return stream.End_Of_Stream

                if line.startswith('-------------'):
                    item = stream.RawTweetItem(_t, _user, _tweet)
                    return item

                if line is None:
                    return stream.End_Of_Stream
            except:
                return stream.End_Of_Stream

        return None


def test():
    tweet_stream = TweetStreamFromFile(datetime.datetime(2016, 1, 1))
    _preprocessor = preprocessor.Preprocessor(tweet_stream)

    tweet = _preprocessor.next()

    while tweet is not stream.End_Of_Stream:
        if tweet is None:
            tweet = _preprocessor.next()
            continue

        tokens = tweet.tokens
        t = tweet.datetime()

        if '#sg50' in tokens or 'sg50' in tokens:
            print t

        tweet = _preprocessor.next()

import matplotlib.pyplot as plt
def test_sg50():
    results = list()
    start = datetime.datetime(2015, 8, 7)
    end = datetime.datetime(2015, 8, 12)
    d = datetime.timedelta(hours=1)
    count = 0
    f = open('./sg50.txt')
    for line in f:
        if line.startswith('2015-'):
            t = datetime.datetime.strptime(line[:-1], '%Y-%m-%d %H:%M:%S')
            if t >= start:
                if t < start + d:
                    count += 1
                else:
                    if t >=  end:
                        break
                    results.append((start, count))
                    start = start + d
                    count = 1

    for result in results:
        print str(result[0]) + '\t' + str(result[1]) + '\t' + '' + '\t' + '0'

    plt.plot(map(lambda x:x[0], results), map(lambda x:x[1], results))
    plt.show()

import datetime


def test2():
    retweeted_counter = dict()

    tweet_stream = TweetStreamFromFile(datetime.datetime(2015, 7, 14))

    tweet = tweet_stream.next()

    while tweet is not stream.End_Of_Stream:
        if tweet:
            if tweet.is_retweet():
                user = tweet.who_is_retweeted()

                if user:
                    if user in retweeted_counter:
                        retweeted_counter[user] += 1
                    else:
                        retweeted_counter[user] = 1

        tweet = tweet_stream.next()

    counter = list()

    for user in retweeted_counter:
        count = retweeted_counter[user]
        if count >= 1000:
            counter.append((user, count))

    counter = sorted(counter, key=lambda x:x[1], reverse = True)

    for c in counter:
        print c[0] , c[1]


# for hashtags
def test3():
    hashtag_counter = dict()

    _stream = TweetStreamFromFile(datetime.datetime(2016, 1, 1))

    tweet_stream = preprocessor.Preprocessor(_stream)

    tweet = tweet_stream.next()

    while tweet is not stream.End_Of_Stream:
        if tweet:
            for token in tweet.tokens:
                if token.startswith('#'):
                    if token in hashtag_counter:
                        hashtag_counter[token] += 1
                    else:
                        hashtag_counter[token] = 1

        tweet = tweet_stream.next()

    counter = list()

    for hashtag in hashtag_counter:
        count = hashtag_counter[hashtag]
        if count >= 3000:
            counter.append((hashtag, count))

    counter = sorted(counter, key=lambda x:x[1], reverse = True)

    for c in counter:
        print c[0] , c[1]


