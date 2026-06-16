/** @odoo-module **/

import { NavBar } from '@web/webclient/navbar/navbar';
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks"; 
import { onMounted } from "@odoo/owl";
import { UserMenu } from "@web/webclient/user_menu/user_menu";
import { useState } from "@odoo/owl";

patch(NavBar.prototype, { 
    // إعادة تمرير UserMenu حتى لا ينكسر Navbar الأصلي
    UserMenu,

    setup() {
        super.setup();

        this.systrayItems = this.systrayItems.filter(
            (item) => item.Component.name !== UserMenu.name
        );

        // 1. استرجاع الحالة المخزنة أولاً (الافتراضي مغلق true)
        const savedTheme = localStorage.getItem("selected_theme") || "light";
        
        // 2. تطبيق السمة فوراً على مستوى الـ DOM قبل تحميل بقية الواجهة
        document.documentElement.setAttribute("data-bs-theme", savedTheme);

        this.state = useState({
            isCollapsed: true, // القائمة مخفية افتراضياً لتوفير مساحة كاملة
            isDark: savedTheme === "dark", 
        });

        this.menuService = useService("menu");
        
        onMounted(() => {
            this.applySidebarLayout();
            this.applyActiveMenuOnLoad();
            
            // تأكيد إضافي عند التركيب لضمان عدم حدوث Flicker
            document.documentElement.setAttribute("data-bs-theme", this.state.isDark ? "dark" : "light");
            
            // مراقب للنقرات الخارجية لإغلاق السايدبار عند الضغط في أي مكان بالخارج
            document.addEventListener("click", this.onExternalClick.bind(this));
        });
    },

    toggleDarkMode() {
        this.state.isDark = !this.state.isDark;
        const theme = this.state.isDark ? "dark" : "light";
        document.documentElement.setAttribute("data-bs-theme", theme);
        localStorage.setItem("selected_theme", theme);
    },

    getMenuHref(menu) {
        if (!menu) return "#";
        if (menu.childrenTree?.length > 0 && !menu.actionID) {
            return "#";
        }
        const menuId = menu.id;
        const actionId = menu.actionID || menu.action_id || "";
        return `/odoo/action-${actionId}?menu_id=${menuId}`;
    },

    /**
     * إغلاق السايدبار عند النقر في الخارج (منطقة العمل أو الأوراق)
     */
    onExternalClick(ev) {
        const sidebarPanel = document.getElementById('sidebar_panel');
        // التحقق من زر الهمبرغر لمنع التداخل أثناء الضغط عليه
        const toggleBtn = ev.target.closest('.o_modern_sidebar_toggle') || ev.target.closest('.sidebar_handle');
        
        if (!this.state.isCollapsed && sidebarPanel && !sidebarPanel.contains(ev.target) && !toggleBtn) {
            this.state.isCollapsed = true;
            this.applySidebarLayout();
        }
    },

    /**
     * التعديل الجديد: التحكم في ظهور واختفاء السايدبار كاملاً
     */
    applySidebarLayout() {
        const sidebarPanel = document.getElementById('sidebar_panel');
        if (!sidebarPanel) return;
    
        const movableElements = document.querySelectorAll(
            '.o_main_navbar, .o_web_client > .o_control_panel, .o_web_client > .o_action_manager'
        );
    
        if (this.state.isCollapsed) {
            // في حالة الإغلاق: إخفاء السايدبار تماماً وإعادة الواجهة لحجمها الطبيعي
            sidebarPanel.classList.add('collapsed');
            sidebarPanel.classList.remove('open');
            
            movableElements.forEach(el => {
                el.classList.add('sidebar-collapsed');
                el.classList.remove('sidebar-active');
            });
        } else {
            // في حالة الفتح: إظهار السايدبار وتزحزح عناصر الواجهة (في الشاشات الكبيرة)
            sidebarPanel.classList.remove('collapsed');
            sidebarPanel.classList.add('open');
            
            movableElements.forEach(el => {
                el.classList.add('sidebar-active');
                el.classList.remove('sidebar-collapsed');
            });
        }
    },

    /**
     * زر الهمبرغر (☰) وزر الإغلاق الداخلي يقومان باستدعاء هذه الدالة
     */
    toggleSidebar() {
        this.state.isCollapsed = !this.state.isCollapsed;
        this.applySidebarLayout();
    },
    
    handleAppLiClick(app, ev) {
        if (!ev.target.closest('a')) {
            this.handleAppClick(app, ev);
        }
    },

    /**
     * التعامل مع النقر على عناصر القائمة الجانبية
     */
    async handleAppClick(menu, ev) {
        if (menu.actionID && ev && (ev.ctrlKey || ev.metaKey || ev.button === 1)) {
            return; 
        }
    
        if (ev) {
            ev.preventDefault();
            ev.stopPropagation();
        }
    
        const liElement = ev?.target.closest('li');
        const hasChildren = menu.childrenTree && menu.childrenTree.length > 0;
    
        // منطق الأكورديون
        if (hasChildren && liElement) {
            const parentUl = liElement.closest('ul');
            if (parentUl) {
                const siblingOpens = parentUl.querySelectorAll(':scope > li.open');
                siblingOpens.forEach(el => {
                    if (el !== liElement) {
                        el.classList.remove('open');
                        const nestedSubs = el.querySelectorAll('.open');
                        nestedSubs.forEach(nested => nested.classList.remove('open'));
                    }
                });
            }
    
            const subMenu = liElement.querySelector(':scope > .sidebar_sub_menu, :scope > ul');
            if (subMenu) {
                const isOpen = subMenu.classList.contains('open');
                subMenu.classList.toggle('open', !isOpen);
                liElement.classList.toggle('open', !isOpen);
            }

            if (menu.actionID) {
                this._cleanupUnrelatedMenus(liElement);
                await this.menuService.selectMenu(menu);

                // إغلاق تلقائي عند اختيار تطبيق مباشر (مثل Discussion) لتوفير مساحة
                // this.state.isCollapsed = true;
                // this.applySidebarLayout();
            }
            
            if (!menu.actionID) return;
        }
    
        // تنفيذ الأكشن للعناصر النهائية (Leaf Nodes) وإغلاق السايدبار بعدها مباشرة
        if (menu?.id && !hasChildren) {
            document.querySelectorAll('.sidebar_panel .active').forEach(el => el.classList.remove('active'));
            liElement?.classList.add('active');
    
            this._cleanupUnrelatedMenus(liElement);
            await this.menuService.selectMenu(menu);
    
            // إغلاق السايدبار الفاخر تلقائياً بعد اختيار الشاشة المطلوبة لراحة العين
            // this.state.isCollapsed = true;
            // this.applySidebarLayout();
        }
    },

    _cleanupUnrelatedMenus(currentLi) {
        const allOpenMenus = document.querySelectorAll('.sidebar_panel li.open');
        allOpenMenus.forEach(openLi => {
            if (openLi !== currentLi && !openLi.contains(currentLi)) {
                openLi.classList.remove('open');
                const sub = openLi.querySelector('.sidebar_sub_menu, ul');
                if (sub) sub.classList.remove('open');
            }
        });
    },

    applyActiveMenuOnLoad() {
        const currentApp = this.menuService.getCurrentApp();
        if (!currentApp) return;

        const appSelector = `.sidebar_menu > li[data-menu-xmlid="${currentApp.xmlid}"]`;
        const appLi = document.querySelector(appSelector);

        if (appLi) {
            appLi.classList.add('active');
            const subMenu = appLi.querySelector('.sidebar_sub_menu');
            if (subMenu) {
                subMenu.classList.add('open');
                appLi.classList.add('open');
            }
        }

        const currentMenu = this.menuService.getCurrentMenu();
        if (currentMenu) {
            const actionSelector = `li[data-menu-xmlid="${currentMenu.xmlid}"]`;
            const actionLi = document.querySelector(`.sidebar_panel ${actionSelector}`);

            if (actionLi) {
                actionLi.classList.add('active');
                let parent = actionLi.parentElement;
                while (parent && !parent.classList.contains('sidebar_menu')) {
                    if (parent.classList.contains('sidebar_sub_menu')) {
                        parent.classList.add('open');
                        parent.parentElement.classList.add('open', 'active');
                    }
                    parent = parent.parentElement;
                }
            }
        }
    },    

    async onNavBarDropdownItemSelection(menu) {
        if (menu) {
            await this.menuService.selectMenu(menu);
        }
    },
});