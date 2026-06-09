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
        super.setup();

        this.systrayItems = this.systrayItems.filter(
            (item) => item.Component.name !== UserMenu.name
        );

        // 1. استرجاع الحالة المخزنة أولاً
        const savedTheme = localStorage.getItem("selected_theme") || "light";
        
        // 2. تطبيق السمة فوراً على مستوى الـ DOM قبل تحميل بقية الواجهة
        document.documentElement.setAttribute("data-bs-theme", savedTheme);

        this.state = useState({
            isCollapsed: true,
            isDark: savedTheme === "dark", // تعيين الحالة بناءً على المخزن
        });

        this.menuService = useService("menu");
        
        onMounted(() => {
            this.applySidebarLayout();
            this.applyActiveMenuOnLoad();
            
            // تأكيد إضافي عند التركيب لضمان عدم حدوث Flicker (وميض أبيض)
            document.documentElement.setAttribute("data-bs-theme", this.state.isDark ? "dark" : "light");
            // ✅ إضافة مراقب للنقرات الخارجية لإغلاق السايدبار
            document.addEventListener("click", this.onExternalClick.bind(this));
        });
    },

    toggleDarkMode() {
        this.state.isDark = !this.state.isDark;
        const theme = this.state.isDark ? "dark" : "light";
        
        // التغيير الفوري
        document.documentElement.setAttribute("data-bs-theme", theme);
        // الحفظ الدائم
        localStorage.setItem("selected_theme", theme);
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
         * ✅ دالة إغلاق السايدبار عند النقر في الخارج (Action Manager أو الأوراق)
         */
    onExternalClick(ev) {
        const sidebarPanel = document.getElementById('sidebar_panel');
        const toggleBtn = document.querySelector('.o_modern_sidebar_toggle'); // أو زر التوجل الخاص بك
        
        // إذا كان السايدبار مفتوحاً والنقرة تمت خارجه وليس على زر الفتح
        if (!this.state.isCollapsed && sidebarPanel && !sidebarPanel.contains(ev.target) && !ev.target.closest('.sidebar')) {
            
            // خيار: إغلاقه فقط في الموبايل
            // if (window.innerWidth <= 768) { 
                this.state.isCollapsed = true;
                this.applySidebarLayout();
            // }
        }
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
            '.o_main_navbar, .o_web_client > .o_control_panel, .o_web_client > .o_action_manager'
        );
    
        const isMobile = window.innerWidth <= 768;
    
        // if (isMobile) {
        //     // ✅ المنطق الجديد للموبايل: يدعم التصغير والفتح
        //     if (this.state.isCollapsed) {
        //         sidebarPanel.classList.add('collapsed'); // وضع الأيقونات
        //         sidebarPanel.classList.remove('open');    // إزالة الفتح الكامل
        //         // document.body.classList.remove('sidebar-mobile-opened');
        //     } else {
        //         sidebarPanel.classList.add('open');       // الفتح الكامل (نصوص + شعار)
        //         sidebarPanel.classList.remove('collapsed');
        //         // document.body.classList.add('sidebar-mobile-opened');
        //   }
        // } else {
            // وضع الديسكتوب (نفس منطقك السابق)
            // document.body.classList.remove('sidebar-mobile-opened');
        sidebarPanel.classList.remove('open'); // لا نحتاج open في الديسكتوب
        
        if (this.state.isCollapsed) {
            sidebarPanel.classList.add('collapsed');
            movableElements.forEach(el => {
                el.classList.add('sidebar-collapsed');
                el.classList.remove('sidebar-active');
            });
        } else {
            sidebarPanel.classList.remove('collapsed');
            movableElements.forEach(el => {
                el.classList.add('sidebar-active');
                el.classList.remove('sidebar-collapsed');
            });
        }
        // }
    },
    /**
     * زر فتح / تصغير السايدبار
     * مسؤول فقط عن تغيير الحالة (state)
     */
    toggleSidebar() {
        // عكس حالة التصغير
        this.state.isCollapsed = !this.state.isCollapsed;

        // بعد تغيير الحالة، نحدّث الواجهة
        this.applySidebarLayout();
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
    /**
     * التعامل مع النقر على عنصر من القائمة الجانبية
     */
    // async handleAppClick(menu, ev) {
    //     if (menu.actionID && ev && (ev.ctrlKey || ev.metaKey || ev.button === 1)) {
    //         return; 
    //     }
    
    //     if (ev) {
    //         ev.preventDefault();
    //         ev.stopPropagation();
    //     }
    
    //     const liElement = ev?.target.closest('li');
    //     const hasChildren = menu.childrenTree && menu.childrenTree.length > 0;
    
    //     // 1. الانسدال الفوري إذا كانت القائمة مصغرة
    //     if (this.state.isCollapsed) {
    //         this.state.isCollapsed = false;
    //         this.applySidebarLayout();
    //     }
    
    //     // 2. منطق الأكورديون (إغلاق الأشقاء فقط)
    //     if (hasChildren && liElement) {
    //         const parentUl = liElement.closest('ul');
    //         if (parentUl) {
    //             const siblingOpens = parentUl.querySelectorAll(':scope > li.open');
    //             siblingOpens.forEach(el => {
    //                 if (el !== liElement) {
    //                     el.classList.remove('open');
    //                     const nestedSubs = el.querySelectorAll('.open');
    //                     nestedSubs.forEach(nested => nested.classList.remove('open'));
    //                 }
    //             });
    //         }
    
    //         const subMenu = liElement.querySelector(':scope > .sidebar_sub_menu, :scope > ul');
    //         if (subMenu) {
    //             const isOpen = subMenu.classList.contains('open');
    //             subMenu.classList.toggle('open', !isOpen);
    //             liElement.classList.toggle('open', !isOpen);
                
    //             // ✅ إذا كان التطبيق يحمل Action، نقوم بتنفيذ الأكشن + تنظيف القوائم البعيدة
    //             if (menu.actionID) {
    //                 this._cleanupUnrelatedMenus(liElement); // دالة تنظيف مخصصة
    //                 await this.menuService.selectMenu(menu);
    //             }
                
    //             if (!menu.actionID) return;
    //         }
    //         // ✅ إضافة: إذا كان التطبيق (الأب) نفسه يحتوي على Action (مثل تطبيق "المناقشة")
    //         if (menu.actionID) {
    //             this._cleanupUnrelatedMenus(liElement);
    //             await this.menuService.selectMenu(menu);

    //             // إغلاق القائمة في الموبايل عند الضغط على تطبيق له أكشن
    //             if (window.innerWidth <= 768) {
    //                 this.state.isCollapsed = true;
    //                 this.applySidebarLayout();
    //             }
    //         }
    //         if (!menu.actionID) return;
        
    //     }
    
    //     // 3. تنفيذ الأكشن للعناصر النهائية (Leaf Nodes)
    //     if (menu?.id && !hasChildren) {
    //         document.querySelectorAll('.sidebar_panel .active').forEach(el => el.classList.remove('active'));
    //         liElement?.classList.add('active');
    
    //         // ✅ تنظيف كل القوائم التي لا تتبع لهذا المسار
    //         this._cleanupUnrelatedMenus(liElement);
    
    //         await this.menuService.selectMenu(menu);
    
    //         if (window.innerWidth <= 768) {
    //             this.state.isCollapsed = true;
    //             this.applySidebarLayout();
    //         }
    //     }
    // },
    
    
    /**
     * التعامل مع النقر على عنصر من القائمة الجانبية
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
    
        // 1. الانسدال الفوري إذا كانت القائمة مصغرة
        if (this.state.isCollapsed) {
            this.state.isCollapsed = false;
            this.applySidebarLayout();
        }
    
        // 2. منطق الأكورديون (فتح وإغلاق القوائم الفرعية)
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

            // ✅ إضافة هامة: إذا كان العنصر الأب نفسه له Action (مثل تطبيق "المناقشة")
            if (menu.actionID) {
                this._cleanupUnrelatedMenus(liElement);
                await this.menuService.selectMenu(menu);

                // إغلاق السايدبار في الموبايل فوراً عند تنفيذ الأكشن
                if (window.innerWidth <= 768) {
                    this.state.isCollapsed = true;
                    this.applySidebarLayout();
                }
            }
            
            if (!menu.actionID) return;
        }
    
        // 3. تنفيذ الأكشن للعناصر النهائية (Leaf Nodes) التي ليس لها أبناء
        if (menu?.id && !hasChildren) {
            document.querySelectorAll('.sidebar_panel .active').forEach(el => el.classList.remove('active'));
            liElement?.classList.add('active');
    
            this._cleanupUnrelatedMenus(liElement);
            await this.menuService.selectMenu(menu);
    
            // ✅ إغلاق السايدبار في الموبايل عند الضغط على أي اختيار نهائي
            if (window.innerWidth <= 768) {
                this.state.isCollapsed = true;
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

    applyActiveMenuOnLoad() {
        // للحصول علي التطبيق الحالي من ال props
        const currentApp = this.menuService.getCurrentApp();
        if (!currentApp) {
            return;
        }

        // تمييز ايقونة التطبيق الرئيسي للسايدبار
        const appSelector = `.sidebar_menu > li[data-menu-xmlid="${currentApp.xmlid}"]`;
        const appLi = document.querySelector(appSelector);

        if (appLi) {
            appLi.classList.add('active');
            // اذا كنت تريد فتح القائمة تلقائيا عند التحميل
            const subMneu = appLi.querySelector('.sidebar_sub_menu');
            if (subMneu) {
                subMneu.classList.add('open');
                appLi.classList.add('open');
            }
        }

        // تمييز العنصر الفرعي المفتوح حاليا
        const currentMenu = this.menuService.getCurrentMenu();
        if (currentMenu) {
            const actionSelector = `li[data-menu-xmlid="${currentMenu.xmlid}"]`;
            // نبحث داخل السايدبار فقط
            const actionLi = document.querySelector(`.sidebar_panel ${actionSelector}`);

            if (actionLi) {
                actionLi.classList.add('active');

                // تأكد من فتح كل الآباء وصولاً لهذا العنصر
                let parent = actionLi.parentElement;
                while (parent && !parent.classList.contains('sidebar_menu')) {
                    if (parent.classList.contains('sidebar_sub_menu')) {
                        parent.classList.add('open');
                        parent.parentElement.classList.add('open', 'active'); // تمييز الأب أيضاً
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




