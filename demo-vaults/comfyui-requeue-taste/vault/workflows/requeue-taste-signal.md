---
id: requeue-taste-signal
name: Requeue Taste Signal
app: ComfyUI
description: Demo ComfyUI adapter vault showing requeue patterns as taste signals.
params:
  - name: prompt
    type: string
    required: true
tags: [comfyui, demo, requeue, taste-signal, adapter, r1]
routes:
  - type: adapter
    adapter: comfyui
    wait_for_history: true
    graph:
      "1":
        class_type: CLIPTextEncode
        inputs:
          text: "{prompt}"
      "2":
        class_type: KSampler
        inputs:
          seed: "{seed}"
fallback_order: [adapter, api, ask]
verification:
  type: none
calls: []
depends_on: []
signals:
  captured_events:
    - route_tier: r1
      app: ComfyUI
      kind: queue_requeue
      prompt_id: demo-prompt
      taste_signal: true
---

# Requeue Taste Signal

Demo vault documenting queue replays as taste signals.
