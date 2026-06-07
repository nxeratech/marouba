---
id: browser-screenshot-page
name: Browser Screenshot Page
app: Browser
app_version: Chrome/Edge latest
author: nxeratech
category: web-automation
description: Capture a screenshot of a browser page through DevTools, headless CLI, or desktop fallbacks.
params:
  - name: url
    type: string
    required: true
  - name: output_path
    type: string
    required: true
  - name: width
    type: integer
    required: true
  - name: height
    type: integer
    required: true
tags: [browser, screenshot, chrome, edge, marketplace-seed]
last_verified: 2026-06-06
created: 2026-06-06
routes:
  - type: api
    endpoint: ws://127.0.0.1:9222/devtools/page/{target_id}
    method: CDP
    payload_template: profiles/browser/payloads/screenshot-page.json
  - type: cli
    command: "chrome --headless --disable-gpu --screenshot={output_path} --window-size={width},{height} {url}"
  - type: uia
    app_window: Google Chrome
    element: Address and search bar
    role: Edit
  - type: shortcut
    keys: [ctrl, l]
  - type: visual
    snapshot: profiles/browser/snapshots/address-bar.png
fallback_order: [api, cli, uia, shortcut, visual, ask]
verification:
  type: file_exists
  path: "{output_path}"
  timeout_seconds: 60
calls: []
depends_on: []
---

# Browser Screenshot Page

Capture a screenshot of a page through DevTools or headless browser fallback.
