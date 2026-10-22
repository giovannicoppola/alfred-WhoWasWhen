"""Voice-over with Kokoro, a local text-to-speech model (Apache 2.0): one WAV per line plus all
lines joined with pauses. Runs on this machine; nothing is sent anywhere.
Needs a Python with `pip install kokoro soundfile` and espeak-ng (`brew install espeak-ng`).
Usage: python narrate.py <lines.txt> <out dir> [--voice af_heart] [--speed 1.0]
The language comes from the voice: a…/b… English (American/British), e… Spanish.
"""
import argparse
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

RATE = 24000

parser = argparse.ArgumentParser()
parser.add_argument('lines', type=Path)
parser.add_argument('out', type=Path)
parser.add_argument('--voice', default='af_heart')
parser.add_argument('--speed', type=float, default=1.0)
parser.add_argument('--pause', type=float, default=0.7, help='seconds between lines in all.wav')
args = parser.parse_args()

lines = [l.strip() for l in args.lines.read_text().splitlines() if l.strip() and not l.startswith('#')]
pipeline = KPipeline(lang_code=args.voice[0], repo_id='hexgrad/Kokoro-82M')
args.out.mkdir(parents=True, exist_ok=True)
gap = np.zeros(int(RATE * args.pause), dtype=np.float32)
joined = []
for n, text in enumerate(lines, 1):
    audio = np.concatenate([np.asarray(chunk.audio) for chunk in pipeline(text, voice=args.voice, speed=args.speed)])
    sf.write(args.out / f'line-{n:02d}.wav', audio, RATE)
    joined += [audio, gap]
    print(f'{n:02d} {len(audio) / RATE:4.1f}s  {text}')
sf.write(args.out / 'all.wav', np.concatenate(joined[:-1]), RATE)
