# marouba-ableton

Marouba Ableton Remote Script.

This is the MAP Ableton bridge bootstrap. It deliberately uses Ableton's normal
Remote Script mechanism, the same extension surface used by Push, Akai, Novation,
and AbletonOSC.

Install target:

```text
%USERPROFILE%\Documents\Ableton\User Library\Remote Scripts\MaroubaAbleton
```

After installation, restart Ableton Live and select `MaroubaAbleton` in:

```text
Preferences -> Link / Tempo / MIDI -> Control Surface
```

Ports:

- Listen: UDP `127.0.0.1:11000`
- Reply: UDP `127.0.0.1:11001`

Current goal scope:

- Load cleanly as a Remote Script.
- Provide `/marouba/health` and `/live/test` OSC health replies.
- Keep the existing keyboard-as-MIDI code as a fallback only.

Future bridge goals add the full LOM capture/replay endpoint set.

## Probe reply pattern

The Remote Script replies to the UDP source address that sent the OSC request.
Barry's companion bridge still uses the stable pattern of binding its probe socket
to `127.0.0.1:11001` before sending to `127.0.0.1:11000`, so replies continue
to arrive on the documented response port. Ad-hoc test tools may also use a
one-shot UDP socket: bind/listen on the same socket used to send the request and
read the reply from that socket. Do not send from one socket and wait on a
different unbound socket.
