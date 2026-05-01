interface ProviderIconProps {
  type: string;
  size?: number;
  className?: string;
}

interface ProviderAssetSpec {
  src?: string;
  alt: string;
  background: string;
  border: string;
  padding?: number;
  roundImage?: boolean;
  objectFit?: "contain" | "cover";
  offsetX?: number;
  offsetY?: number;
  label?: string;
  labelColor?: string;
}

const PROVIDER_ASSETS: Record<string, ProviderAssetSpec> = {
  openai: {
    src: "/provider-logos/openai.svg",
    alt: "OpenAI",
    background: "#ffffff",
    border: "rgba(15,23,42,0.10)",
    padding: 0,
    roundImage: true,
  },
  deepseek: {
    src: "/provider-logos/deepseek.ico",
    alt: "DeepSeek",
    background: "#ffffff",
    border: "rgba(37,99,235,0.18)",
    padding: 2,
  },
  glm: {
    src: "/provider-logos/zai.svg",
    alt: "GLM Code",
    background: "#ffffff",
    border: "rgba(15,23,42,0.10)",
    padding: 0,
    objectFit: "contain",
  },
  minimax: {
    src: "/provider-logos/minimax.png",
    alt: "MiniMax",
    background: "#ffffff",
    border: "rgba(244,63,94,0.18)",
    padding: 0,
    roundImage: true,
    objectFit: "cover",
  },
  gemini: {
    src: "/provider-logos/gemini.svg",
    alt: "Gemini",
    background: "#ffffff",
    border: "rgba(99,102,241,0.18)",
    padding: 2,
  },
  qwen: {
    src: "/provider-logos/qwen.svg",
    alt: "Qwen",
    background: "#ffffff",
    border: "rgba(249,115,22,0.18)",
    padding: 2,
  },
  claude: {
    src: "/provider-logos/claude.ico",
    alt: "Claude",
    background: "#ffffff",
    border: "rgba(180,83,9,0.18)",
    padding: 2,
  },
  nvidia: {
    src: "/provider-logos/nvidia.ico",
    alt: "NVIDIA NIM",
    background: "#000000",
    border: "rgba(118,185,0,0.25)",
    padding: 2,
  },
  mistral: {
    src: "/provider-logos/mistral.ico",
    alt: "Mistral AI",
    background: "#ffffff",
    border: "rgba(255,112,0,0.20)",
    padding: 2,
  },
  groq: {
    src: "/provider-logos/groq.png",
    alt: "Groq",
    background: "#f55036",
    border: "rgba(245,80,54,0.20)",
    padding: 3,
    roundImage: true,
  },
  moonshot: {
    src: "/provider-logos/moonshot.ico",
    alt: "Moonshot",
    background: "#ffffff",
    border: "rgba(99,102,241,0.20)",
    padding: 2,
  },
  doubao: {
    src: "/provider-logos/doubao.png",
    alt: "豆包",
    background: "#ffffff",
    border: "rgba(0,150,255,0.18)",
    padding: 2,
  },
  yi: {
    src: "/provider-logos/yi.ico",
    alt: "Yi",
    background: "#ffffff",
    border: "rgba(124,58,237,0.20)",
    padding: 2,
  },
  baichuan: {
    src: "/provider-logos/baichuan.ico",
    alt: "百川",
    background: "#ffffff",
    border: "rgba(37,99,235,0.18)",
    padding: 2,
  },
  stepfun: {
    src: "/provider-logos/stepfun.png",
    alt: "阶跃星辰",
    background: "#ffffff",
    border: "rgba(13,148,136,0.20)",
    padding: 2,
  },
  siliconflow: {
    src: "/provider-logos/siliconflow.png",
    alt: "硅基流动",
    background: "#ffffff",
    border: "rgba(14,165,233,0.20)",
    padding: 3,
  },
  xai: {
    src: "/provider-logos/xai.png",
    alt: "Grok",
    background: "#000000",
    border: "rgba(255,255,255,0.15)",
    padding: 3,
  },
  together: {
    src: "/provider-logos/together.ico",
    alt: "Together AI",
    background: "#ffffff",
    border: "rgba(109,40,217,0.20)",
    padding: 2,
  },
  custom: {
    alt: "Custom API",
    background: "linear-gradient(135deg, #6b7280 0%, #4b5563 100%)",
    border: "rgba(255,255,255,0.12)",
    label: "API",
    labelColor: "#ffffff",
  },
};

function getProviderSpec(type: string): ProviderAssetSpec {
  return PROVIDER_ASSETS[type.trim().toLowerCase()] ?? PROVIDER_ASSETS.custom;
}

function resolveLabelSize(size: number, label: string): number {
  if (label.length >= 3) return Math.max(8, Math.round(size * 0.31));
  if (label.length === 2) return Math.max(9, Math.round(size * 0.37));
  return Math.max(11, Math.round(size * 0.52));
}

export function ProviderIcon({ type, size = 28, className = "" }: ProviderIconProps) {
  const spec = getProviderSpec(type);
  const radius = Math.max(7, Math.round(size * 0.28));
  const padding = spec.padding ?? 0;
  const imageSize = Math.max(1, size - padding * 2);
  const hasImageOffset = Boolean(spec.offsetX || spec.offsetY);

  return (
    <div
      className={`inline-flex shrink-0 items-center justify-center overflow-hidden shadow-sm ${className}`}
      style={{
        width: size,
        height: size,
        borderRadius: radius,
        background: spec.background,
        border: `1px solid ${spec.border}`,
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.12)",
      }}
      aria-label={`${spec.alt} provider icon`}
      title={spec.alt}
    >
      {spec.src ? (
        <img
          src={spec.src}
          alt={spec.alt}
          style={{
            width: imageSize,
            height: imageSize,
            objectFit: spec.objectFit ?? "contain",
            borderRadius: spec.roundImage ? Math.max(0, radius - 1) : undefined,
            transform: hasImageOffset
              ? `translate(${spec.offsetX ?? 0}px, ${spec.offsetY ?? 0}px)`
              : undefined,
            display: "block",
          }}
        />
      ) : (
        <span
          style={{
            color: spec.labelColor ?? "#ffffff",
            fontSize: resolveLabelSize(size, spec.label ?? ""),
            fontWeight: 800,
            lineHeight: 1,
            letterSpacing: "-0.04em",
            fontFamily: "Inter, Segoe UI, Arial, sans-serif",
            textTransform: "uppercase",
          }}
        >
          {spec.label}
        </span>
      )}
    </div>
  );
}

export function ProviderIconSmall({ type, className = "" }: { type: string; className?: string }) {
  return <ProviderIcon type={type} size={24} className={className} />;
}
