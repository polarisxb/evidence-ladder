import { NavLink } from "react-router-dom";
import { Home, Plus, Layers, MessageSquare, GitCompare, Settings, Info, PlugZap, FlaskConical, Globe, BrainCircuit } from "lucide-react";
import { useLocale } from "../../i18n";

export function Sidebar() {
  const { t, locale, setLocale } = useLocale();

  const navItems = [
    { to: "/", label: t("nav.dashboard"), icon: Home },
    { to: "/scan/new", label: t("nav.newScan"), icon: Plus },
    { to: "/autotest", label: t("nav.autotest"), icon: BrainCircuit },
    { to: "/adapters", label: t("nav.adapters"), icon: PlugZap },
    { to: "/templates", label: t("nav.templates"), icon: Layers },
    { to: "/playground", label: t("nav.playground"), icon: MessageSquare },
    { to: "/compare", label: t("nav.compare"), icon: GitCompare },
    { to: "/judge-calibration", label: t("nav.calibration"), icon: FlaskConical },
  ];

  const sysItems = [
    { to: "/settings", label: t("nav.settings"), icon: Settings },
    { to: "/about", label: t("nav.about"), icon: Info },
  ];

  return (
    <aside className="fixed left-0 top-0 h-screen w-[200px] bg-white flex flex-col py-6 px-3.5">
      {/* Brand Wordmark: pure typography, no icon. Serif face for a
          classical, editorial feel — closer to premium print brands than
          to generic SaaS icon-based logos. The bronze-gold dot separator
          is the single visual flourish, echoing "Gold Label" in
          calibration. */}
      <div className="flex flex-col items-start gap-0.5 px-2 pb-6">
        <div className="flex items-baseline gap-1">
          <span
            className="text-[19px] font-bold text-gray-900 tracking-[0.06em]"
            style={{ fontFamily: '"Noto Serif SC","Source Han Serif SC","Songti SC",serif' }}
          >
            Evidence
          </span>
          <span className="text-amber-600 text-[15px] font-bold leading-none -translate-y-0.5">·</span>
          <span
            className="text-[19px] font-bold text-gray-900 tracking-[0.06em]"
            style={{ fontFamily: '"Noto Serif SC","Source Han Serif SC","Songti SC",serif' }}
          >
            Ladder
          </span>
        </div>
        <span className="text-[9px] text-gray-400 font-medium tracking-[0.25em] uppercase">E0–E5 Evidence Ladder</span>
      </div>

      <nav className="flex-1 space-y-0.5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] font-medium transition-colors ${
                isActive
                  ? "text-gray-900 bg-gray-100"
                  : "text-gray-400 hover:text-gray-600"
              }`
            }
          >
            <item.icon className="w-4 h-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-0.5 pt-4 border-t border-gray-100">
        {sysItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] font-medium transition-colors ${
                isActive
                  ? "text-gray-900 bg-gray-100"
                  : "text-gray-400 hover:text-gray-600"
              }`
            }
          >
            <item.icon className="w-4 h-4" />
            {item.label}
          </NavLink>
        ))}

        {/* Language switcher */}
        <div className="flex items-center gap-1.5 px-2.5 py-2 mt-1">
          <Globe className="w-3.5 h-3.5 text-gray-400" />
          <button
            type="button"
            onClick={() => setLocale("zh")}
            className={`text-[12px] font-medium transition-colors ${
              locale === "zh" ? "text-gray-900" : "text-gray-400 hover:text-gray-600"
            }`}
          >
            中
          </button>
          <span className="text-gray-300 text-[12px]">/</span>
          <button
            type="button"
            onClick={() => setLocale("en")}
            className={`text-[12px] font-medium transition-colors ${
              locale === "en" ? "text-gray-900" : "text-gray-400 hover:text-gray-600"
            }`}
          >
            EN
          </button>
        </div>
      </div>
    </aside>
  );
}
