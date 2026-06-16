/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";

export class LanguageSwitcher extends Component {
    static template = "qlink_backend_theme_alhadhri.LanguageSwitcher";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            installedLanguages: [],
            currentLangCode: user.lang || "en_US",
        });

        onWillStart(async () => {
            try {
                const langs = await this.orm.call("res.lang", "get_installed", []);
                this.state.installedLanguages = langs.map((l) => ({
                    code: l[0],
                    name: l[1],
                }));
            } catch (error) {
                console.error("Failed to load languages:", error);
            }
        });
    }

    async switchLanguage(langCode) {
        if (this.state.currentLangCode === langCode) {
            return;
        }

        try {
            // 1. Permanently update the language field in the database and AWAIT it
            await this.orm.write("res.users", [user.userId], {
                lang: langCode,
            });

            // 2. Safely tell Odoo 18's user service to update runtime context variables and AWAIT it
            if (this.env.services.user?.updateContext) {
                await this.env.services.user.updateContext({ lang: langCode });
            }

            // Update local state reactive token
            this.state.currentLangCode = langCode;

            // 3. Clear running router caches
            this.action.doAction("reload_context");

            // 4. FIX: Use standard URL manipulation to force Odoo to re-read the home routing 
            // page entirely from scratch, recalculating the LTR/RTL HTML body tags correctly.
            window.location.href = window.location.origin + window.location.pathname + window.location.hash;

        } catch (error) {
            console.error("Failed to switch language:", error);
        }
    }
}

patch(NavBar, {
    components: {
        ...NavBar.components,
        LanguageSwitcher,
    },
});