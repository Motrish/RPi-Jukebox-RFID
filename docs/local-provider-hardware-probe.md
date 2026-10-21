# Private LocalProvider playback probe

This optional manual probe exercises the real LocalProvider and MPD session on the
existing Zero W test profile. It does not register a production provider.

The private MPD must already run on `127.0.0.1:6601`, with its music directory at
`~/phoniebox-hardwaretest/mpd-p01/music` and an indexed `lokal.mp3` in that directory.
Spotify and other playback clients must remain stopped throughout the probe.
Use the pinned Python dependencies from this revision in a private virtual environment.

Before running the helper from the repository root, set the private MPD volume to
8 percent with `timeout 5s mpc -h 127.0.0.1 -p 6601 volume 8`. Only continue if that
command succeeds. Run `tools/hardware/local_provider_probe.py` using the environment's
Python, with both `src/jukebox` and `src/jukebox/jukebox` on `PYTHONPATH`.

The helper checks the authorized file before connecting and requires a fresh stopped,
error-free MPD status before changing the queue. It replaces the private test queue
with that one file. The expected audible sequence is two seconds of playback, one
second paused, two seconds resumed, a seek to the beginning, one second of playback,
then stop. Each operation must produce a `CONFIRMED` JSON receipt; a successful run
contains START, PAUSE, RESUME, SEEK and STOP in that order and exits with status zero.

Each operation has its own five-second deadline. On failure or interruption after
START, the helper makes one bounded stop attempt with the same execution lease and
disconnects. A failed or unconfirmed stop does not establish that audio has stopped:
resolve that state before starting Spotify or another player. There is no automatic
retry or reconnection.

Protocol tests cannot establish audio quality or release of the actual MiniAmp.
Record the receipts and listening result on the device. This probe also does not
establish mixed playlists, RFID exclusion, natural-end events, or automatic source
handoff.
