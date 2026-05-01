import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { KeyRound, LockKeyhole, RefreshCw, Trash2 } from "lucide-react";
import { clearStoredAppApiKey, getStoredAppApiKey, hasEmbeddedAppApiKey, setStoredAppApiKey } from "../../api/client";
import { useToast } from "../Toast";
import { useLocale } from "../../i18n";
import { Sidebar } from "./Sidebar";

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const { toast } = useToast();
  const { t } = useLocale();
  const location = useLocation();
  const [authRequired, setAuthRequired] = useState(false);
  const [apiKey, setApiKey] = useState(() => getStoredAppApiKey());
  const embeddedKey = hasEmbeddedAppApiKey();

  useEffect(() => {
    const handleAuthRequired = () => setAuthRequired(true);
    const handleKeyUpdated = () => setApiKey(getStoredAppApiKey());

    window.addEventListener("app-api-auth-required", handleAuthRequired as EventListener);
    window.addEventListener("app-api-key-updated", handleKeyUpdated as EventListener);
    return () => {
      window.removeEventListener("app-api-auth-required", handleAuthRequired as EventListener);
      window.removeEventListener("app-api-key-updated", handleKeyUpdated as EventListener);
    };
  }, []);

  const showAuthBanner = !embeddedKey && (authRequired || apiKey.length > 0);

  function handleSaveApiKey() {
    if (!apiKey.trim()) {
      toast("warning", t("layout.enterKey"));
      return;
    }
    setStoredAppApiKey(apiKey);
    setAuthRequired(false);
    toast("success", t("layout.saveKey"));
    window.location.reload();
  }

  function handleClearApiKey() {
    clearStoredAppApiKey();
    setApiKey("");
    setAuthRequired(false);
    toast("success", t("common.success"));
  }

  return (
    <div className="flex min-h-screen bg-[#fafafa]">
      <Sidebar />
      <main className="flex-1 p-12 ml-[200px] overflow-auto">
        <div key={location.pathname} className="animate-fade-in space-y-4">
          {showAuthBanner && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 shadow-sm">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-white border border-amber-200 flex items-center justify-center shrink-0">
                  <LockKeyhole className="w-5 h-5 text-amber-700" />
                </div>
                <div className="flex-1 min-w-0 space-y-3">
                  <div>
                    <p className="text-sm font-semibold text-amber-900">{t("layout.apiKeyRequired")}</p>
                    <p className="text-xs text-amber-800 mt-1">
                      {t("layout.apiKeyDesc")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <div className="relative flex-1 min-w-[280px]">
                      <KeyRound className="w-4 h-4 text-amber-700 absolute left-3 top-1/2 -translate-y-1/2" />
                      <input
                        type="password"
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder={t("layout.enterKey")}
                        className="w-full pl-9 pr-3 py-2 rounded-xl border border-amber-200 bg-white text-sm text-gray-900 placeholder:text-gray-400 focus:border-amber-400 focus:outline-none focus:ring-1 focus:ring-amber-200"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={handleSaveApiKey}
                      className="px-4 py-2 rounded-xl bg-gray-900 text-white text-sm hover:bg-gray-800 transition-colors"
                    >
                      {t("layout.saveKey")}
                    </button>
                    <button
                      type="button"
                      onClick={() => window.location.reload()}
                      className="px-3 py-2 rounded-xl border border-amber-200 bg-white text-amber-900 text-sm hover:bg-amber-100 transition-colors"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                    {apiKey.length > 0 && (
                      <button
                        type="button"
                        onClick={handleClearApiKey}
                        className="px-3 py-2 rounded-xl border border-rose-200 bg-white text-rose-700 text-sm hover:bg-rose-50 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
          <div>{children}</div>
        </div>
      </main>
    </div>
  );
}
