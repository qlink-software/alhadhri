# Noto Notification Center

## Highlights
- Covers sessions, cases, consultations, reports, payments, and any custom record through the linking fields.
- Fixed orange banner across the UI with three actions: view record, snooze 15 minutes, and action taken.
- Embedded tone that behaves like WhatsApp/Messenger desktop sounds.
- Every interface uses explicit `list` views as requested.

## Setup
1. Install the module, then open `Noto Notifications ▸ Notification Register`.
2. Create a record, set the due time, type, and optionally link a target model and ID.
3. Enable “Manual Dismissal” to keep the banner visible until someone clicks a button.

## Customization
- Add new types by extending the selection in `models/notification_item.py`.
- Adjust the refresh cadence via `POLL_INTERVAL_MS` inside `static/src/js/sticky_notifier.js`.
- Swap the embedded tone by updating the `SOUND_URI` constant.
