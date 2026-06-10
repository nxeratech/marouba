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
