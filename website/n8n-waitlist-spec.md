# Marouba Waitlist n8n Spec

Target webhook:

`https://webhook.nxeratech.ie/marouba-waitlist`

## Flow

1. Webhook Trigger
   - Method: `POST`
   - Path: `/marouba-waitlist`
   - Expected body:
     - `name`
     - `email`
     - `primary_app`
     - `source`

2. Normalize Submission
   - Trim whitespace from `name`, `email`, and `primary_app`.
   - Lowercase `email`.
   - Add `submitted_at` timestamp.
   - Add `page`: `marouba.app`.

3. Save to Google Sheet
   - Spreadsheet: `Marouba Waitlist`
   - Sheet: `Waitlist`
   - Columns:
     - `submitted_at`
     - `name`
     - `email`
     - `primary_app`
     - `source`
     - `page`

4. Post to Discord
   - Channel: `#marouba-waitlist`
   - Message:

```text
New Marouba waitlist signup
Name: {{name}}
Email: {{email}}
App: {{primary_app}}
Source: {{source}}
```

5. Respond to Browser
   - Status: `200`
   - Body:

```json
{
  "ok": true
}
```

## Notes

Use the same pattern as the Graft waitlist: webhook trigger, light normalization, Google Sheet append, Discord notification, then immediate JSON response. Keep the browser response fast and do not block on optional enrichment.
