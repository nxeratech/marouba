---
id: browser-fill-and-submit-form
name: Browser Fill and Submit Form
app: Browser
app_version: Chrome/Edge latest
author: nxeratech
category: web-automation
description: Fill a browser form and submit it through DevTools, CLI automation, or desktop fallbacks.
params:
  - name: url
    type: string
    required: true
  - name: fields_json
    type: string
    required: true
  - name: submit_selector
    type: string
    required: true
  - name: success_url_fragment
    type: string
    required: true
tags: [browser, form, submit, marketplace-seed]
last_verified: 2026-06-06
created: 2026-06-06
routes:
  - type: api
    endpoint: ws://127.0.0.1:9222/devtools/page/{target_id}
    method: CDP
    payload_template: profiles/browser/payloads/fill-and-submit-form.json
  - type: cli
    command: "python tools/browser_form_submit.py --url {url} --fields {fields_json} --submit {submit_selector}"
  - type: uia
    app_window: Google Chrome
    element: Submit
    role: Button
  - type: shortcut
    keys: [tab, enter]
  - type: visual
    snapshot: profiles/browser/snapshots/submit-button.png
fallback_order: [api, cli, uia, shortcut, visual, ask]
verification:
  type: url_contains
  path: "{success_url_fragment}"
  timeout_seconds: 30
calls: []
depends_on: []
---

# Browser Fill and Submit Form

Fill a web form and submit it through DevTools, CLI automation, or desktop fallbacks.
