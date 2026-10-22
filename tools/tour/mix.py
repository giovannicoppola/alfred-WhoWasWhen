"""Adds the narration to the composed tour: one line per caption, the last over the end card,
each a beat after its caption and never over the line before. Voice only: the app makes no
sound of its own to show.

Usage: python3 mix.py <recording dir> <narration dir> <tour.mp4>   (rewrites the video in place)
Needs numpy, soundfile and ffmpeg.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

LEAD = 0.25
rec, voice, video = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
plan = json.loads((rec / 'plan.json').read_text())
starts = [c['t'] for c in plan['captions']] + [plan['end']]
lines = sorted(voice.glob('line-*.wav'))
rate = sf.info(lines[0]).samplerate
track = np.zeros(int((plan['end'] + 6.0) * rate), np.float32)
free_at = 0.0
for k, (path, start) in enumerate(zip(lines, starts), 1):
    audio, _ = sf.read(path, dtype='float32')
    begin = max(start + LEAD, free_at)
    if begin > start + 1.0:
        print(f'line {k} starts {begin - start:.1f}s after its caption: shorten line {k - 1}')
    i = int(begin * rate)
    track[i:i + len(audio)] += audio[: len(track) - i]
    free_at = begin + len(audio) / rate + 0.2
wav = rec / 'tour-voice.wav'
sf.write(wav, track, rate)
out = video.with_suffix('.voiced.mp4')
# Normalised to -16 LUFS, where phones and browsers play most things; the bare voice sits near -26.
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', video, '-i', wav, '-map', '0:v', '-map', '1:a',
                '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '48000', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '128k',
                '-movflags', '+faststart', '-shortest', out], check=True)
out.replace(video)
print('narrated', video)
