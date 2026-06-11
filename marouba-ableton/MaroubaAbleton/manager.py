from __future__ import absolute_import, print_function

import json
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
        self._osc_server.add_handler("/marouba/execute", self._execute)
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
        return ("ok", "marouba-ableton", "midi", "execute", "execute-v3", "capture-13.5")

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


    def _execute(self, params):
        try:
            action = str(params[0]) if len(params) > 0 else ""
            payload = {}
            if len(params) > 1 and params[1]:
                payload = json.loads(params[1])
            result = self._execute_action(action, payload)
            return ("ok", json.dumps(result, sort_keys=True))
        except Exception as error:
            logger.exception("Ableton LOM execute failed")
            return ("error", str(error))

    def _execute_action(self, action, payload):
        action = (action or payload.get("action") or "").strip()
        if action in ("set_parameter", "parameter.set", "set_param", "ableton_lom"):
            return self._execute_set_parameter(payload)
        if action in ("play_note", "midi.play_note", "ableton_midi"):
            return self._execute_play_note(payload)
        if action in ("transport", "set_transport", "transport.set"):
            return self._execute_transport(payload)
        if action in ("set_send", "send.set"):
            return self._execute_set_send(payload)
        if action in ("automation_arm", "automation.set"):
            return self._execute_automation(payload)
        if action in ("arrangement", "arrangement_op"):
            return self._execute_arrangement(payload)
        if action in ("snapshot_devices", "devices.snapshot"):
            return self._execute_device_snapshot(payload)
        if action in ("snapshot_device", "device.snapshot"):
            return self._execute_single_device_snapshot(payload)
        if action in ("load_device", "load_instrument", "load_preset", "browser.load", "ableton_browser"):
            return self._execute_load_device(payload)
        raise RuntimeError("unsupported Ableton action: %s" % action)

    def _route_payload(self, payload):
        route = payload.get("route")
        if isinstance(route, dict):
            merged = dict(route)
            for key, value in payload.items():
                if key != "route" and key not in merged:
                    merged[key] = value
            return merged
        return payload

    def _execute_set_parameter(self, payload):
        payload = self._route_payload(payload)
        try:
            parameter = self._resolve_parameter(payload)
        except Exception as error:
            send_name = self._send_name_from_parameter_payload(payload)
            if send_name is None:
                raise
            send_payload = dict(payload)
            send_payload["send"] = send_name
            result = self._execute_set_send(send_payload)
            result["action"] = "set_parameter"
            result["mapped_to"] = "send"
            result["fallback_reason"] = str(error)
            return result
        raw_value = payload.get("value")
        if isinstance(raw_value, dict):
            raw_value = raw_value.get("normalized", raw_value.get("raw"))
        normalized = self._float_or_none(raw_value)
        if normalized is None:
            normalized = self._float_or_none(payload.get("normalized"))
        if normalized is None:
            raise RuntimeError("set_parameter route missing numeric value")
        minimum = self._float_or_default(getattr(parameter, "min", 0.0), 0.0)
        maximum = self._float_or_default(getattr(parameter, "max", 1.0), 1.0)
        value = minimum + max(0.0, min(1.0, normalized)) * (maximum - minimum)
        parameter.value = value
        snapshot = self._parameter_snapshot(parameter)
        return {
            "action": "set_parameter",
            "route": "api",
            "track": snapshot[0],
            "device": snapshot[1],
            "parameter": snapshot[2],
            "display_value": snapshot[3],
            "normalized_value": snapshot[4],
            "target": snapshot[5],
        }

    def _execute_load_device(self, payload):
        payload = self._route_payload(payload)
        device_name = str(
            payload.get("name")
            or payload.get("device")
            or payload.get("device_name")
            or payload.get("preset_name")
            or ""
        ).strip()
        if not device_name:
            raise RuntimeError("load_device route missing device name")
        track = self._resolve_track(payload)
        target_index = payload.get("target_index", payload.get("device_index", 0))
        try:
            target_index = int(target_index)
        except Exception:
            target_index = 0
        devices_before = list(getattr(track, "devices", []) or [])
        displaced_device = None
        if 0 <= target_index < len(devices_before):
            displaced_device = self._safe_name(devices_before[target_index])
        replace = bool(payload.get("replace") or payload.get("replacement") or payload.get("displaced_device"))
        if replace and displaced_device and displaced_device.lower() != device_name.lower():
            if hasattr(track, "delete_device"):
                track.delete_device(target_index)
            else:
                raise RuntimeError("Track.delete_device unavailable for replacement load")
        if not hasattr(track, "insert_device"):
            raise RuntimeError("Track.insert_device unavailable in this Live version")
        track.insert_device(device_name, target_index)
        device = self._resolve_device(
            dict(payload, device=device_name, device_name=device_name),
            track,
            strict=True,
        )
        applied = self._apply_device_parameter_snapshot(device, payload.get("parameter_snapshot"))
        track_index, track_id = self._track_identity(track)
        return {
            "action": "load_device",
            "route": "api",
            "track": self._safe_name(track),
            "track_name": self._safe_name(track),
            "track_index": track_index,
            "track_id": track_id,
            "device": self._safe_name(device),
            "target_index": target_index,
            "replace": replace,
            "displaced_device": displaced_device,
            "parameters_applied": applied,
            "target": "track:%s/device:%s" % (self._safe_name(track), self._safe_name(device)),
        }

    def _execute_device_snapshot(self, payload):
        payload = self._route_payload(payload)
        track = self._resolve_track(payload)
        track_index, track_id = self._track_identity(track)
        include_parameters = bool(payload.get("include_parameters") or payload.get("full"))
        devices = []
        for index, device in enumerate(list(getattr(track, "devices", []) or [])):
            parameters = []
            if include_parameters:
                parameters = self._device_parameter_snapshot(device)
            device_index, device_id = self._device_identity(device, index)
            item = {
                "index": index,
                "id": device_id,
                "name": self._safe_name(device),
                "class_name": device.__class__.__name__,
            }
            if include_parameters:
                item["parameters"] = parameters
            devices.append(item)
        return {
            "action": "snapshot_devices",
            "route": "api",
            "source": "ableton_lom",
            "compact": not include_parameters,
            "track": self._safe_name(track),
            "track_name": self._safe_name(track),
            "track_index": track_index,
            "track_id": track_id,
            "devices": devices,
        }

    def _execute_single_device_snapshot(self, payload):
        payload = self._route_payload(payload)
        track = self._resolve_track(payload)
        devices = list(getattr(track, "devices", []) or [])
        device_index = payload.get("device_index", payload.get("target_index", payload.get("index", None)))
        device = None
        if device_index is not None:
            try:
                device = devices[int(device_index)]
            except Exception:
                device = None
        if device is None:
            device = self._resolve_device(payload, track, strict=True)
            try:
                device_index = devices.index(device)
            except Exception:
                device_index = -1
        track_index, track_id = self._track_identity(track)
        device_index, device_id = self._device_identity(device, device_index)
        return {
            "action": "snapshot_device",
            "route": "api",
            "source": "ableton_lom",
            "track": self._safe_name(track),
            "track_name": self._safe_name(track),
            "track_index": track_index,
            "track_id": track_id,
            "device": {
                "index": device_index,
                "id": device_id,
                "name": self._safe_name(device),
                "class_name": device.__class__.__name__,
                "parameters": self._device_parameter_snapshot(device),
            },
        }

    def _device_parameter_snapshot(self, device):
        parameters = []
        for parameter in list(getattr(device, "parameters", []) or []):
            try:
                minimum = self._float_or_default(getattr(parameter, "min", 0.0), 0.0)
                maximum = self._float_or_default(getattr(parameter, "max", 1.0), 1.0)
                value = self._float_or_default(getattr(parameter, "value", minimum), minimum)
                normalized = 0.0 if maximum == minimum else (value - minimum) / (maximum - minimum)
                parameters.append({
                    "name": self._safe_name(parameter),
                    "display_value": str(parameter),
                    "normalized": max(0.0, min(1.0, normalized)),
                })
            except Exception:
                continue
        return parameters

    def _execute_play_note(self, payload):
        payload = self._route_payload(payload)
        clip = self._resolve_midi_clip_for_write()
        pitch = int(payload.get("pitch", 60))
        velocity = int(payload.get("velocity", 100))
        start_time = self._float_or_default(payload.get("start_time"), 0.0)
        duration = self._float_or_default(payload.get("duration"), None)
        if duration is None:
            duration_ms = self._float_or_default(payload.get("duration_ms"), 250.0)
            tempo = self._float_or_default(payload.get("tempo"), self._current_tempo())
            duration = duration_ms * tempo / 60000.0 if tempo > 0 else 0.5
        note = {
            "pitch": pitch,
            "start_time": start_time,
            "duration": max(0.03125, duration),
            "velocity": velocity,
            "mute": False,
        }
        self._add_note_to_clip(clip, note)
        return {
            "action": "play_note",
            "route": "api",
            "pitch": pitch,
            "velocity": velocity,
            "start_time": start_time,
            "duration": note["duration"],
            "clip": self._safe_name(clip),
        }

    def _execute_transport(self, payload):
        payload = self._route_payload(payload)
        song = self._song()
        command = str(payload.get("command") or payload.get("state") or "").lower()
        if command in ("play", "start"):
            try:
                song.start_playing()
            except Exception:
                song.is_playing = True
        elif command in ("stop",):
            try:
                song.stop_playing()
            except Exception:
                song.is_playing = False
        elif command in ("toggle",):
            song.is_playing = not bool(getattr(song, "is_playing", False))
        if "is_playing" in payload:
            desired = bool(payload.get("is_playing"))
            if desired and not bool(getattr(song, "is_playing", False)):
                song.start_playing()
            if not desired and bool(getattr(song, "is_playing", False)):
                song.stop_playing()
        for field in ("record_mode", "session_record", "arrangement_overdub", "loop"):
            if field in payload and hasattr(song, field):
                setattr(song, field, bool(payload.get(field)))
        if "tempo" in payload:
            song.tempo = float(payload.get("tempo"))
        return dict(self._read_transport_snapshot(), action="transport", route="api")

    def _execute_set_send(self, payload):
        payload = self._route_payload(payload)
        track = self._resolve_track(payload)
        sends = list(getattr(getattr(track, "mixer_device", None), "sends", []) or [])
        if not sends:
            raise RuntimeError("selected track has no sends")
        index = payload.get("send_index", payload.get("send", payload.get("param", 0)))
        if isinstance(index, str):
            stripped = index.strip().upper()
            if stripped and stripped[0].isalpha():
                index = ord(stripped[0]) - ord("A")
        index = int(index)
        if index < 0 or index >= len(sends):
            raise RuntimeError("send index out of range: %s" % index)
        send = sends[index]
        normalized = self._float_or_none(payload.get("value"))
        if normalized is None:
            normalized = self._float_or_none(payload.get("normalized"))
        if normalized is None:
            raise RuntimeError("set_send route missing value")
        minimum = self._float_or_default(getattr(send, "min", 0.0), 0.0)
        maximum = self._float_or_default(getattr(send, "max", 1.0), 1.0)
        send.value = minimum + max(0.0, min(1.0, normalized)) * (maximum - minimum)
        return {
            "action": "set_send",
            "route": "api",
            "track": self._safe_name(track),
            "send_index": index,
            "display_value": self._display_parameter_value(send, send.value),
            "normalized_value": self._normalized_parameter_value(send, send.value),
        }

    def _execute_automation(self, payload):
        payload = self._route_payload(payload)
        song = self._song()
        for field in ("session_automation_record", "arrangement_overdub", "record_mode"):
            if field in payload and hasattr(song, field):
                setattr(song, field, bool(payload.get(field)))
        return {
            "action": "automation_arm",
            "route": "api",
            "session_automation_record": bool(getattr(song, "session_automation_record", False)),
            "arrangement_overdub": bool(getattr(song, "arrangement_overdub", False)),
            "record_mode": bool(getattr(song, "record_mode", False)),
        }

    def _execute_arrangement(self, payload):
        payload = self._route_payload(payload)
        operation = str(payload.get("operation") or payload.get("command") or "").lower()
        if operation in ("set_loop", "loop"):
            song = self._song()
            if "loop_start" in payload:
                song.loop_start = float(payload.get("loop_start"))
            if "loop_length" in payload:
                song.loop_length = float(payload.get("loop_length"))
            if "loop" in payload:
                song.loop = bool(payload.get("loop"))
            return {"action": "arrangement", "operation": "set_loop", "route": "api"}
        raise RuntimeError("arrangement operation not implemented via LOM: %s" % operation)

    def _target_parts(self, payload):
        target = str(payload.get("target") or "")
        parts = {}
        for item in target.split("/"):
            if ":" not in item:
                continue
            key, value = item.split(":", 1)
            parts[key.strip().lower()] = value.strip()
        return parts

    def _resolve_track(self, payload):
        parts = self._target_parts(payload)
        track_id = str(payload.get("track_id") or parts.get("track_id") or "").strip()
        track_name = str(
            payload.get("track")
            or payload.get("track_name")
            or parts.get("track_name")
            or parts.get("track")
            or ""
        ).lower()
        track_index = payload.get("track_index")
        tracks = list(getattr(self._song(), "tracks", []) or [])
        if track_id:
            for index, track in enumerate(tracks):
                if self._track_identity(track, index)[1] == track_id:
                    return track
        if track_index is not None:
            try:
                return tracks[int(track_index)]
            except Exception:
                pass
        if track_name:
            for track in tracks:
                if self._safe_name(track).lower() == track_name:
                    return track
        track = self._selected_track()
        if track is None:
            raise RuntimeError("selected track unavailable")
        return track

    def _track_identity(self, track, known_index=None):
        tracks = list(getattr(self._song(), "tracks", []) or [])
        index = known_index
        if index is None:
            for candidate_index, candidate in enumerate(tracks):
                if candidate == track:
                    index = candidate_index
                    break
        if index is None:
            index = -1
        live_ptr = getattr(track, "_live_ptr", None)
        if live_ptr is not None:
            return index, "lom:%s" % live_ptr
        return index, "track_index:%s" % index

    def _device_identity(self, device, known_index=None):
        index = -1 if known_index is None else known_index
        try:
            index = int(index)
        except Exception:
            index = -1
        live_ptr = getattr(device, "_live_ptr", None)
        if live_ptr is not None:
            return index, "lom:%s" % live_ptr
        return index, "device_index:%s" % index

    def _resolve_device(self, payload, track, strict=None):
        parts = self._target_parts(payload)
        device_name = str(payload.get("device") or payload.get("device_name") or parts.get("device") or "").lower()
        devices = list(getattr(track, "devices", []) or [])
        if device_name:
            for device in devices:
                if self._safe_name(device).lower() == device_name:
                    return device
            if strict is not False:
                raise RuntimeError("device not found on track %s: %s" % (self._safe_name(track), device_name))
        elif strict:
            raise RuntimeError("device target missing for strict route")
        device = self._selected_device()
        if device is not None:
            return device
        if devices:
            return devices[0]
        raise RuntimeError("device unavailable")

    def _resolve_parameter(self, payload):
        parts = self._target_parts(payload)
        track = self._resolve_track(payload)
        device = self._resolve_device(payload, track)
        param_name = str(payload.get("param") or payload.get("parameter") or payload.get("element_name") or parts.get("parameter") or "").lower()
        if param_name:
            for parameter in list(getattr(device, "parameters", []) or []):
                if self._safe_name(parameter).lower() == param_name:
                    return parameter
        parameter = self._selected_parameter_object()
        if parameter is not None:
            return parameter
        raise RuntimeError("parameter unavailable: %s" % param_name)

    def _apply_device_parameter_snapshot(self, device, snapshot):
        if not snapshot:
            return 0
        parameters = list(getattr(device, "parameters", []) or [])
        applied = 0
        for item in snapshot:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("param") or item.get("parameter") or "").strip().lower()
            if not name:
                continue
            parameter = None
            for candidate in parameters:
                if self._safe_name(candidate).lower() == name:
                    parameter = candidate
                    break
            if parameter is None:
                continue
            normalized = self._float_or_none(item.get("normalized"))
            if normalized is None:
                normalized = self._float_or_none(item.get("value"))
            if normalized is None:
                continue
            minimum = self._float_or_default(getattr(parameter, "min", 0.0), 0.0)
            maximum = self._float_or_default(getattr(parameter, "max", 1.0), 1.0)
            parameter.value = minimum + max(0.0, min(1.0, normalized)) * (maximum - minimum)
            applied += 1
        return applied

    def _send_name_from_parameter_payload(self, payload):
        parts = self._target_parts(payload)
        raw_name = str(
            payload.get("param")
            or payload.get("parameter")
            or payload.get("element_name")
            or parts.get("parameter")
            or ""
        ).strip()
        if not raw_name:
            return None
        first = raw_name[0].upper()
        if not first.isalpha():
            return None
        if len(raw_name) == 1 or raw_name[1] in ("-", "_", " ", ":"):
            return first
        return None

    def _resolve_midi_clip_for_write(self):
        for clip in self._candidate_midi_clips():
            if self._clip_is_midi(clip):
                return clip
        track = self._selected_track()
        if track is None:
            raise RuntimeError("no selected track for MIDI note write")
        for slot in list(getattr(track, "clip_slots", []) or []):
            try:
                if not slot.has_clip and hasattr(slot, "create_clip"):
                    slot.create_clip(4.0)
                    return slot.clip
            except Exception:
                continue
        raise RuntimeError("no writable MIDI clip available")

    def _add_note_to_clip(self, clip, note):
        if hasattr(clip, "add_new_notes"):
            errors = []
            candidates = []
            try:
                import Live
                spec_type = Live.Clip.MidiNoteSpecification
                for args in (
                    (),
                    (note["pitch"], note["start_time"], note["duration"], note["velocity"], note["mute"]),
                ):
                    try:
                        spec = spec_type(*args)
                        spec.pitch = note["pitch"]
                        spec.start_time = note["start_time"]
                        spec.duration = note["duration"]
                        spec.velocity = note["velocity"]
                        spec.mute = note["mute"]
                        candidates.append((spec,))
                    except Exception as error:
                        errors.append("MidiNoteSpecification build failed: %s" % error)
            except Exception as error:
                errors.append("Live.Clip.MidiNoteSpecification unavailable: %s" % error)
            candidates.extend([
                [(note["pitch"], note["start_time"], note["duration"], note["velocity"], note["mute"])],
                ((note["pitch"], note["start_time"], note["duration"], note["velocity"], note["mute"]),),
            ])
            for candidate in candidates:
                try:
                    clip.add_new_notes(candidate)
                    return
                except Exception as error:
                    errors.append(str(error))
            raise RuntimeError("add_new_notes failed: %s" % "; ".join(errors[-6:]))
        raise RuntimeError("Clip.add_new_notes unavailable in this Live version")

    def _float_or_none(self, value):
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    def _float_or_default(self, value, default):
        parsed = self._float_or_none(value)
        return default if parsed is None else parsed

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
        track_index, track_id = self._track_identity(track)
        device_name = self._safe_name(device)
        param_name = self._safe_name(parameter)
        target = "track_id:%s/track_index:%s/track_name:%s/device:%s/parameter:%s" % (
            track_id,
            track_index,
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
            track_id,
            str(track_index),
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
