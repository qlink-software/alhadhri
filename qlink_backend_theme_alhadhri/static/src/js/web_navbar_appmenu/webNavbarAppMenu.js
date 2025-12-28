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
        // إضافة دالة الربط للقوائم الفرعيه هنا
        this.handleSubMenuToggleClickBound = this.handleSubMenuToggleClick.bind(this); 
        this.handleAccordionClickBound = this.handleAccordionClick.bind(this);

        onMounted(() => {
            this.updateSidebarSections(); 
            this.addMainMenuListeners();
            // this.addSectionMenuListeners();
            if (this.sidebarLinks?.el) {
                this.allSubMenus = this.sidebarLinks.el.querySelectorAll('.sidebar_sub_menu');
                // this.allArrows = this.sidebarLinks.el.querySelectorAll('.arrow-indicator');
                // إضافة مستمعات النقر للقوائم الفرعية الثانوية
                this.addSubMenuToggleListeners();
                this.addAccordionListeners();
            }
            
            const closeSidebarBtn = document.getElementById('closeSidebar');
            if (closeSidebarBtn) {
                closeSidebarBtn.addEventListener('click', this.closeSidebar.bind(this));
            }

            // الإغلاق عند النقر خارج القائمة (لتحسين UX)
            document.addEventListener('click', this.handleOutsideClick.bind(this));
            
        });

        this.env.bus.addEventListener("MENUS:APP-CHANGED", () => {
            this.updateSidebarSections.bind(this)
            // this.addSectionMenuListeners();
        }
        );

    },
    // Ensure this is defined outside the class or bound correctly if using a class
// For a class method, the binding in addAccordionListeners is good.

handleAccordionClick(event) {
    const header = event.currentTarget;
    // The panel is the element immediately following the header in the DOM
    const panel = header.nextElementSibling; 

    if (!panel) return; // Safety check

    // 1. Toggle the "active" class on the header
    header.classList.toggle('active'); 

    // 2. Toggle the panel's visibility (like your provided logic)
    // Note: The vanilla JS logic uses inline 'style.display', 
    // but it's generally better practice to use classes for styling, 
    // especially for transitions/animations. 
    // I'll provide both options.

    // --- Option A: Using inline style (closest to your provided logic) ---
    // if (panel.style.display === "block") {
    //     panel.style.display = "none";
    // } else {
    //     panel.style.display = "block";
    // }
    
    // --- Option B: Using max-height for CSS control (Recommended) ---
    // If you're using CSS to hide/show the panel with max-height/height,
    // this is the standard way to toggle:
    if (panel.style.maxHeight) {
        // Close the panel
        panel.style.maxHeight = null;
    } else {
        // Open the panel
        // Use scrollHeight to get the full height of the content
        panel.style.maxHeight = panel.scrollHeight + "px";
    }

    // --- Optional: Close siblings (modified to look at panels) ---
    // If you still want the "single open accordion" behavior, 
    // you need to loop through *all* headers and their corresponding panels.
    // This part requires access to all headers, which might be tricky 
    // within the click handler unless you scope it differently.
    // For simplicity, I'm removing the sibling logic, as your example 
    // vanilla JS loop *did not* include sibling closure.
},

// The addAccordionListeners method can remain largely the same, 
// ensuring you are selecting the correct header elements.

addAccordionListeners() {
    if (!this.sidebarLinks?.el) return;

    // Assuming '.accordion' is the class on your clickable header element
    const headers = this.sidebarLinks.el.querySelectorAll('.accordion');

    headers.forEach(header => {
        // Ensure handleAccordionClick is correctly bound to 'this' 
        // if this code lives inside a class/object.
        header.removeEventListener(
            'click',
            this.handleAccordionClickBound
        );
        header.addEventListener(
            'click',
            this.handleAccordionClickBound
        );
    });
},
    
    // دالة جديدة لمعالجة النقر على أزرار فتح/إغلاق القائمة الفرعية الثانوية
    handleSubMenuToggleClick(event) { 
        const clickedElement = event.currentTarget; 
        
        // يضمن أن النقر لا يؤدي إلى تنقل Odoo إذا كان هناك زر فتح/إغلاق
        event.preventDefault(); 
        
        // الحصول على العنصر الأب المباشر الذي هو `<li>`
        const parentLi = clickedElement.closest('li');

        if (parentLi) {
            // 1. منطق إغلاق جميع الأشقاء (Siblings) في نفس المستوى
            const siblings = parentLi.parentElement.querySelectorAll('li');
            siblings.forEach(li => {
                // نتأكد من أننا لا نغلق العنصر الذي تم النقر عليه حاليًا
                if (li !== parentLi) {
                    li.classList.remove('open');
                }
            });

            // 2. تبديل (Toggle) الفئة 'open' على العنصر الأب `<li>` لفتحه أو إغلاقه
            parentLi.classList.toggle('open');
            
        }
    },
    // دالة جديدة لإضافة مستمعات الأحداث إلى جميع عناصر .o_menu_toggle
    addSubMenuToggleListeners() { 
        if (!this.sidebarLinks?.el) return;

        // اختيار جميع أزرار التبديل داخل القائمة الجانبية
        const toggleButtons = this.sidebarLinks.el.querySelectorAll('.sidebar_sub_menu .o_menu_toggle');
        
        // تكرار على كل زر وإضافة مستمع الحدث
        toggleButtons.forEach(button => {
            // إزالة المستمع القديم أولاً (للتأكد من عدم تكراره)
            button.removeEventListener('click', this.handleSubMenuToggleClickBound);
            // إضافة المستمع الجديد
            button.addEventListener('click', this.handleSubMenuToggleClickBound);
        });
    },

    

    // دالة لمعالجة النقر خارج القائمة الجانبية
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
        if (!this.sidebarLinks || !this.sidebarLinks.el) return;
    
        // 1. استهداف جميع القوائم الفرعية (المستوى الأول والثاني)
        const allSubMenus = this.sidebarLinks.el.querySelectorAll('.sidebar_sub_menu, .sidebar_sub_menu ul');
    
        // 2. إغلاق كل شيء عند تحميل الصفحة لضمان حالة نظيفة
        allSubMenus.forEach(menu => {
            menu.classList.remove('open');
            // إذا كنت تستخدم منطق الأكورديون (max-height)
            if (menu.style.maxHeight) {
                menu.style.maxHeight = null;
            }
        });
    
        // 3. (اختياري) إذا أردت فتح التطبيق الرئيسي فقط بدون أقسامه الفرعية:
        const currentApp = this.menuService.getCurrentApp();
        if (currentApp) {
            const currentAppLink = this.sidebarLinks.el.querySelector(`[data-app-id="${currentApp.id}"]`);
            if (currentAppLink) {
                // نفتح فقط الحاوية الكبرى للتطبيق الحالي
                const mainSubMenu = currentAppLink.querySelector('.sidebar_sub_menu');
                if (mainSubMenu) {
                    mainSubMenu.classList.add('open');
                }
            }
        }
    },


    handleMainMenuClick(event) {
        // منع التداخل إذا تم النقر على عنصر فرعي بالفعل
        if (event.target.closest('.sidebar_sub_menu li')) return;
    
        event.preventDefault();
        const clickedElement = event.currentTarget; 
        const subMenu = clickedElement.querySelector('.sidebar_sub_menu');
    
        if (!subMenu) return;
    
        const isOpen = subMenu.classList.contains('open');
    
        // إغلاق القوائم الأخرى (إذا أردت سلوك الأكورديون)
        this.allSubMenus.forEach(menu => {
            if (menu !== subMenu) menu.classList.remove('open');
        });
    
        // تبديل حالة القائمة الحالية فقط
        subMenu.classList.toggle('open', !isOpen);
    },

    addMainMenuListeners() {
        if (!this.sidebarLinks?.el) return;

        const mainMenus = this.sidebarLinks.el.querySelectorAll('.sidebar_main_menu, .sidebar_menu > li');
        mainMenus.forEach(menu => {
            menu.removeEventListener('click', this.handleMainMenuClickBound);
            menu.addEventListener('click', this.handleMainMenuClickBound);
        });
    },

    // to open the sidebar menu
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

    // to close the sidebar menu
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

