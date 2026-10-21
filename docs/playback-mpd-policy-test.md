# Real MPD policy acceptance test

Run the test on Linux with MPD 0.24.x installed:

```sh
cd test/playback_session
python3 -m unittest -v test_mpd_policy_linux.MpdPolicyAcceptance
```

On slow devices such as the Raspberry Pi Zero W, MPD binary startup and solo
`--version` load can take 9 seconds or more. Raise the internal wait limits
without changing the default (3.0 seconds) by exporting an override first:

```sh
export MPD_POLICY_TEST_TIMEOUT=30
```

The fixture copies the staged policy to private temporary paths, selects a
currently free loopback port, and adds a null audio output. It creates a short
database bootstrap MPD process so the fixture track is indexed, stops that
process, then starts a second process using the policy under test. The second
process must allow anonymous reads and reject anonymous and wrong-password
writes. The configured owner must be able to add the fixture and control
playback. Both children are owned by the test and always stopped and reaped.
The test confirms each child PID owns the listener before sending policy
commands, and checks the indexed fixture through the policy owner's read grant.

The portable version-banner regression can run without MPD or Linux:

```sh
cd test/playback_session
python3 -m unittest -v test_mpd_policy_linux.MpdVersionParser
```

The test skips outside Linux or without MPD 0.24.x. It checks this example's
behavior in an isolated process; it does not inspect a device's active MPD
configuration, other listeners, or production service state.
