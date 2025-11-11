/** @odoo-module **/

import { NavBar } from '@web/webclient/navbar/navbar';
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks"; 
import { onMounted, useRef } from "@odoo/owl";
import { UserMenu } from "@web/webclient/user_menu/user_menu";

patch(NavBar.prototype, {
    UserMenu,
    setup() {
        super.setup();
        
        this.systrayItems = this.systrayItems.filter(
            (item) => item.Component.name !== UserMenu.name
        );
        
        this.openSidebarBtn = useRef("openSidebar"); 
        this.sidebarLinks = useRef("sidebarLinks");
        this.actionService = useService("action"); 
        this.menuService = useService("menu");

        this.handleMainMenuClickBound = this.handleMainMenuClick.bind(this);

        onMounted(() => {
            this.updateSidebarSections(); 
            this.addMainMenuListeners();
            if (this.sidebarLinks?.el) {
                this.allSubMenus = this.sidebarLinks.el.querySelectorAll('.sidebar_sub_menu');
                this.allArrows = this.sidebarLinks.el.querySelectorAll('.arrow-indicator');
            }
            
            const closeSidebarBtn = document.getElementById('closeSidebar');
            if (closeSidebarBtn) {
                closeSidebarBtn.addEventListener('click', this.closeSidebar.bind(this));
            }

            // ✅ الإغلاق عند النقر خارج القائمة (لتحسين UX)
            document.addEventListener('click', this.handleOutsideClick.bind(this));
        });

        this.env.bus.addEventListener("MENUS:APP-CHANGED", this.updateSidebarSections.bind(this));
    },

    // ✅ دالة لمعالجة النقر خارج القائمة الجانبية
    handleOutsideClick(event) {
        const sidebarPanel = document.getElementById('sidebar_panel');
        const openSidebarFloating = document.querySelector('.o_floating_sidebar_toggle_container');
        
        // إذا كانت القائمة مفتوحة ولم يتم النقر عليها أو على زر الفتح العائم
        if (sidebarPanel && sidebarPanel.classList.contains('open') &&
            !sidebarPanel.contains(event.target) && 
            !openSidebarFloating.contains(event.target)) {
            this.closeSidebar();
        }
    },

    updateSidebarSections() {
        if (!this.sidebarLinks || !this.sidebarLinks.el) {
            console.warn("sidebarLinks is not ready yet");
            return;
        }
    
        const allSubMenus = this.sidebarLinks.el.querySelectorAll('.sidebar_sub_menu');
        const allArrows = this.sidebarLinks.el.querySelectorAll('.arrow-indicator');

        // إغلاق كل القوائم وتصفير دوران الأسهم
        allSubMenus.forEach(menu => menu.classList.remove('open'));
        allArrows.forEach(a => a.style.transform = 'rotate(0deg)');
    
        const currentApp = this.menuService.getCurrentApp();
        if (currentApp) {
            const currentAppLink = this.sidebarLinks.el.querySelector(`[data-app-id="${currentApp.id}"]`);
            if (currentAppLink) {
                const currentSubMenu = currentAppLink.querySelector('.sidebar_sub_menu');
                const currentArrow = currentAppLink.querySelector('.arrow-indicator');

                if (currentSubMenu) currentSubMenu.classList.add('open');
                if (currentArrow) currentArrow.style.transform = 'rotate(90deg)';
            }
        }
        
        const mainMenus = this.sidebarLinks.el.querySelectorAll('.sidebar_main_menu, .sidebar_menu > li');
        mainMenus.forEach(menu => {
            menu.removeEventListener('click', this.handleMainMenuClickBound);
            this.handleMainMenuClickBound = this.handleMainMenuClickBound || this.handleMainMenuClick.bind(this);
            menu.addEventListener('click', this.handleMainMenuClickBound);
        });
    },


    handleMainMenuClick(event) {
        if (event.target.closest('.sidebar_sub_menu')) return;

        event.preventDefault();
        
        const clickedElement = event.currentTarget; 
        
        const subMenu = clickedElement.querySelector('.sidebar_sub_menu');
        const arrow = clickedElement.querySelector('.arrow-indicator');

        if (!subMenu) return;

        const isOpen = subMenu.classList.contains('open');

        this.allSubMenus.forEach(menu => menu.classList.remove('open'));
        this.allArrows.forEach(a => a.style.transform = 'rotate(0deg)');

        if (!isOpen) {
            subMenu.classList.add('open');
            if (arrow) arrow.style.transform = 'rotate(90deg)';
        }
    },

    addMainMenuListeners() {
        if (!this.sidebarLinks?.el) return;

        const mainMenus = this.sidebarLinks.el.querySelectorAll('.sidebar_main_menu, .sidebar_menu > li');
        mainMenus.forEach(menu => {
            menu.removeEventListener('click', this.handleMainMenuClickBound);
            menu.addEventListener('click', this.handleMainMenuClickBound);
        });
    },

    openSidebar() {
        const sidebarPanel = document.getElementById('sidebar_panel');
        if (!sidebarPanel) return;

        // ✅ إضافة كلاس 'open' لتحريك القائمة عبر CSS
        sidebarPanel.classList.add('open'); 

        // ✅ إضافة كلاس 'sidebar-active' لتحريك المحتوى عبر CSS
        const movableElements = document.querySelectorAll('.o_main_navbar, .o_web_client > .o_control_panel, .o_web_client > .o_action_manager');
        movableElements.forEach(el => el.classList.add('sidebar-active'));

        // إخفاء زر الفتح العائم
        const openSidebarFloating = document.querySelector('.o_floating_sidebar_toggle_container');
        if (openSidebarFloating) openSidebarFloating.style.display = 'none';
    },

    closeSidebar() {
        const sidebarPanel = document.getElementById('sidebar_panel');
        if (!sidebarPanel) return;

        // ✅ إزالة كلاس 'open' لغلق القائمة عبر CSS
        sidebarPanel.classList.remove('open');

        // ✅ إزالة كلاس 'sidebar-active' لإرجاع المحتوى عبر CSS
        const movableElements = document.querySelectorAll('.o_main_navbar, .o_web_client > .o_control_panel, .o_web_client > .o_action_manager');
        movableElements.forEach(el => el.classList.remove('sidebar-active'));
        
        // إظهار زر الفتح العائم
        const openSidebarFloating = document.querySelector('.o_floating_sidebar_toggle_container');
        if (openSidebarFloating) openSidebarFloating.style.display = 'block';
    },

    async onNavBarDropdownItemSelection(menu) {
        if (menu) {
            await this.menuService.selectMenu(menu);
            this.updateSidebarSections();
        }
    },
});