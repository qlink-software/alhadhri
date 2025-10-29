/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const POLL_INTERVAL_MS = 30000;
const SOUND_URI =
    "data:audio/wav;base64,UklGRjQAAABXQVZFZm10IBAAAAABAAEAESsAACJWAAACABAAZGF0YQAAAAAAAACqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq";

class NotoStickyNotifier extends Component {
    setup() {
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.state = useState({ alerts: [] });
        this.interval = null;
        this.audio = new Audio(SOUND_URI);
        this.audio.preload = "auto";

        onMounted(async () => {
            this.busService.addChannel("notification.refresh");
            this.busService.addEventListener("notification", ({ detail }) => {
                for (const [channel] of detail) {
                    if (channel === "notification.refresh") {
                        this._refresh();
                        break;
                    }
                }
            });
            await this._refresh(true);
            this.interval = setInterval(() => this._refresh(), POLL_INTERVAL_MS);
        });

        onWillUnmount(() => {
            if (this.interval) {
                clearInterval(this.interval);
            }
            this.busService.deleteChannel("notification.refresh");
        });
    }

    async _refresh(forceSound = false) {
        try {
            const alerts = await this.orm.call(
                "noto.notification.item",
                "get_due_notifications",
                [],
                { context: { bin_size: true } }
            );
            const previousIds = new Set(this.state.alerts.map((a) => a.id));
            this.state.alerts = alerts;
            const newAlerts = alerts.filter((alert) => !previousIds.has(alert.id));
            if (alerts.length && (forceSound || newAlerts.some((a) => a.need_sound))) {
                this.audio.currentTime = 0;
                await this.audio.play().catch(() => {
                    this.notification.add(_t("Please enable audio playback for Noto alerts."), {
                        type: "warning",
                    });
                });
            }
        } catch (error) {
            console.error("Noto notifier error", error);
        }
    }

    async handleAction(alert, action) {
        try {
            const result = await this.orm.call(
                "noto.notification.item",
                "take_action",
                [alert.id, action]
            );
            if (action === "open" && result) {
                await this.actionService.doAction(result);
            }
            await this._refresh();
        } catch (error) {
            console.error("Noto notifier action error", error);
            const message =
                error && error.message
                    ? error.message
                    : _t("Unable to complete the requested action.");
            this.notification.add(message, { type: "danger" });
        }
    }
}

NotoStickyNotifier.template = "notification.StickyNotifier";

registry.category("main_components").add("notoStickyNotifier", {
    Component: NotoStickyNotifier,
});
