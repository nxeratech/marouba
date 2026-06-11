from __future__ import absolute_import, print_function

import logging
import os
import time

from ableton.v2.control_surface import ControlSurface

from .maroubaosc import OSC_LISTEN_PORT, OSC_RESPONSE_PORT, MaroubaOscServer


logger = logging.getLogger("marouba-ableton")


class Manager(ControlSurface):
    """Marouba's Ableton Remote Script bootstrap.

    This intentionally mirrors AbletonOSC's no-thread tick loop. Ableton's
    embedded Python environment can be unhappy with background threads, so the
    OSC server is drained from Live's scheduled control-surface callback.
    """

    def __init__(self, c_instance):
        ControlSurface.__init__(self, c_instance)
        self._log_handler = None
        self._osc_server = None
        self._parameter_listeners = []
        self._last_parameter_snapshot = None
        self._transport_snapshot = {}
        self._midi_events = []
        self._clip_note_listeners = []
        self._clip_note_snapshots = {}
        self._clip_note_meta = {}
        self._clip_note_sequence = 0
        self._start_logging()
        try:
            self._osc_server = MaroubaOscServer()
            self._install_handlers()
            self._install_lom_listeners()
            self.schedule_message(1, self._tick)
            self.show_message(
                "MaroubaAbleton: Listening for OSC on port %d" % OSC_LISTEN_PORT
            )
            logger.info("MaroubaAbleton loaded cleanly with MIDI capture enabled")
        except Exception as error:
            logger.exception("MaroubaAbleton failed to start")
            self.show_message("MaroubaAbleton failed to start: %s" % error)

    def _start_logging(self):
        module_path = os.path.dirname(os.path.realpath(__file__))
        log_dir = os.path.join(module_path, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_path = os.path.join(log_dir, "marouba-ableton.log")
        self._log_handler = logging.FileHandler(log_path)
        self._log_handler.setLevel(logging.INFO)
        self._log_handler.setFormatter(
            logging.Formatter("(%(asctime)s) [%(levelname)s] %(message)s")
        )
        logger.setLevel(logging.INFO)
        logger.addHandler(self._log_handler)

    def _install_handlers(self):
        self._osc_server.add_handler("/marouba/health", self._health)
        self._osc_server.add_handler(
            "/marouba/parameter/selected", self._selected_parameter
        )
        self._osc_server.add_handler("/marouba/transport/snapshot", self._transport)
        self._osc_server.add_handler("/marouba/midi/drain", self._midi_drain)
        self._osc_server.add_handler("/live/test", self._test)
        self._osc_server.add_handler("/live/application/get/version", self._version)

    def _install_lom_listeners(self):
        song = self._song()
        self._transport_snapshot = self._read_transport_snapshot()
        self._add_listener(song, "is_playing", self._on_transport_changed)
        self._add_listener(song, "record_mode", self._on_transport_changed)
        self._add_listener(song, "session_record", self._on_transport_changed)
        self._add_listener(song, "tempo", self._on_transport_changed)
        view = getattr(song, "view", None)
        if view is not None:
            self._add_listener(view, "selected_track", self._on_selection_changed)
            self._add_listener(view, "selected_device", self._on_selection_changed)
            self._add_listener(view, "selected_parameter", self._on_selected_parameter_changed)
        self._refresh_parameter_listeners()
        self._refresh_clip_note_listeners()

    def _add_listener(self, owner, name, callback):
        add_name = "add_%s_listener" % name
        has_name = "%s_has_listener" % name
        try:
            add = getattr(owner, add_name, None)
            has = getattr(owner, has_name, None)
            if add is None:
                return
            if has is not None and has(callback):
                return
            add(callback)
            logger.info("LOM listener added: %s.%s", owner.__class__.__name__, name)
        except Exception:
            logger.exception("Failed adding LOM listener: %s", name)

    def _remove_parameter_listeners(self):
        for parameter, callback in list(self._parameter_listeners):
            try:
                if parameter.value_has_listener(callback):
                    parameter.remove_value_listener(callback)
            except Exception:
                logger.exception("Failed removing parameter listener")
        self._parameter_listeners = []

    def _refresh_parameter_listeners(self):
        self._remove_parameter_listeners()
        device = self._selected_device()
        if device is None:
            return
        for parameter in list(getattr(device, "parameters", []) or []):
            try:
                callback = self._make_parameter_listener(parameter)
                if not parameter.value_has_listener(callback):
                    parameter.add_value_listener(callback)
                self._parameter_listeners.append((parameter, callback))
            except Exception:
                logger.exception("Failed listening to parameter: %s", self._safe_name(parameter))

    def _make_parameter_listener(self, parameter):
        def _listener():
            self._last_parameter_snapshot = self._parameter_snapshot(parameter)
            logger.info(
                "Parameter changed: %s=%s",
                self._last_parameter_snapshot[3],
                self._last_parameter_snapshot[4],
            )

        return _listener

    def _on_transport_changed(self):
        self._transport_snapshot = self._read_transport_snapshot()

    def _on_selection_changed(self):
        self._refresh_parameter_listeners()
        self._refresh_clip_note_listeners()

    def _on_selected_parameter_changed(self):
        parameter = self._selected_parameter_object()
        if parameter is not None:
            self._last_parameter_snapshot = self._parameter_snapshot(parameter)

    def _health(self, _params):
        return ("ok", "marouba-ableton", "midi")

    def _selected_parameter(self, _params):
        parameter = self._selected_parameter_object()
        if parameter is not None:
            return ("ok",) + self._parameter_snapshot(parameter)
        if self._last_parameter_snapshot is not None:
            return ("ok",) + self._last_parameter_snapshot
        return ("error", "selected parameter unavailable")

    def _transport(self, _params):
        snapshot = self._read_transport_snapshot()
        return (
            "ok",
            int(snapshot.get("is_playing", 0)),
            int(snapshot.get("record_mode", 0)),
            int(snapshot.get("session_record", 0)),
            str(snapshot.get("tempo", "")),
        )

    def _midi_drain(self, _params):
        events = self._midi_events
        self._midi_events = []
        response = ["ok", len(events)]
        for event in events:
            response.extend(
                [
                    event["kind"],
                    event["channel"],
                    event["pitch"],
                    event["velocity"],
                    event["timestamp_ms"],
                    event.get("start_time", ""),
                    event.get("duration", ""),
                    event.get("tempo", ""),
                    event.get("note_id", ""),
                    event.get("source", "lom_clip_notes"),
                ]
            )
        return tuple(response)

    def receive_midi(self, midi_bytes):
        # Control-surface MIDI input is intentionally not Marouba's primary
        # capture path. It only fires when users manually route MIDI to this
        # script, which violates zero setup. Trusted note capture comes from
        # Clip.notes LOM snapshots after notes are committed to a clip.
        try:
            return super(Manager, self).receive_midi(midi_bytes)
        except AttributeError:
            return None

    def _test(self, _params):
        self.show_message("MaroubaAbleton: OSC OK")
        return ("ok",)

    def _version(self, _params):
        app = self.application()
        return (
            app.get_major_version(),
            app.get_minor_version(),
            app.get_bugfix_version(),
        )

    def _song(self):
        song = getattr(self, "song", None)
        if callable(song):
            return song()
        return song

    def _selected_track(self):
        try:
            return self._song().view.selected_track
        except Exception:
            return None

    def _selected_device(self):
        try:
            return self._song().view.selected_device
        except Exception:
            track = self._selected_track()
            devices = list(getattr(track, "devices", []) or []) if track is not None else []
            return devices[0] if devices else None

    def _selected_parameter_object(self):
        try:
            parameter = self._song().view.selected_parameter
            if parameter is not None:
                return parameter
        except Exception:
            pass
        return None

    def _remove_clip_note_listeners(self):
        for clip, callback in list(self._clip_note_listeners):
            try:
                if clip is not None and clip.notes_has_listener(callback):
                    clip.remove_notes_listener(callback)
            except Exception:
                logger.exception("Failed removing Clip.notes listener")
        self._clip_note_listeners = []
        self._clip_note_snapshots = {}
        self._clip_note_meta = {}

    def _refresh_clip_note_listeners(self):
        self._remove_clip_note_listeners()
        for clip in self._candidate_midi_clips():
            self._add_clip_note_listener(clip, baseline_existing=True)

    def _sync_clip_note_listeners(self):
        known = set(self._clip_key(clip) for clip, _callback in self._clip_note_listeners)
        for clip in self._candidate_midi_clips():
            clip_key = self._clip_key(clip)
            if clip_key not in known:
                self._add_clip_note_listener(clip, baseline_existing=False)

    def _add_clip_note_listener(self, clip, baseline_existing):
        try:
            if clip is None or not self._clip_is_midi(clip):
                return
            clip_key = self._clip_key(clip)
            self._clip_note_snapshots[clip_key] = self._clip_note_snapshot(clip) if baseline_existing else {}
            self._clip_note_meta[clip_key] = self._clip_meta(clip)
            callback = self._make_clip_notes_listener(clip, clip_key)
            if not clip.notes_has_listener(callback):
                clip.add_notes_listener(callback)
            self._clip_note_listeners.append((clip, callback))
            logger.info("LOM listener added: Clip.notes %s", self._clip_note_meta[clip_key].get("name", ""))
            if not baseline_existing:
                self._on_clip_notes_changed(clip, clip_key)
        except Exception:
            logger.exception("Failed adding Clip.notes listener")

    def _make_clip_notes_listener(self, clip, clip_key):
        def _listener():
            self._on_clip_notes_changed(clip, clip_key)
        return _listener

    def _on_clip_notes_changed(self, clip, clip_key):
        try:
            previous = self._clip_note_snapshots.get(clip_key, {})
            current = self._clip_note_snapshot(clip)
            meta = self._clip_meta(clip)
            self._clip_note_meta[clip_key] = meta
            tempo = self._current_tempo()
            for note_key, note in current.items():
                if note_key in previous:
                    continue
                self._queue_clip_note_events(note, meta, tempo)
            self._clip_note_snapshots[clip_key] = current
        except Exception:
            logger.exception("Failed processing Clip.notes change")

    def _queue_clip_note_events(self, note, meta, tempo):
        self._clip_note_sequence += 1
        note_id = str(note.get("note_id") or self._clip_note_sequence)
        pitch = int(note.get("pitch", 0))
        velocity = int(note.get("velocity", 0))
        start_time = float(note.get("start_time", 0.0))
        duration = float(note.get("duration", 0.0))
        start_ms = int(round(start_time * 60000.0 / tempo)) if tempo > 0 else 0
        duration_ms = int(round(duration * 60000.0 / tempo)) if tempo > 0 else 0
        base = {
            "channel": 1,
            "pitch": pitch,
            "velocity": velocity,
            "start_time": "%.12f" % start_time,
            "duration": "%.12f" % duration,
            "tempo": "%.6f" % tempo,
            "note_id": note_id,
            "source": "lom_clip_notes",
            "clip_name": meta.get("name", ""),
            "track_name": meta.get("track", ""),
        }
        on_event = dict(base)
        on_event.update({"kind": "note_on", "timestamp_ms": start_ms})
        off_event = dict(base)
        off_event.update({"kind": "note_off", "timestamp_ms": start_ms + duration_ms, "velocity": 0})
        self._midi_events.append(on_event)
        self._midi_events.append(off_event)
        self._midi_events.sort(key=lambda event: int(event.get("timestamp_ms", 0)))
        if len(self._midi_events) > 4096:
            self._midi_events = self._midi_events[-4096:]
        logger.info(
            "Clip note captured: pitch=%s velocity=%s start=%.6f duration=%.6f tempo=%.3f",
            pitch,
            velocity,
            start_time,
            duration,
            tempo,
        )

    def _candidate_midi_clips(self):
        candidates = []
        song = self._song()
        view = getattr(song, "view", None)
        for clip in (
            getattr(view, "detail_clip", None) if view is not None else None,
            getattr(view, "highlighted_clip_slot", None).clip if view is not None and getattr(view, "highlighted_clip_slot", None) is not None and getattr(view, "highlighted_clip_slot", None).has_clip else None,
        ):
            self._append_unique_clip(candidates, clip)
        for track in list(getattr(song, "tracks", []) or []):
            try:
                if not bool(getattr(track, "arm", False)) and track != self._selected_track():
                    continue
            except Exception:
                pass
            for slot in list(getattr(track, "clip_slots", []) or []):
                try:
                    if slot.has_clip:
                        self._append_unique_clip(candidates, slot.clip)
                except Exception:
                    continue
        return candidates

    def _append_unique_clip(self, candidates, clip):
        if clip is None:
            return
        key = self._clip_key(clip)
        if key not in [self._clip_key(item) for item in candidates]:
            candidates.append(clip)

    def _clip_key(self, clip):
        try:
            return str(clip._live_ptr)
        except Exception:
            return str(id(clip))

    def _clip_is_midi(self, clip):
        try:
            return bool(getattr(clip, "is_midi_clip", False))
        except Exception:
            return False

    def _clip_meta(self, clip):
        track_name = ""
        try:
            for track in list(getattr(self._song(), "tracks", []) or []):
                for slot in list(getattr(track, "clip_slots", []) or []):
                    if getattr(slot, "has_clip", False) and slot.clip == clip:
                        track_name = self._safe_name(track)
                        raise StopIteration
        except StopIteration:
            pass
        except Exception:
            pass
        return {"name": self._safe_name(clip), "track": track_name}

    def _clip_note_snapshot(self, clip):
        notes = self._get_clip_notes(clip)
        snapshot = {}
        for note in notes:
            parsed = self._parse_clip_note(note)
            if parsed is None:
                continue
            key = parsed.get("note_id") or "%s:%.9f:%.9f:%s:%s" % (
                parsed.get("pitch"),
                parsed.get("start_time"),
                parsed.get("duration"),
                parsed.get("velocity"),
                parsed.get("mute", 0),
            )
            snapshot[str(key)] = parsed
        return snapshot

    def _get_clip_notes(self, clip):
        if hasattr(clip, "get_all_notes_extended"):
            return list(clip.get_all_notes_extended())
        if hasattr(clip, "get_notes_extended"):
            return list(clip.get_notes_extended(0, 0, 128, 4096))
        if hasattr(clip, "get_notes"):
            return list(clip.get_notes(0, 0, 128, 4096))
        return []

    def _parse_clip_note(self, note):
        try:
            if hasattr(note, "pitch"):
                return {
                    "note_id": getattr(note, "note_id", None),
                    "pitch": int(note.pitch),
                    "start_time": float(note.start_time),
                    "duration": float(note.duration),
                    "velocity": int(note.velocity),
                    "mute": int(getattr(note, "mute", 0)),
                }
            return {
                "note_id": note.get("note_id"),
                "pitch": int(note.get("pitch")),
                "start_time": float(note.get("start_time")),
                "duration": float(note.get("duration")),
                "velocity": int(note.get("velocity")),
                "mute": int(note.get("mute", 0)),
            }
        except Exception:
            try:
                return {
                    "note_id": None,
                    "pitch": int(note[0]),
                    "start_time": float(note[1]),
                    "duration": float(note[2]),
                    "velocity": int(note[3]),
                    "mute": int(note[4]) if len(note) > 4 else 0,
                }
            except Exception:
                logger.exception("Failed parsing clip note: %s", note)
                return None

    def _current_tempo(self):
        try:
            return float(self._song().tempo)
        except Exception:
            return 120.0

    def _parameter_snapshot(self, parameter):
        track = self._selected_track()
        device = self._device_for_parameter(parameter) or self._selected_device()
        raw_value = self._parameter_value(parameter)
        normalized = self._normalized_parameter_value(parameter, raw_value)
        display = self._display_parameter_value(parameter, raw_value)
        track_name = self._safe_name(track)
        device_name = self._safe_name(device)
        param_name = self._safe_name(parameter)
        target = "track:%s/device:%s/parameter:%s" % (
            track_name,
            device_name,
            param_name,
        )
        return (
            track_name,
            device_name,
            param_name,
            display,
            "%.12f" % normalized,
            target,
        )

    def _device_for_parameter(self, parameter):
        track = self._selected_track()
        for device in list(getattr(track, "devices", []) or []) if track is not None else []:
            try:
                if parameter in list(getattr(device, "parameters", []) or []):
                    return device
            except Exception:
                continue
        return None

    def _parameter_value(self, parameter):
        try:
            return float(parameter.value)
        except Exception:
            return 0.0

    def _normalized_parameter_value(self, parameter, value):
        try:
            minimum = float(parameter.min)
            maximum = float(parameter.max)
            if abs(maximum - minimum) > 0.0000001:
                normalized = (float(value) - minimum) / (maximum - minimum)
            else:
                normalized = float(value)
            return max(0.0, min(1.0, normalized))
        except Exception:
            return max(0.0, min(1.0, float(value)))

    def _display_parameter_value(self, parameter, value):
        try:
            return str(parameter.str_for_value(value))
        except Exception:
            try:
                return str(parameter)
            except Exception:
                return str(value)

    def _safe_name(self, obj):
        if obj is None:
            return ""
        try:
            return str(obj.name)
        except Exception:
            return ""

    def _read_transport_snapshot(self):
        song = self._song()
        snapshot = {}
        for name in ("is_playing", "record_mode", "session_record", "tempo"):
            try:
                snapshot[name] = getattr(song, name)
            except Exception:
                snapshot[name] = 0
        return snapshot

    def _tick(self):
        self._sync_clip_note_listeners()
        if self._osc_server is not None:
            self._osc_server.process()
        self.schedule_message(1, self._tick)

    def disconnect(self):
        logger.info("MaroubaAbleton disconnecting")
        self._remove_parameter_listeners()
        self._remove_clip_note_listeners()
        if self._osc_server is not None:
            self._osc_server.shutdown()
        if self._log_handler is not None:
            logger.removeHandler(self._log_handler)
            self._log_handler.close()
        super(Manager, self).disconnect()
