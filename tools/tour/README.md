# App tour video

A 52-second narrated tour of the iPhone app, 1080×1920, for the landing page and social posts:
`docs/media/whowaswhen-tour.mp4` and its poster frame `whowaswhen-tour-poster.jpg`. It asks the
app what it is for: who ruled in 1789, the artists of 1888, van Gogh's details, a jump to the
year he was born, the English monarchs as a timeline, Discover, and a quiz question.

```
runner/          a separate Xcode project (XcodeGen) whose UI test drives the installed WhoWasWhen
record.mjs       builds the app, installs it fresh, films the tour                -> build/tour
retime.py        the film on its true timeline, at a steady 30 fps (run by record.mjs)
narrate.py       one Kokoro line per caption, plus the end card
plan.py          which parts of the film to keep, so each scene lasts as long as its line
compose.mjs      captions, phone bezel, touch rings and the landing page's end card
mix.py           the narration, loudness-normalised
```

```sh
cd tools/tour && npm install
export SIM=<simulator udid>                 # an iPhone 16 Pro; record.mjs reinstalls the app on it
export KOKORO_PYTHON=<python with kokoro, soundfile, numpy>
npm run record && npm run voice && npm run plan && npm run video
```

Needs Xcode with XcodeGen, ffmpeg, Chrome (for the captions), Python with Pillow, and a
connection (portraits and summaries come from Wikipedia). The narration runs locally with
[Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) (Apache 2.0), voice `af_heart`.

"On this day" and Discover change with the date and the dice, so every run differs there.

## Why it is built this way

- **A separate runner project**, so `ios/project.yml` never gains a target for a video. Its UI
  test drives WhoWasWhen by bundle id; `TourHost` is only there because XCUITest needs an app of
  its own to attach to.
- **Taps go through one snapshot of the screen** and land by position: a Details sheet over the
  results leaves two buttons with one label, and querying element by element stalls the runner.
- **The film decides the timing, not the log.** `plan.py` keeps every stretch where the screen
  moves and trims the still ones to fit the narration, giving most of the time to each scene's
  final state.
- **`retime.py`** works around the simulator encoder's timestamps, which put screens seconds early
  in anything decoded straight from `film.mp4`.

## Changing it

- Captions and touches are in `runner/TourTests/TourTests.swift`; the words spoken are in
  `narration.txt`, one line per caption, then one for the end card. Write numbers as words
  ("seventeen eighty-nine"), or the voice reads them as amounts.
- If a line is longer than its scene, `mix.py` says which line to shorten.
