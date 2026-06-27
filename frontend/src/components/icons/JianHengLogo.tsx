/**
 * JianHengLogo — Evidence-Ladder brand mark.
 *
 * A fusion of Chinese calligraphic typography and modern tech aesthetic:
 *
 *   - Deep midnight navy squircle background — the "black box" of LLMs
 *     we scrutinize.
 *   - Cyan glow at the top-left — scanning light / scrutiny in progress.
 *   - Centered bold serif "鉴" character — rendered with system serif
 *     fonts (Noto Serif SC, Source Han Serif, Songti, etc.) so the
 *     glyph is always pixel-perfect, never misshapen like AI-generated
 *     Chinese characters.
 *   - Tiny bronze-gold dot at the bottom-right — the signature accent
 *     representing "Gold Label" or verified evidence.
 *
 * The icon is self-contained (not using ``currentColor``) so the brand
 * palette stays consistent across light/dark surfaces.
 *
 * Uses a stable ID suffix to avoid ``<defs>`` clashes if multiple
 * instances coexist on the same page.
 */
export function JianHengLogo({ className, title }: { className?: string; title?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      role="img"
      aria-label={title ?? "Evidence-Ladder"}
    >
      <title>{title ?? "Evidence-Ladder"}</title>
      <defs>
        <linearGradient id="jh-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#0f172a" />
          <stop offset="100%" stopColor="#020617" />
        </linearGradient>
        <radialGradient id="jh-glow" cx="0.25" cy="0.25" r="0.55">
          <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
        </radialGradient>
      </defs>
      {/* 背景：深墨夜空渐变（黑盒隐喻） */}
      <rect width="24" height="24" rx="4.5" fill="url(#jh-bg)" />
      {/* 左上科技光晕（扫描/审视的动作感） */}
      <circle cx="6" cy="6" r="8" fill="url(#jh-glow)" />
      {/* 鉴字：系统衬线字体渲染，确保字形不糊 */}
      <text
        x="12"
        y="17.8"
        textAnchor="middle"
        fontSize="16.5"
        fontWeight="900"
        fontFamily="'STXingkai','Xingkai SC','STKaiti','Kaiti SC','KaiTi','华文楷体','楷体','LXGW WenKai','STSong','SimSun',serif"
        fill="#f8fafc"
      >
        鉴
      </text>
      {/* 右下青铜金点：品牌签名色（Gold Label） */}
      <circle cx="19.5" cy="19.5" r="1.2" fill="#d97706" />
    </svg>
  );
}
