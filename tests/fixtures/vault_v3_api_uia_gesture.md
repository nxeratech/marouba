---
vault_spec_version: 3
id: v3-api-route
name: V3 API Route
app: Ableton Live
description: V3 workflow with api/uia/gesture routes.
params: []
tags: [v3, test]
author: nxeratech
created: 2026-06-10
routes: []
fallback_order: [api, uia, gesture, ask]
verification: {"type":"none"}
---

# V3 API Route

## Steps

### Step 001 - Set Auto Filter cutoff

```yaml
id: step_001
type: set_parameter
intent: Set Auto Filter cutoff to 3.42 kHz.
signals:
  dwell_before_ms: 1200
  revisit_of: null
  undo_cluster: null
routes:
  - type: api
    api: ableton_lom
    target: track:1/device:Auto Filter
    device: Auto Filter
    param: Frequency
    value: 0.73
    display_value: 3.42 kHz
  - type: uia
    element_name: Frequency
    action: set_value
    value: 0.73
  - type: gesture
    events:
      - kind: mousedown
        normalized_x: 0.5
        normalized_y: 0.5
```