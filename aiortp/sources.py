import audioop

import numpy as np
import pysndfile

from .dtmf import DTMF_MAP
from .rtp import RTPSource
from .packet import pack_rtpevent


class AudioFile(RTPSource):
    def __init__(self, filename, timeframe, *, loop=None, future=None):
        audio = pysndfile.PySndfile(filename)
        frames = audio.read_frames(dtype=np.int16)
        self.media = audioop.lin2ulaw(frames.tobytes(), frames.itemsize)

        self._loop = loop
        self._future = future

        self.format = 0
        self.timeframe = timeframe

        self.stopped = False
        self.timestamp = 20
        self.seq = 49709
        self.ssrc = 167411976
        self.marked = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.stopped:
            raise StopIteration()

        chunk = self.media[:self.timeframe]
        self.media = self.media[self.timeframe:]

        result = (self.marked, self.format, self.seq, self.timestamp,
                  self.ssrc, chunk)
        self.timestamp += self.timeframe
        return result

    def stop(self):
        if self._loop and self._future:
            self._future.cancel()
        self.stopped = True


class Tone:
    def __init__(self, frequency, duration, timeframe, *,
                 loop=None, future=None, sample_rate=8000, amplitude=10000):
        sample_times = np.arange(sample_rate * duration) / sample_rate
        wave = amplitude * np.sin(2 * np.pi * frequency * sample_times)
        samples = np.array(wave, dtype=np.int16)
        self.media = audioop.lin2ulaw(samples.tobytes(), 2)

        self._loop = loop
        self._future = future

        self.format = 0
        self.timeframe = timeframe
        self.stopped = False
        self.timestamp = 0
        self.seq = 39227
        self.ssrc = 3491926
        self.marked = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.stopped:
            raise StopIteration()

        chunk = self.media[:self.timeframe]
        self.media = self.media[self.timeframe:]

        result = (self.marked, self.format, self.seq, self.timestamp,
                  self.ssrc, chunk)
        self.timestamp += self.timeframe
        return result

    def stop(self):
        if self._loop and self._future:
            self._future.cancel()
        self.stopped = True


class DTMF:
    def __init__(self, sequence, *, tone_length=None, loop=None, future=None):
        self.sequence = [DTMF_MAP[x] for x in sequence]
        self.tone_length = tone_length or 200

        self.seq_iter = iter(self.sequence)
        self.current = next(self.seq_iter)
        self.cur_length = 0

        self._loop = loop
        self._future = future

        self.format = 101
        self.timeframe = 20
        self.stopped = False
        self.timestamp = 20
        self.seq = 49710
        self.ssrc = 167411978
        self.marked = True

    def __iter__(self):
        return self

    def __next__(self):
        if self.stopped:
            raise StopIteration()

        if self.marked and self.cur_length:
            self.marked = False

        # If we're off the end of the previous dtmf packet, get a new one
        if self.cur_length > self.tone_length:
            self.timestamp += 20  # self.tone_length - 60
            self.cur_length = 0
            self.current = next(self.seq_iter)
            self.marked = True

        # Last three rtpevent messages should be marked as the end of event
        end = bool(self.cur_length + 60 >= self.tone_length)
        event = pack_rtpevent({'event_id': self.current,
                               'end_of_event': end,
                               'reserved': 0,
                               'volume': 10,
                               'duration': self.cur_length * 8})
        self.cur_length += 20
        return (self.marked, self.format, self.seq, self.timestamp,
                self.ssrc, event)

    def stop(self):
        if self._loop and self._future:
            self._future.cancel()
        self.stopped = True