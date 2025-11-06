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
        // 🔑 الحل الأول: تصفية UserMenu من systrayItems
        // هذا يمنع Odoo من عرض القائمة تلقائياً
        this.systrayItems = this.systrayItems.filter(
            (item) => item.Component.name !== UserMenu.name
        );
        // المراجع
        this.openSidebarBtn = useRef("openSidebar"); 
        this.sidebarLinks = useRef("sidebarLinks");
        this.actionService = useService("action"); 
        this.menuService = useService("menu");

        // الدوال مربوطة
        this.handleMainMenuClickBound = this.handleMainMenuClick.bind(this);

        onMounted(() => {
            this.openSidebar(); 
            this.updateSidebarSections(); 
            this.addMainMenuListeners();
            // تخزين كل العناصر لتسريع الأداء
            if (this.sidebarLinks?.el) {
                this.allSubMenus = this.sidebarLinks.el.querySelectorAll('.sidebar_sub_menu');
                this.allArrows = this.sidebarLinks.el.querySelectorAll('.arrow-indicator');
            }
        });

        this.env.bus.addEventListener("MENUS:APP-CHANGED", this.updateSidebarSections.bind(this));
    },

    updateSidebarSections() {
        if (!this.sidebarLinks || !this.sidebarLinks.el) {
            console.warn("sidebarLinks is not ready yet");
            return;
        }
    
        const allSubMenus = this.sidebarLinks.el.querySelectorAll('.sidebar_sub_menu');
        allSubMenus.forEach(menu => menu.classList.remove('open'));
    
        const currentApp = this.menuService.getCurrentApp();
        if (currentApp) {
            const currentAppLink = this.sidebarLinks.el.querySelector(`[data-app-id="${currentApp.id}"]`);
            if (currentAppLink) {
                const currentSubMenu = currentAppLink.querySelector('.sidebar_sub_menu');
                if (currentSubMenu) currentSubMenu.classList.add('open');
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
        // إذا تم النقر داخل قائمة فرعية، تجاهل العملية لمنع إغلاق القائمة
        if (event.target.closest('.sidebar_sub_menu')) return;

        event.preventDefault();
        
        // **التعديل هنا:** البحث عن العنصر الأب الذي يمثل القائمة الرئيسية (<li>)
        // سواء تم النقر على الرابط (<a>) أو السهم (<span>)
        const clickedElement = event.currentTarget; 
        
        // البحث عن القائمة الفرعية (إذا كانت موجودة) والسهم داخل العنصر الذي تم النقر عليه
        const subMenu = clickedElement.querySelector('.sidebar_sub_menu');
        const arrow = clickedElement.querySelector('.arrow-indicator');

        // إذا لم توجد قائمة فرعية، لا تفعل شيئاً
        if (!subMenu) return;

        const isOpen = subMenu.classList.contains('open');

        // أغلق كل القوائم المفتوحة حالياً (وهذا يحقق سلوك التبديل)
        this.allSubMenus.forEach(menu => menu.classList.remove('open'));
        this.allArrows.forEach(a => a.style.transform = 'rotate(0deg)');

        // إذا كانت القائمة مغلقة، افتحها الآن
        if (!isOpen) {
            subMenu.classList.add('open');
            if (arrow) arrow.style.transform = 'rotate(90deg)';
        }
        // إذا كانت مفتوحة، فستُغلق في الخطوة السابقة (الإغلاق الشامل)
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

        // تحديد العرض ديناميكي حسب حجم الشاشة
        const sidebarWidth = window.innerWidth < 768 ? '70%' : '250px';
        sidebarPanel.style.display = 'block';
        sidebarPanel.classList.add('fixed_sidebar_active');
        sidebarPanel.style.left = '0';
        sidebarPanel.style.width = sidebarWidth;

        const mainNavbar = document.querySelector('.o_main_navbar');
        if (mainNavbar) {
            mainNavbar.style.left = sidebarWidth;
            mainNavbar.style.width = `calc(100% - ${sidebarWidth})`;
            mainNavbar.style.transition = 'all .2s linear';
        }

        const controlPanel = document.querySelector('.o_web_client > .o_control_panel');
        if (controlPanel) {
            controlPanel.style.left = sidebarWidth;
            controlPanel.style.width = `calc(100% - ${sidebarWidth})`;
            controlPanel.style.transition = 'all .2s linear';
        }

        const actionManager = document.querySelector('.o_web_client > .o_action_manager');
        if (actionManager) {
            actionManager.style.marginLeft = sidebarWidth;
            actionManager.style.transition = 'all .2s linear';
        }

        if (this.openSidebarBtn?.el) this.openSidebarBtn.el.style.display = 'none';
    },

    closeSidebar() {
        const sidebarPanel = document.getElementById('sidebar_panel');
        if (!sidebarPanel) return;

        sidebarPanel.style.left = '-250px';
        sidebarPanel.classList.remove('fixed_sidebar_active');

        const mainNavbar = document.querySelector('.o_main_navbar');
        if (mainNavbar) {
            mainNavbar.style.left = '0';
            mainNavbar.style.width = '100%';
            mainNavbar.style.transition = 'all .2s linear';
        }

        const controlPanel = document.querySelector('.o_web_client > .o_control_panel');
        if (controlPanel) {
            controlPanel.style.left = '0';
            controlPanel.style.width = '100%';
            controlPanel.style.transition = 'all .2s linear';
        }

        const actionManager = document.querySelector('.o_web_client > .o_action_manager');
        if (actionManager) {
            actionManager.style.marginLeft = '0';
            actionManager.style.transition = 'all .2s linear';
        }

        if (this.openSidebarBtn?.el) this.openSidebarBtn.el.style.display = 'block';
    },

    async onNavBarDropdownItemSelection(menu) {
        if (menu) {
            await this.menuService.selectMenu(menu);
            this.updateSidebarSections();
        }
    },
});
