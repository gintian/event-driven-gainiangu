__author__ = 'Wei Xie'
__email__ = 'linegroup3@gmail.com'
__affiliation__ = 'Pinnacle Lab for Analytics, Singapore Management University'
__website__ = 'http://mysmu.edu/phdis2012/wei.xie.2012'


import calendar, datetime
from collections import deque
import math

from scipy.sparse import dok_matrix
from scipy.sparse import csr_matrix
import numpy as np

import fast_hashing
import solver
import fast_smoother
import stemmer
import postprocessor

import experiment.exp_config as config

import experiment.event_output as event_output


_SKETCH_BUCKET_SIZE = eval(config.get('sketch', 'sketch_bucket_size'))

_NUM_TOPICS = eval(config.get('sketch', 'num_topics'))

_PROBABILITY_THRESHOLD = eval(config.get('sketch', 'probability_threshold'))

_ACTIVE_WINDOW_SIZE = eval(config.get('sketch', 'active_window_size'))

_CUT_TIMESTAMP = eval(config.get('sketch', 'cut_timestamp'))

_MAX_NUMBER_WORDS = eval(config.get('sketch', 'max_number_words'))


class SparseSmootherContainer():
    _THRESHOLD_FOR_CLEANING = eval(config.get('sketch', 'threshold_for_cleaning'))
    _CAPACITY_FOR_CLEANING = eval(config.get('sketch', 'capacity_for_cleaning'))

    def __init__(self):
        self.container = {}

        self.is_xsmoother = None

        if config.get('sketch', 'smoother') == 'XEWMASmoother':
            print 'Using XEWMASmoother.'
            self.is_xsmoother = True

        if config.get('sketch', 'smoother') == 'EWMASmoother':
            print 'Using EWMASmoother.'
            self.is_xsmoother = False

    def close(self):
        pass

    def _clean(self, _timestamp):
        to_be_cleaned_up = []
        for key, value in self.container.iteritems():
            tp = value.get(_timestamp)
            if not tp:
                print _timestamp, value.timestamp
                print 'stream item seems out of time order!'
                continue
            t ,v ,a = tp
            if v <= self._THRESHOLD_FOR_CLEANING: # check v
                to_be_cleaned_up.append(key)

        print 'cleaning', len(to_be_cleaned_up), 'items...'
        for key in to_be_cleaned_up:
            self.container.pop(key)

    def get(self, _id, _timestamp):
        # check for cleaning
        if len(self.container) > self._CAPACITY_FOR_CLEANING:
            self._clean(_timestamp)

        # return
        if _id in self.container:
            return self.container[_id]
        else:

            if self.is_xsmoother:
                _smoother = fast_smoother.XEWMASmoother()
            else:
                _smoother = fast_smoother.EWMASmoother()

            self.container[_id] = _smoother
            return _smoother


class TopicSketch:

    def __init__(self):

        self.sketch_m2 = [SparseSmootherContainer() for i in range(fast_hashing.HASH_NUMBER)]
        self.sketch_m3 = [SparseSmootherContainer() for i in range(fast_hashing.HASH_NUMBER)]

        self.timestamp = 0

        self.active_terms = deque([])

        np.random.seed(0)
        self.random_projector = np.random.rand(_SKETCH_BUCKET_SIZE)

    def close(self):
        pass

    @staticmethod
    def _index(i, j):
        return i * _SKETCH_BUCKET_SIZE + j

    @staticmethod
    def _inverse_index(_id):
        i = _id / _SKETCH_BUCKET_SIZE
        _id -= i * _SKETCH_BUCKET_SIZE

        j = _id

        return i, j

    @staticmethod
    def _cut(_t):
        _d = datetime.datetime.utcfromtimestamp(_t)
        _d = datetime.datetime(_d.year, _d.month, _d.day)
        return calendar.timegm(_d.timetuple())

    def pre_process(self, uid, tokens):
        # adding into active terms before stemming
        self.active_terms.append((self.timestamp, tokens, uid))

        while len(self.active_terms) > 0:
            term = self.active_terms[0]
            if term[0] < self.timestamp - _ACTIVE_WINDOW_SIZE * 60:
                self.active_terms.popleft()
            else:
                break

        # stemming
        tokens = map(lambda x: stemmer.stem(x), tokens)

        if len(tokens) < 3:
            return None

        # hashing
        results = [] # (counts, random_projectors, n_words, h)

        for h in range(fast_hashing.HASH_NUMBER):
            results.append(({}, {}, len(tokens), h))

        for token in tokens:
            hash_code = np.array(fast_hashing.hash_code(token)) % _SKETCH_BUCKET_SIZE

            for h in range(fast_hashing.HASH_NUMBER):
                code = hash_code[h]
                if code in results[h][0]:
                    results[h][0][code] += 1
                else:
                    results[h][0][code] = 1

                #results[h][1][code] = hash(token) % 2

        return results

    def process_m2_unit(self, _count, _n_words, _h):
        s = _n_words * (_n_words - 1.0)

        for k1 in _count:
            for k2 in _count:
                if k1 > k2:
                    continue
                if k1 == k2:
                    num = _count[k1] * (_count[k1] - 1)
                else:
                    num = _count[k1] * _count[k2]

                if num == 0:
                    continue

                num /= s

                if _CUT_TIMESTAMP:
                    self.sketch_m2[_h].get(self._index(k1, k2), self.timestamp).observe(TopicSketch._cut(self.timestamp), num)
                else:
                    self.sketch_m2[_h].get(self._index(k1, k2), self.timestamp).observe(self.timestamp, num)

    def process_m3_unit(self, _count, _random_projector, _n_words, _h):
        s = _n_words * (_n_words - 1.0) * (_n_words - 2.0)

        for k1 in _count:
            for k2 in _count:
                if k1 > k2:
                    continue
                num = 0
                for k3 in _count:

                    if k1 == k2 and k2 == k3:
                        v = _count[k1] * (_count[k1] - 1) * (_count[k1] - 2)
                    elif k1 == k2:
                        v = _count[k1] * (_count[k1] - 1) * _count[k3]
                    elif k2 == k3:
                        v = _count[k2] * (_count[k2] - 1) * _count[k1]
                    elif k3 == k1:
                        v = _count[k3] * (_count[k3] - 1) * _count[k2]
                    else:
                        v = _count[k1] * _count[k2] * _count[k3]

                    #num += v * _random_projector[k3]
                    num += v * self.random_projector[k3]

                if num == 0:
                    continue

                num /= s

                if _CUT_TIMESTAMP:
                    self.sketch_m3[_h].get(self._index(k1, k2), self.timestamp).observe(TopicSketch._cut(self.timestamp), num)
                else:
                    self.sketch_m3[_h].get(self._index(k1, k2), self.timestamp).observe(self.timestamp, num)

    def process_unit(self, _results):
        _count = _results[0]
        _random_projector = _results[1]
        _n_words = _results[2]
        _h = _results[3]
        # print _count, _random_projector, _n_words, _h
        self.process_m2_unit(_count, _n_words, _h)
        self.process_m3_unit(_count, _random_projector, _n_words, _h)

    def process(self, _ptweet):
        self.timestamp = _ptweet.timestamp

        results = self.pre_process(_ptweet.uid, _ptweet.tokens)

        if results is None:
            return

        map(self.process_unit, results)

    def infer_unit(self, _h):
        infer_threshold = 1e-6

        k = _NUM_TOPICS
        n = _SKETCH_BUCKET_SIZE

        m2 = dok_matrix((n, n), dtype=np.float64)
        m3 = dok_matrix((n, n), dtype=np.float64)

        container = self.sketch_m2[_h]
        for key, value in container.container.iteritems():
            i, j = self._inverse_index(key)
            if _CUT_TIMESTAMP:
                v = value.get(TopicSketch._cut(self.timestamp))[2]
                if abs(v) > infer_threshold:
                    m2[i,j] = v
                    if i != j:
                        m2[j,i] = v
            else:
                v = value.get(self.timestamp)[2]
                if abs(v) > infer_threshold:
                    m2[i,j] = v
                    if i != j:
                        m2[j,i] = v

        container = self.sketch_m3[_h]
        for key, value in container.container.iteritems():
            i, j = self._inverse_index(key)
            if _CUT_TIMESTAMP:
                v = value.get(TopicSketch._cut(self.timestamp))[2]
                if abs(v) > infer_threshold:
                    m3[i,j] = v
                    if i != j:
                        m3[j,i] = v
            else:
                v = value.get(self.timestamp)[2]
                if abs(v) > infer_threshold:
                    m3[i,j] = v
                    if i != j:
                        m3[j,i] = v

        return solver.solve(csr_matrix(m2), csr_matrix(m3), n, k)

    @staticmethod
    def refine_prob(_prob):
        prob = _prob.real
        prob = map(lambda x: x if x > 0 else 0, prob)
        prob = prob / sum(prob)
        return prob

    def run_time_infer(self):
        infer_results = map(self.infer_unit, range(fast_hashing.HASH_NUMBER))

        probs = list()
        for i in range(len(infer_results)):
            a = infer_results[i][0]
            print 'a=', max(a, key=lambda x: x.real).real
            k = a.index(max(a, key=lambda x: x.real))
            v = infer_results[i][2]
            prob = self.refine_prob(v[:, k])
            probs.append(prob)

        self.analyse_topics(probs)

    def analyse_topics(self, _probs):
        words = set()
        for term in self.active_terms:
            for word in term[1]:
                words.add(word)
        print "size of words:", len(words)

        high_prob_words = []
        for _word in words:
            word = stemmer.stem(_word)
            hash_code = np.array(fast_hashing.hash_code(word)) % _SKETCH_BUCKET_SIZE
            min_prob_list = []
            for h in range(fast_hashing.HASH_NUMBER):
                prob = _probs[h][hash_code[h]]
                min_prob_list.append(prob)

            min_prob_list.sort()
            min_prob = min_prob_list[1] # !!!
            if min_prob >= _PROBABILITY_THRESHOLD:
                high_prob_words.append((word, min_prob, hash_code))

        high_prob_words.sort(key=lambda x: x[1], reverse=True)
        high_prob_words = high_prob_words[:_MAX_NUMBER_WORDS]

        print high_prob_words

        _kws = list()
        _kps = list()

        post_result = postprocessor.process(high_prob_words, self.active_terms)

        print post_result

        if not post_result[0]:
            return

        _event = dict()
        _id = event_output.getId()
        _event['eid'] = _id
        _event['topicID'] = _id

        _event['info.dtime'] = str(datetime.datetime.utcfromtimestamp(self.timestamp))

        '''
        for high_prob_word in high_prob_words:
            _kws.append(high_prob_word[0])
            _kps.append(high_prob_word[1])'''
        word_level_result = post_result[1]
        for i in range(len(high_prob_words)):
            high_prob_word = high_prob_words[i]
            if word_level_result[i]:
                _kws.append(high_prob_word[0])
                _kps.append(high_prob_word[1])


        _event['info.keywords'] = _kws
        _event['info.probs'] = _kps

        _event['info.numUsers'] = post_result[3]
        _event['info.numGeoUsers'] = 0
        _event['info.numTweets'] = post_result[2]
        _event['info.numGeoTweets'] = 0

        event_output.put(_id, _event)



