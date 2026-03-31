// 左侧导航栏：负责页面切换、主题切换以及当前登录用户展示。
import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Home, LayoutDashboard, Sparkles, Search, Bell, Settings,
  Sun, Moon, LogOut, Menu, ChevronRight, Activity
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { AppPage, NavigationIcon, NavigationItemDefinition } from '../navigation';
import {
  FOOTER_NAVIGATION_ITEMS,
  isNavigationGroupActive,
  NAVIGATION_ITEMS,
  PAGE_PATHS,
  PAGE_TITLES,
} from '../navigation';

interface NavItemProps {
  icon?: LucideIcon;
  label: string;
  active?: boolean;
  badge?: number;
  isSubItem?: boolean;
  isDark?: boolean;
  isCollapsed?: boolean;
  hasArrow?: boolean;
  isLastSubItem?: boolean;
  isOpen?: boolean;
  onClick?: () => void;
}

const ICON_MAP: Record<NavigationIcon, LucideIcon> = {
  home: Home,
  'layout-dashboard': LayoutDashboard,
  sparkles: Sparkles,
  search: Search,
  bell: Bell,
  settings: Settings,
};

function NavItem({ icon: Icon, label, active, badge, isSubItem, isDark, isCollapsed, hasArrow, isOpen, onClick }: NavItemProps) {
  if (isCollapsed && isSubItem) return null;

  return (
    <div className="relative">
      {isSubItem && !isCollapsed && (
        <div className={`absolute left-[-1rem] top-1/2 w-2 h-[1px] ${isDark ? 'bg-slate-700' : 'bg-slate-200'}`}></div>
      )}

      <button
        onClick={onClick}
        className={`w-full flex items-center justify-between transition-all duration-300 group relative ${isCollapsed ? 'px-0 justify-center py-3' : 'px-4 rounded-xl'
          } ${active
            ? (isDark
              ? 'text-white bg-[#323B4E] shadow-[0_0_15px_rgba(42,53,213,0.15)] ring-1 ring-white/10'
              : 'text-brand font-bold bg-slate-100 shadow-sm')
            : (isDark ? 'text-slate-400 hover:text-white hover:bg-[#1F222E]' : 'text-slate-500 hover:text-slate-900 hover:bg-slate-50')
          } ${isSubItem && !isCollapsed ? 'py-2 mb-1' : (active && !isCollapsed ? 'py-4 mb-2' : 'py-2.5 mb-1')}`}>
        <div className={`flex items-center ${isCollapsed ? 'justify-center' : ''}`}>
          {Icon && (
            <div className={`transition-colors duration-300 ${isCollapsed ? '' : 'mr-3'} ${active
              ? (isDark ? 'text-white' : 'text-brand')
              : (isDark ? (isOpen ? 'text-white' : 'text-slate-500 group-hover:text-slate-300') : 'text-slate-400 group-hover:text-slate-600')
              } ${isCollapsed && active ? (isDark ? 'bg-brand p-2 rounded-xl text-white shadow-lg shadow-brand/20' : 'bg-brand p-2 rounded-xl text-white shadow-lg shadow-brand/20') : ''}`}>
              <Icon className="w-5 h-5" />
            </div>
          )}
          {!isCollapsed && (
            <span className={`${isSubItem ? 'text-xs' : 'text-sm'} tracking-wide ${active ? 'font-medium' : ''} ${!active && isOpen ? 'text-white' : ''}`}>{label}</span>
          )}
        </div>

        {!isCollapsed && (
          <div className="flex items-center space-x-2">
            {badge && (
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full transition-colors duration-300 ${active ? 'bg-brand text-white' : (isDark ? 'bg-slate-800 text-slate-400' : 'bg-brand-light text-brand')
                }`}>
                {badge}
              </span>
            )}
            {hasArrow && (
              <ChevronRight className={`w-3.5 h-3.5 transition-transform ${isOpen ? 'rotate-90 text-white' : ''}`} />
            )}
          </div>
        )}
      </button>
    </div>
  );
}

interface SidebarProps {
  isDarkMode: boolean;
  setIsDarkMode: (val: boolean) => void;
  isCollapsed: boolean;
  setIsCollapsed: (val: boolean) => void;
  currentPage: AppPage;
  userName?: string;
  userRole?: string;
  onLogout: () => void;
}

export function Sidebar({
  isDarkMode,
  setIsDarkMode,
  isCollapsed,
  setIsCollapsed,
  currentPage,
  userName,
  userRole,
  onLogout,
}: SidebarProps) {
  const navigate = useNavigate();
  const [logoUrl, setLogoUrl] = React.useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const goToPage = React.useCallback((page: AppPage) => {
    navigate(PAGE_PATHS[page]);
  }, [navigate]);

  const handleLogoUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setLogoUrl(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const renderNavigationItem = (item: NavigationItemDefinition) => {
    const icon = item.icon ? ICON_MAP[item.icon] : undefined;

    if (item.children && item.children.length > 0) {
      return (
        <div className="pt-2" key={item.page}>
          <NavItem
            icon={icon}
            label={item.label}
            isDark={isDarkMode}
            isCollapsed={isCollapsed}
            hasArrow={!isCollapsed}
            active={isNavigationGroupActive(currentPage, item.page)}
            onClick={() => goToPage(item.page)}
          />
          {!isCollapsed && (
            <div className="mt-1 ml-9 space-y-0 relative">
              <div className={`absolute left-[-1rem] top-0 bottom-5 w-[1px] ${isDarkMode ? 'bg-slate-700' : 'bg-slate-200'}`}></div>
              {item.children.map((childPage) => (
                <div key={childPage}>
                  <NavItem
                    label={PAGE_TITLES[childPage]}
                    isSubItem
                    isDark={isDarkMode}
                    active={currentPage === childPage}
                    onClick={() => goToPage(childPage)}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    return (
      <div key={item.page}>
        <NavItem
          icon={icon}
          label={item.label}
          badge={item.badge}
          active={currentPage === item.page}
          isDark={isDarkMode}
          isCollapsed={isCollapsed}
          onClick={() => goToPage(item.page)}
        />
      </div>
    );
  };

  return (
    <aside className={`flex flex-col relative overflow-hidden z-10 shadow-sm shrink-0 transition-all duration-300 ${isCollapsed ? 'w-20' : 'w-72'} ${isDarkMode ? 'bg-[#0F111A] border-r border-slate-800' : 'bg-white border-r border-slate-100'}`}>

      {/* 1. Top Controls (Dots) */}
      <div className="h-12 flex items-center justify-end px-6 shrink-0">
        {/* <div className="flex space-x-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-[#FF5F57]"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-[#FFBD2E]"></div>
          <div className="w-2.5 h-2.5 rounded-full bg-[#28C840]"></div>
        </div> */}
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          className={`p-1.5 rounded-lg transition-colors ${isDarkMode ? 'hover:bg-slate-800 text-slate-400' : 'hover:bg-slate-100 text-slate-500'}`}
        >
          <Menu className="w-4 h-4" />
        </button>
      </div>

      {/* 2. Logo & Search */}
      <div className={`flex items-center px-6 mb-6 transition-all duration-300 ${isCollapsed ? 'justify-center' : 'justify-between'}`}>
        <button
          type="button"
          aria-label="上传工作台 Logo"
          className="flex items-center cursor-pointer"
          onClick={() => fileInputRef.current?.click()}
        >
          <input type="file" ref={fileInputRef} onChange={handleLogoUpload} className="hidden" accept="image/*" />
          <div className="w-12 h-12 bg-brand rounded-2xl flex items-center justify-center text-white shadow-lg shadow-brand/20 shrink-0 overflow-hidden">
            {logoUrl ? (
              <img src={logoUrl} alt="Logo" className="w-full h-full object-cover" />
            ) : (
              <Activity className="w-7 h-7" />
            )}
          </div>
          {!isCollapsed && (
            <span className={`ml-3 font-bold text-lg tracking-tight ${isDarkMode ? 'text-white' : 'text-slate-900'}`}>AI业务工作台</span>
          )}
        </button>
        {!isCollapsed && (
          <button className={`p-2 rounded-xl transition-colors ${isDarkMode ? 'text-slate-400 hover:bg-slate-800' : 'text-slate-400 hover:bg-slate-100'}`}>
            <Search className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* 3. Main Navigation */}
      <nav className="flex-1 px-4 space-y-1 overflow-y-auto relative z-10 custom-scrollbar">
        {NAVIGATION_ITEMS.map((item) => renderNavigationItem(item))}
      </nav>

      {/* 4. Bottom Sections (Notifications & Settings) */}
      <div className={`px-4 py-4 space-y-1 relative z-10 shrink-0`}>
        {FOOTER_NAVIGATION_ITEMS.map((item) => renderNavigationItem(item))}
      </div>

      {/* 5. Theme Switcher & User Profile */}
      <div className={`p-4 border-t relative z-10 shrink-0 ${isDarkMode ? 'border-slate-800' : 'border-slate-100'}`}>

        {!isCollapsed && (
          <div className={`flex items-center p-1 rounded-2xl mb-4 ${isDarkMode ? 'bg-[#090B11]' : 'bg-slate-100'}`}>
            <button
              onClick={() => setIsDarkMode(false)}
              className={`flex-1 flex items-center justify-center space-x-2 py-2 rounded-xl text-xs font-bold transition-all ${!isDarkMode ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-300'}`}
            >
              <Sun className="w-3.5 h-3.5" />
              <span>Light</span>
            </button>
            <button
              onClick={() => setIsDarkMode(true)}
              className={`flex-1 flex items-center justify-center space-x-2 py-2 rounded-xl text-xs font-bold transition-all ${isDarkMode ? 'bg-brand text-white shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
            >
              <Moon className="w-3.5 h-3.5" />
              <span>Dark</span>
            </button>
          </div>
        )}

        <div className={`flex items-center p-3 rounded-2xl transition-all duration-300 ${isCollapsed ? 'justify-center' : 'justify-between'} ${isDarkMode ? 'bg-[#1F222E]' : 'bg-slate-50'}`}>
          <div className="flex items-center min-w-0">
            <div className="relative shrink-0">
              <img src="https://picsum.photos/seed/avatar3/100/100" alt="User" className="w-10 h-10 rounded-xl object-cover shadow-sm" referrerPolicy="no-referrer" />
              <span className="absolute -bottom-1 -right-1 w-3 h-3 bg-brand border-2 border-white rounded-full"></span>
            </div>
            {!isCollapsed && (
              <div className="ml-3 flex flex-col min-w-0">
                <span className={`text-sm font-bold truncate ${isDarkMode ? 'text-white' : 'text-slate-900'}`}>
                  {userName || '未命名用户'}
                </span>
                <span className={`text-xs truncate ${isDarkMode ? 'text-slate-500' : 'text-slate-400'}`}>
                  {userRole || '访客'}
                </span>
              </div>
            )}
          </div>
          {!isCollapsed && (
            <button onClick={onLogout} className={`p-1.5 rounded-lg transition-colors ${isDarkMode ? 'text-slate-400 hover:bg-slate-700 hover:text-white' : 'text-slate-400 hover:bg-slate-200'}`}>
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}
