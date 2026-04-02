/** @odoo-module **/

import { NavBar } from '@web/webclient/navbar/navbar';
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks"; 
import { onMounted, useRef } from "@odoo/owl";
import { UserMenu } from "@web/webclient/user_menu/user_menu";
import { useState } from "@odoo/owl";


patch(NavBar.prototype, { 
    // إعادة تمرير UserMenu حتى لا ينكسر Navbar الأصلي
    UserMenu,

    setup() {
        // استدعاء setup الأصلي لـ NavBar (مهم جداً)
        super.setup();

        // إزالة UserMenu من systray (الزاوية اليمنى)
        // حتى لا يظهر مرتين (مرة في Navbar ومرة في Sidebar)
        this.systrayItems = this.systrayItems.filter(
            (item) => item.Component.name !== UserMenu.name
        );

        this.state = useState({
            isOpen: true, // نغير التسمية لتكون أوضح (مفتوح افتراضياً)
        });
        // مرجع DOM لقائمة الروابط الجانبية (للاستخدام لاحقاً إن لزم)
        this.sidebarLinks = useRef("sidebarLinks");

        // خدمة القوائم الرسمية في Odoo
        // مسؤولة عن تشغيل التطبيقات والأكشن
        this.menuService = useService("menu");
        
        // Hook يُنفّذ بعد تركيب الـ DOM
        // نستخدمه لتطبيق حالة السايدبار الافتراضية
        onMounted(() => {
            this.applySidebarLayout();
            this.applyActiveMenuOnLoad(); // ✅ تمييز العنصر المفتوح حالياً

        });
    },
    // New Helper to generate the URL for the <a> tag
    getMenuHref(menu) {
        if (!menu) return "#";
        
        // If it's a folder (has children but no direct action), 
        // we don't want a "New Tab" to do anything, so we return a void hash.
        if (menu.childrenTree?.length > 0 && !menu.actionID) {
            return "#";
        }
        // This allows Right Click -> Open in New Tab to target the specific action
        const menuId = menu.id;
        const actionId = menu.actionID || menu.action_id || "";
        
        return `/odoo/action-${actionId}?menu_id=${menuId}`;
    },

    /**
     * دالة مسؤولة فقط عن:
     * مزامنة حالة OWL (state) مع شكل الواجهة (DOM + CSS)
     * ❗ لا تغيّر state هنا
     */
    applySidebarLayout() {
        const sidebarPanel = document.getElementById('sidebar_panel');
        if (!sidebarPanel) return;
    
        const movableElements = document.querySelectorAll(
            '.o_main_navbar, .o_action_manager, .o_control_panel, .o_content'
        );
    
        if (this.state.isOpen) {
            // وضع الظهور الكامل
            sidebarPanel.classList.add('sidebar-active');
            sidebarPanel.classList.remove('sidebar-hidden'); // كلاس جديد للإخفاء
            
            movableElements.forEach(el => {
                el.classList.add('sidebar-active');
                el.classList.remove('sidebar-none');
            });
        } else {
            // وضع الإخفاء التام
            sidebarPanel.classList.remove('sidebar-active');
            sidebarPanel.classList.add('sidebar-hidden');
            
            movableElements.forEach(el => {
                el.classList.remove('sidebar-active');
                el.classList.add('sidebar-none');
            });
        }
    },
    // دالة التبديل
    // toggleSidebar() {
    //     this.state.isOpen = !this.state.isOpen;
    //     this.applySidebarLayout();
    // }
    toggleSidebar() {
        this.state.isOpen = !this.state.isOpen;
        this.applySidebarLayout();
        
        // إذا قام المستخدم بفتح القائمة، نعيد تمييز العناصر النشطة فوراً
        if (this.state.isOpen) {
            // نستخدم setTimeout بسيط لضمان أن الـ DOM أصبح مرئياً
            setTimeout(() => {
                this.applyActiveMenuOnLoad();
            }, 100);
        }
    },

    /**
     * helper function to handle click on li (outside <a>)
     */
    handleAppLiClick(app, ev) {
        if (!ev.target.closest('a')) {
            this.handleAppClick(app, ev);
        }
    },

    /**
     * التعامل مع النقر على عنصر من القائمة الجانبية
     * (تطبيق – قسم – عنصر نهائي)
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
    
        // // 1. الانسدال الفوري إذا كانت القائمة مصغرة
        // if (this.state.isCollapsed) {
        //     this.state.isCollapsed = false;
        //     this.applySidebarLayout();
        // }
    
        // 2. منطق الأكورديون (إغلاق الأشقاء فقط)
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
                
                // ✅ إذا كان التطبيق يحمل Action، نقوم بتنفيذ الأكشن + تنظيف القوائم البعيدة
                if (menu.actionID) {
                    this._cleanupUnrelatedMenus(liElement); // دالة تنظيف مخصصة
                    await this.menuService.selectMenu(menu);
                }
                
                if (!menu.actionID) return;
            }
        }
    
        // تنفيذ الأكشن للعناصر النهائية
        if (menu?.id && !hasChildren) {
            document.querySelectorAll('.sidebar_panel .active').forEach(el => el.classList.remove('active'));
            liElement?.classList.add('active');

            this._cleanupUnrelatedMenus(liElement);
            await this.menuService.selectMenu(menu);

            // في الموبايل فقط نغلق القائمة بعد الاختيار
            if (window.innerWidth <= 768) {
                this.state.isOpen = false; 
                this.applySidebarLayout();
            }
        }
    },
    
    /**
     * دالة مساعدة لتنظيف القوائم غير المرتبطة بالعنصر الحالي
     */
    _cleanupUnrelatedMenus(currentLi) {
        const allOpenMenus = document.querySelectorAll('.sidebar_panel li.open');
        allOpenMenus.forEach(openLi => {
            // نغلق القائمة فقط إذا لم تكن هي نفسها العنصر المختار وليست "أب" له
            if (openLi !== currentLi && !openLi.contains(currentLi)) {
                openLi.classList.remove('open');
                const sub = openLi.querySelector('.sidebar_sub_menu, ul');
                if (sub) sub.classList.remove('open');
            }
        });
    },

    // applyActiveMenuOnLoad() {
    //     const currentApp = this.menuService.getCurrentApp();
    //     if (!currentApp) return;
    
    //     // 1. تحديد التطبيق الحالي
    //     const appSelector = `.sidebar_menu > li[data-menu-xmlid="${currentApp.xmlid}"]`;
    //     const appLi = document.querySelector(appSelector);
    
    //     if (appLi) {
    //         appLi.classList.add('active');
    //         const subMenu = appLi.querySelector('.sidebar_sub_menu');
    //         if (subMenu) {
    //             subMenu.classList.add('open');
    //             appLi.classList.add('open');
    //         }
    //     }
    
    //     // 2. تحديد العنصر الفرعي (Action)
    //     const currentMenu = this.menuService.getCurrentMenu();
    //     if (currentMenu) {
    //         const actionLi = document.querySelector(`.sidebar_panel li[data-menu-xmlid="${currentMenu.xmlid}"]`);
    
    //         if (actionLi) {
    //             actionLi.classList.add('active');
    
    //             // فتح كل الآباء وصولاً للعنصر المختار
    //             let parent = actionLi.parentElement;
    //             while (parent && !parent.classList.contains('sidebar_menu')) {
    //                 if (parent.classList.contains('sidebar_sub_menu') || parent.tagName === 'UL') {
    //                     parent.classList.add('open');
    //                     parent.parentElement.classList.add('open', 'active');
    //                 }
    //                 parent = parent.parentElement;
    //             }
                
    //             // اختياري: إذا وجدنا عنصراً نشطاً، نفتح السايدبار تلقائياً
    //             this.state.isOpen = true;
    //             this.applySidebarLayout();
    //         }
    //     }
    // }
    // applyActiveMenuOnLoad() {
    //     const currentApp = this.menuService.getCurrentApp();
    //     const currentMenu = this.menuService.getCurrentMenu();
        
    //     if (!currentApp) return;
    
    //     // 1. إزالة أي حالة Active أو Open قديمة لتجنب التكرار
    //     document.querySelectorAll('.sidebar_panel .active, .sidebar_panel .open').forEach(el => {
    //         el.classList.remove('active', 'open');
    //     });
    
    //     // 2. تمييز التطبيق الرئيسي (Root App)
    //     const appLi = document.querySelector(`.sidebar_menu > li[data-menu-xmlid="${currentApp.xmlid}"]`);
    //     if (appLi) {
    //         appLi.classList.add('active');
    //         // لا نفتح القائمة الفرعية للتطبيق إلا إذا كان هو نفسه الأكشن الحالي أو يحتوي عليه
    //     }
    
    //     // 3. تمييز العنصر الفرعي المفتوح حالياً (Leaf Action)
    //     if (currentMenu) {
    //         const actionLi = document.querySelector(`.sidebar_panel li[data-menu-xmlid="${currentMenu.xmlid}"]`);
    
    //         if (actionLi) {
    //             actionLi.classList.add('active');
    
    //             // 4. المنطق السحري: فتح كل الآباء صعوداً إلى الأعلى
    //             let parent = actionLi.parentElement;
    //             while (parent && !parent.classList.contains('sidebar_menu')) {
    //                 // إذا وجدنا قائمة فرعية أو عنصر أب، نقوم بفتحه
    //                 if (parent.classList.contains('sidebar_sub_menu') || parent.tagName === 'UL') {
    //                     parent.classList.add('open');
    //                     // إضافة كلاس open للـ li الأب لتدوير السهم (Arrow)
    //                     if (parent.parentElement && parent.parentElement.tagName === 'LI') {
    //                         parent.parentElement.classList.add('open');
    //                         // اختياري: تمييز الآباء بلون خفيف
    //                         parent.parentElement.classList.add('active-path'); 
    //                     }
    //                 }
    //                 parent = parent.parentElement;
    //             }
    //         }
    //     }
    // },    
    applyActiveMenuOnLoad() {
        // 1. الحصول على التطبيق الحالي والقائمة الحالية بأمان
        const currentApp = this.menuService.getCurrentApp();
        
        // في Odoo 18 نستخدم getCurrentMenuId أو نصل للمنيو من الخدمة مباشرة
        const currentMenuId = this.menuService.getCurrentMenuId ? 
                             this.menuService.getCurrentMenuId() : 
                             (this.menuService.currentPrimaryMenu ? this.menuService.currentPrimaryMenu.id : null);
        
        if (!currentApp) return;
    
        // 2. تنظيف شامل لأي حالات active أو open سابقة لضمان التحديث الصحيح
        const sidebar = document.querySelector('.sidebar_panel');
        if (sidebar) {
            sidebar.querySelectorAll('.active, .open, .active-path').forEach(el => {
                el.classList.remove('active', 'open', 'active-path');
            });
        }
    
        // 3. تمييز التطبيق الرئيسي (الآيقونة/العنصر الأول في السايدبار)
        const appLi = document.querySelector(`.sidebar_menu > li[data-menu-xmlid="${currentApp.xmlid}"]`);
        if (appLi) {
            appLi.classList.add('active');
        }
    
        // 4. تمييز العنصر النشط وفتح "شجرة الآباء" (Breadcrumbs Logic)
        if (currentMenuId) {
            // نبحث عن العنصر باستخدام المعرف الرقمي (data-menu-id) 
            // أو الـ xmlid كخيار احتياطي لضمان الوصول للعنصر
            const actionLi = document.querySelector(`.sidebar_panel li[data-menu-id="${currentMenuId}"]`) || 
                             document.querySelector(`.sidebar_panel li[data-menu-xmlid="${currentApp.xmlid}"]`);
    
            if (actionLi) {
                actionLi.classList.add('active');
    
                // 5. المنطق السحري: الصعود من العنصر المختار إلى أعلى لفتح كل القوائم المتداخلة
                let parent = actionLi.parentElement;
                
                while (parent && !parent.classList.contains('sidebar_menu')) {
                    // إذا كان العنصر الحالي هو قائمة (UL) أو حاوية قوائم فرعية
                    if (parent.classList.contains('sidebar_sub_menu') || parent.tagName === 'UL') {
                        parent.classList.add('open');
                        
                        // العثور على الـ LI الأب لهذه القائمة لفتحه وتدوير السهم الخاص به
                        const parentLi = parent.closest('li');
                        if (parentLi) {
                            parentLi.classList.add('open');
                            parentLi.classList.add('active-path'); // لتمييز مسار الأب بصرياً
                        }
                    }
                    parent = parent.parentElement;
                }
            }
        }
    },
    /**
     * اختيار عنصر من Navbar العلوي
     * (مثلاً من Dropdown التطبيقات)
     */
    async onNavBarDropdownItemSelection(menu) {
        if (menu) {
            // تشغيل التطبيق / الأكشن
            await this.menuService.selectMenu(menu);

            // في وضع الشاشات الصغيرة (موبايل)
            // يمكن إغلاق السايدبار تلقائياً
            if (window.innerWidth < 768) {
                this.closeSidebar?.(); // حماية في حال لم تكن الدالة موجودة
            }
        }
    },
});
















































// /** @odoo-module **/

// import { NavBar } from '@web/webclient/navbar/navbar';
// import { patch } from "@web/core/utils/patch";
// import { useService } from "@web/core/utils/hooks"; 
// import { onMounted, useRef } from "@odoo/owl";
// import { UserMenu } from "@web/webclient/user_menu/user_menu";

// patch(NavBar.prototype, {
//     UserMenu,
//     setup() {
//         super.setup();
        
//         this.systrayItems = this.systrayItems.filter(
//             (item) => item.Component.name !== UserMenu.name
//         );
        
//         this.openSidebarBtn = useRef("openSidebar"); 
//         this.sidebarLinks = useRef("sidebarLinks");
//         this.actionService = useService("action"); 
//         this.menuService = useService("menu");

//         this.handleMainMenuClickBound = this.handleMainMenuClick.bind(this);
//         // إضافة دالة الربط للقوائم الفرعيه هنا
//         this.handleSubMenuToggleClickBound = this.handleSubMenuToggleClick.bind(this); 
//         this.handleAccordionClickBound = this.handleAccordionClick.bind(this);

//         onMounted(() => {
//             this.updateSidebarSections(); 
//             this.addMainMenuListeners();
//             // this.addSectionMenuListeners();
//             if (this.sidebarLinks?.el) {
//                 this.allSubMenus = this.sidebarLinks.el.querySelectorAll('.sidebar_sub_menu');
//                 // this.allArrows = this.sidebarLinks.el.querySelectorAll('.arrow-indicator');
//                 // إضافة مستمعات النقر للقوائم الفرعية الثانوية
//                 this.addSubMenuToggleListeners();
//                 this.addAccordionListeners();
//             }
            
//             const closeSidebarBtn = document.getElementById('closeSidebar');
//             if (closeSidebarBtn) {
//                 closeSidebarBtn.addEventListener('click', this.closeSidebar.bind(this));
//             }

//             // الإغلاق عند النقر خارج القائمة (لتحسين UX)
//             document.addEventListener('click', this.handleOutsideClick.bind(this));
            
//         });

//         this.env.bus.addEventListener("MENUS:APP-CHANGED", () => {
//             this.updateSidebarSections.bind(this)
//             // this.addSectionMenuListeners();
//         }
//         );

//     },
//     // Ensure this is defined outside the class or bound correctly if using a class
// // For a class method, the binding in addAccordionListeners is good.

// handleAccordionClick(event) {
//     const header = event.currentTarget;
//     // The panel is the element immediately following the header in the DOM
//     const panel = header.nextElementSibling; 

//     if (!panel) return; // Safety check

//     // 1. Toggle the "active" class on the header
//     header.classList.toggle('active'); 

//     // 2. Toggle the panel's visibility (like your provided logic)
//     // Note: The vanilla JS logic uses inline 'style.display', 
//     // but it's generally better practice to use classes for styling, 
//     // especially for transitions/animations. 
//     // I'll provide both options.

//     // --- Option A: Using inline style (closest to your provided logic) ---
//     // if (panel.style.display === "block") {
//     //     panel.style.display = "none";
//     // } else {
//     //     panel.style.display = "block";
//     // }
    
//     // --- Option B: Using max-height for CSS control (Recommended) ---
//     // If you're using CSS to hide/show the panel with max-height/height,
//     // this is the standard way to toggle:
//     if (panel.style.maxHeight) {
//         // Close the panel
//         panel.style.maxHeight = null;
//     } else {
//         // Open the panel
//         // Use scrollHeight to get the full height of the content
//         panel.style.maxHeight = panel.scrollHeight + "px";
//     }

//     // --- Optional: Close siblings (modified to look at panels) ---
//     // If you still want the "single open accordion" behavior, 
//     // you need to loop through *all* headers and their corresponding panels.
//     // This part requires access to all headers, which might be tricky 
//     // within the click handler unless you scope it differently.
//     // For simplicity, I'm removing the sibling logic, as your example 
//     // vanilla JS loop *did not* include sibling closure.
// },

// // The addAccordionListeners method can remain largely the same, 
// // ensuring you are selecting the correct header elements.

// addAccordionListeners() {
//     if (!this.sidebarLinks?.el) return;

//     // Assuming '.accordion' is the class on your clickable header element
//     const headers = this.sidebarLinks.el.querySelectorAll('.accordion');

//     headers.forEach(header => {
//         // Ensure handleAccordionClick is correctly bound to 'this' 
//         // if this code lives inside a class/object.
//         header.removeEventListener(
//             'click',
//             this.handleAccordionClickBound
//         );
//         header.addEventListener(
//             'click',
//             this.handleAccordionClickBound
//         );
//     });
// },
    
//     // دالة جديدة لمعالجة النقر على أزرار فتح/إغلاق القائمة الفرعية الثانوية
//     handleSubMenuToggleClick(event) { 
//         const clickedElement = event.currentTarget; 
        
//         // يضمن أن النقر لا يؤدي إلى تنقل Odoo إذا كان هناك زر فتح/إغلاق
//         event.preventDefault(); 
        
//         // الحصول على العنصر الأب المباشر الذي هو `<li>`
//         const parentLi = clickedElement.closest('li');

//         if (parentLi) {
//             // 1. منطق إغلاق جميع الأشقاء (Siblings) في نفس المستوى
//             const siblings = parentLi.parentElement.querySelectorAll('li');
//             siblings.forEach(li => {
//                 // نتأكد من أننا لا نغلق العنصر الذي تم النقر عليه حاليًا
//                 if (li !== parentLi) {
//                     li.classList.remove('open');
//                 }
//             });

//             // 2. تبديل (Toggle) الفئة 'open' على العنصر الأب `<li>` لفتحه أو إغلاقه
//             parentLi.classList.toggle('open');
            
//         }
//     },
//     // دالة جديدة لإضافة مستمعات الأحداث إلى جميع عناصر .o_menu_toggle
//     addSubMenuToggleListeners() { 
//         if (!this.sidebarLinks?.el) return;

//         // اختيار جميع أزرار التبديل داخل القائمة الجانبية
//         const toggleButtons = this.sidebarLinks.el.querySelectorAll('.sidebar_sub_menu .o_menu_toggle');
        
//         // تكرار على كل زر وإضافة مستمع الحدث
//         toggleButtons.forEach(button => {
//             // إزالة المستمع القديم أولاً (للتأكد من عدم تكراره)
//             button.removeEventListener('click', this.handleSubMenuToggleClickBound);
//             // إضافة المستمع الجديد
//             button.addEventListener('click', this.handleSubMenuToggleClickBound);
//         });
//     },

    

//     // دالة لمعالجة النقر خارج القائمة الجانبية
//     handleOutsideClick(event) {
//         const sidebarPanel = document.getElementById('sidebar_panel');
//         const openSidebarFloating = document.querySelector('.o_floating_sidebar_toggle_container');
        
//         // إذا كانت القائمة مفتوحة ولم يتم النقر عليها أو على زر الفتح العائم
//         if (sidebarPanel && sidebarPanel.classList.contains('open') &&
//             !sidebarPanel.contains(event.target) && 
//             !openSidebarFloating.contains(event.target)) {
//             this.closeSidebar();
//         }
//     },

//     updateSidebarSections() {
//         if (!this.sidebarLinks || !this.sidebarLinks.el) return;
    
//         // 1. استهداف جميع القوائم الفرعية (المستوى الأول والثاني)
//         const allSubMenus = this.sidebarLinks.el.querySelectorAll('.sidebar_sub_menu, .sidebar_sub_menu ul');
    
//         // 2. إغلاق كل شيء عند تحميل الصفحة لضمان حالة نظيفة
//         allSubMenus.forEach(menu => {
//             menu.classList.remove('open');
//             // إذا كنت تستخدم منطق الأكورديون (max-height)
//             if (menu.style.maxHeight) {
//                 menu.style.maxHeight = null;
//             }
//         });
    
//         // 3. (اختياري) إذا أردت فتح التطبيق الرئيسي فقط بدون أقسامه الفرعية:
//         const currentApp = this.menuService.getCurrentApp();
//         if (currentApp) {
//             const currentAppLink = this.sidebarLinks.el.querySelector(`[data-app-id="${currentApp.id}"]`);
//             if (currentAppLink) {
//                 // نفتح فقط الحاوية الكبرى للتطبيق الحالي
//                 const mainSubMenu = currentAppLink.querySelector('.sidebar_sub_menu');
//                 if (mainSubMenu) {
//                     mainSubMenu.classList.add('open');
//                 }
//             }
//         }
//     },


//     handleMainMenuClick(event) {
//         // منع التداخل إذا تم النقر على عنصر فرعي بالفعل
//         if (event.target.closest('.sidebar_sub_menu li')) return;
    
//         event.preventDefault();
//         const clickedElement = event.currentTarget; 
//         const subMenu = clickedElement.querySelector('.sidebar_sub_menu');
    
//         if (!subMenu) return;
    
//         const isOpen = subMenu.classList.contains('open');
    
//         // إغلاق القوائم الأخرى (إذا أردت سلوك الأكورديون)
//         this.allSubMenus.forEach(menu => {
//             if (menu !== subMenu) menu.classList.remove('open');
//         });
    
//         // تبديل حالة القائمة الحالية فقط
//         subMenu.classList.toggle('open', !isOpen);
//     },

//     addMainMenuListeners() {
//         if (!this.sidebarLinks?.el) return;

//         const mainMenus = this.sidebarLinks.el.querySelectorAll('.sidebar_main_menu, .sidebar_menu > li');
//         mainMenus.forEach(menu => {
//             menu.removeEventListener('click', this.handleMainMenuClickBound);
//             menu.addEventListener('click', this.handleMainMenuClickBound);
//         });
//     },

//     // to open the sidebar menu
//     openSidebar() {
//         const sidebarPanel = document.getElementById('sidebar_panel');
//         if (!sidebarPanel) return;

//         // ✅ إضافة كلاس 'open' لتحريك القائمة عبر CSS
//         sidebarPanel.classList.add('open'); 

//         // ✅ إضافة كلاس 'sidebar-active' لتحريك المحتوى عبر CSS
//         const movableElements = document.querySelectorAll('.o_main_navbar, .o_web_client > .o_control_panel, .o_web_client > .o_action_manager');
//         movableElements.forEach(el => el.classList.add('sidebar-active'));

//         // إخفاء زر الفتح العائم
//         const openSidebarFloating = document.querySelector('.o_floating_sidebar_toggle_container');
//         if (openSidebarFloating) openSidebarFloating.style.display = 'none';
//     },

//     // to close the sidebar menu
//     closeSidebar() {
//         const sidebarPanel = document.getElementById('sidebar_panel');
//         if (!sidebarPanel) return;

//         // ✅ إزالة كلاس 'open' لغلق القائمة عبر CSS
//         sidebarPanel.classList.remove('open');

//         // ✅ إزالة كلاس 'sidebar-active' لإرجاع المحتوى عبر CSS
//         const movableElements = document.querySelectorAll('.o_main_navbar, .o_web_client > .o_control_panel, .o_web_client > .o_action_manager');
//         movableElements.forEach(el => el.classList.remove('sidebar-active'));
        
//         // إظهار زر الفتح العائم
//         const openSidebarFloating = document.querySelector('.o_floating_sidebar_toggle_container');
//         if (openSidebarFloating) openSidebarFloating.style.display = 'block';
//     },

//     async onNavBarDropdownItemSelection(menu) {
//         if (menu) {
//             await this.menuService.selectMenu(menu);
//             this.updateSidebarSections();
//         }
//     },
// });

