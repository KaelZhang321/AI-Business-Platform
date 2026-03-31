// 会议 BI 适配页：负责按需挂载 legacy 样式、切换桌面/移动布局，并提供返回工作台入口。
import React from 'react';
import { ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import Dashboard from '../legacy-meeting-bi/pages/Dashboard';
import MobileDashboard from '../legacy-meeting-bi/pages/mobile/MobileDashboard';
import { useLegacyStyleLinks } from '../legacy-meeting-bi/hooks/useLegacyStyleLinks';
import { PAGE_PATHS } from '../navigation';
import globalCssUrl from '../legacy-meeting-bi/styles/global.css?url';
import bigscreenCssUrl from '../legacy-meeting-bi/styles/bigscreen.css?url';
import mobileCssUrl from '../legacy-meeting-bi/styles/mobile.css?url';

const MOBILE_BREAKPOINT = 1200;

function useIsMobileMeetingBi() {
  const [isMobile, setIsMobile] = React.useState(() => window.innerWidth < MOBILE_BREAKPOINT);

  React.useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return isMobile;
}

export function MeetingBiView() {
  const navigate = useNavigate();
  const isMobile = useIsMobileMeetingBi();
  const styleUrls = React.useMemo(
    () => [globalCssUrl, isMobile ? mobileCssUrl : bigscreenCssUrl],
    [isMobile],
  );

  useLegacyStyleLinks(styleUrls);

  return (
    <div className="relative min-h-screen overflow-auto bg-[#050f24]">
      <button
        type="button"
        onClick={() => navigate(PAGE_PATHS.dashboard)}
        className="fixed left-0 top-0 z-[1200] inline-flex items-center gap-2 rounded-full border border-cyan-300/20 bg-slate-950/70 px-4 py-2 text-sm font-medium text-cyan-50 shadow-lg backdrop-blur-md transition hover:border-cyan-300/40 hover:bg-slate-900/85"
      >
        <ArrowLeft className="h-4 w-4" />
        返回工作台
      </button>

      {isMobile ? <MobileDashboard /> : <Dashboard />}
    </div>
  );
}
