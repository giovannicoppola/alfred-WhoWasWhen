"""Turns the simulator's film into a steady 30 fps screen.mp4 on the film's true timeline.

simctl writes a frame only when the screen changes, and its B-frames carry display times that
run ahead of their decode times. Once those disagree often enough, ffmpeg stops trusting the
display times and times every frame by its decode time instead, which ran 8 s behind on a test
recording, so anything decoded from the start (the fps filter, trim) put screens seconds early.
This reads each frame's real display time with ffprobe, decodes the frames in order, and holds
each one until the next is due.

Usage: python3 retime.py <recording dir>   (reads film.mp4, writes screen.mp4)
"""
import subprocess
import sys
from pathlib import Path

FPS = 30
W, H = 684, 1488  # the size compose.mjs shows it at (even, for the encoder)

rec = Path(sys.argv[1])
film = rec / 'film.mp4'
probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'frame=pts_time',
                        '-of', 'csv=p=0', film], check=True, capture_output=True, text=True).stdout
times = [float(line.strip(',')) for line in probe.split() if line.strip(',')]

decode = subprocess.Popen(['ffmpeg', '-v', 'fatal', '-i', film, '-fps_mode', 'passthrough', '-vf', f'scale={W}:{H}:flags=lanczos',
                           '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-'], stdout=subprocess.PIPE)
encode = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-s', f'{W}x{H}', '-r', str(FPS),
                           '-i', '-', '-c:v', 'libx264', '-preset', 'fast', '-crf', '14', '-pix_fmt', 'yuv420p', rec / 'screen.mp4'],
                          stdin=subprocess.PIPE)
size = W * H * 3 // 2
current, written, index = None, 0, 0
for start in times:
    frame = decode.stdout.read(size)
    if len(frame) < size:
        break
    # Hold the previous frame until this one is due, then take over.
    while current is not None and written / FPS < start:
        encode.stdin.write(current)
        written += 1
    current, index = frame, index + 1
if current is not None:
    encode.stdin.write(current)
    written += 1
encode.stdin.close()
encode.wait()
decode.wait()
if index != len(times):
    sys.exit(f'decoded {index} frames but ffprobe listed {len(times)}')
print(f'{index} frames over {times[-1]:.1f}s -> {written} frames at {FPS} fps in screen.mp4')
