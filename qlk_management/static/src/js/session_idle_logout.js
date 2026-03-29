/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

const IDLE_TIMEOUT_MS = 60 * 60 * 1000;
const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "touchstart", "scroll"];

registry.category("services").add("qlk_session_idle_logout", {
    dependencies: ["notification"],
    start(_env, { notification }) {
        let timeoutId;
        let loggingOut = false;

        // هذا الإجراء يعيد ضبط مؤقت الخمول بعد أي تفاعل من المستخدم.
        const resetIdleTimer = () => {
            if (loggingOut) {
                return;
            }
            browser.clearTimeout(timeoutId);
            timeoutId = browser.setTimeout(async () => {
                loggingOut = true;
                detachListeners();
                try {
                    const response = await rpc("/qlk_management/session/idle_logout", {});
                    notification.add(_t("You have been logged out due to inactivity."), {
                        type: "warning",
                    });
                    browser.setTimeout(() => {
                        browser.location.replace(response?.redirect_url || "/web/login");
                    }, 250);
                } catch {
                    browser.location.replace("/web/login");
                }
            }, IDLE_TIMEOUT_MS);
        };

        const onActivity = () => resetIdleTimer();

        const attachListeners = () => {
            for (const eventName of ACTIVITY_EVENTS) {
                browser.addEventListener(eventName, onActivity, { passive: true });
            }
        };

        const detachListeners = () => {
            for (const eventName of ACTIVITY_EVENTS) {
                browser.removeEventListener(eventName, onActivity);
            }
        };

        attachListeners();
        resetIdleTimer();

        return {
            stop() {
                detachListeners();
                browser.clearTimeout(timeoutId);
            },
        };
    },
});
