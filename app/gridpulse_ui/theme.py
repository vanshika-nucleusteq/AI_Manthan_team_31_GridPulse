"""Design tokens (dark default, light), global CSS and the Plotly template for the dashboard."""

from __future__ import annotations

from typing import Any

THEMES: dict[str, dict[str, str]] = {
    "dark": {
        "background": "#060A12",
        "foreground": "#EEF2F7",
        "card": "#0D131C",
        "popover": "#10171F",
        "primary": "#C1F354",
        "primary-foreground": "#101A05",
        "muted": "#192029",
        "muted-foreground": "#969FAB",
        "accent": "#212E12",
        "accent-foreground": "#CEF682",
        "destructive": "#FC5855",
        "warning": "#FCB442",
        "success": "#66DA85",
        "border": "#222933",
        "input": "#272E38",
        "chart-2": "#43CAE7",
        "chart-3": "#FCB442",
        "chart-5": "#6A727D",
        "sidebar": "#090F16",
        "sidebar-accent": "#0B2425",
        "sidebar-border": "#1E252E",
        "glow": "rgba(193,243,84,0.22)",
    },
    "light": {
        "background": "#F7F6F0",
        "foreground": "#10171F",
        "card": "#FEFDFB",
        "popover": "#FEFDFB",
        "primary": "#21771A",
        "primary-foreground": "#F9FBF4",
        "muted": "#EBEAE2",
        "muted-foreground": "#565E69",
        "accent": "#DDEED4",
        "accent-foreground": "#11370E",
        "destructive": "#D8151E",
        "warning": "#D37900",
        "success": "#1C8742",
        "border": "#DDDBD2",
        "input": "#DDDBD2",
        "chart-2": "#007FA6",
        "chart-3": "#D37900",
        "chart-5": "#8A919B",
        "sidebar": "#F2F0E9",
        "sidebar-accent": "#E4E8DA",
        "sidebar-border": "#DDDBD2",
        "glow": "rgba(33,119,26,0.18)",
    },
}

FONTS = (
    "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700"
    "&family=Space+Grotesk:wght@400;500;600;700&display=swap"
)

BASE_CSS = """
@import url('{fonts}');
:root {{ {tokens} --sans: 'Space Grotesk', ui-sans-serif, system-ui, sans-serif;
  --mono: 'JetBrains Mono', ui-monospace, monospace; }}
html, body, .stApp, [data-testid="stAppViewContainer"] {{ background: var(--background) !important;
  color: var(--foreground); font-family: var(--sans); }}
.stApp *:not([data-testid="stIconMaterial"]) {{ font-family: var(--sans); }}
[data-testid="stMarkdownContainer"] p {{ font-size: inherit; line-height: 1.5; }}
[data-testid="stHeader"], #MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"] {{ display: none !important; }}
[data-testid="stMainBlockContainer"], .block-container {{ max-width: 1500px; padding: 0 2rem 3rem;
  margin: 0 auto; }}
[data-testid="stVerticalBlock"] {{ gap: 24px; }}
.stApp p, .stApp span, .stApp div {{ color: inherit; }}
.mono, .mono * {{ font-family: var(--mono) !important; font-variant-numeric: tabular-nums; }}
.eyebrow {{ font-family: var(--mono) !important; font-size: 11px !important; text-transform: uppercase;
  letter-spacing: .14em; color: var(--muted-foreground); margin: 0 0 4px; }}
.muted {{ color: var(--muted-foreground) !important; }}

/* sidebar */
[data-testid="stSidebar"] {{ background: var(--sidebar) !important; border-right: 1px solid
  var(--sidebar-border); width: 256px !important; min-width: 256px !important; }}
[data-testid="stSidebar"] > div {{ padding: 20px 16px; }}
[data-testid="stSidebarHeader"], [data-testid="stSidebarCollapseButton"] {{ display: none; }}
[data-testid="stSidebarUserContent"] {{ padding: 0 !important; display: flex; flex-direction: column;
  min-height: calc(100vh - 40px); }}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{ gap: 4px; }}
.logo {{ display: flex; align-items: center; gap: 10px; margin-bottom: 36px; }}
.logo-mark {{ width: 36px; height: 36px; border-radius: 12px; background: var(--primary);
  display: flex; align-items: center; justify-content: center; color: var(--primary-foreground); }}
.logo b {{ display: block; font-size: 14px; font-weight: 700; letter-spacing: -.01em; color: var(--foreground); }}
[data-testid="stSidebar"] .eyebrow {{ color: var(--muted-foreground) !important; opacity: 1; }}
.logo small {{ font-family: var(--mono) !important; font-size: 10px; text-transform: uppercase;
  letter-spacing: .18em; color: var(--muted-foreground); }}
[class*="st-key-nav_"] button {{ width: 100%; justify-content: flex-start; background: transparent;
  border: none; border-radius: 12px; padding: 10px 12px; color: var(--muted-foreground);
  font-weight: 500; font-size: 14px; min-height: 0; }}
[class*="st-key-nav_"] button:hover {{ background: color-mix(in srgb, var(--sidebar-accent) 60%,
  transparent); color: var(--foreground); border: none; }}
[class*="st-key-nav_"] button p {{ font-size: 14px; }}

/* live dot */
.live {{ position: relative; display: inline-flex; width: 8px; height: 8px; flex: none; }}
.live::before, .live::after {{ content: ""; position: absolute; inset: 0; border-radius: 999px;
  background: var(--primary); }}
.live::before {{ animation: ping 1.4s cubic-bezier(0,0,.2,1) infinite; opacity: .6; }}
@keyframes ping {{ 75%, 100% {{ transform: scale(2.2); opacity: 0; }} }}

/* header */
.st-key-header {{ border-bottom: 1px solid var(--border); padding: 18px 0 16px; margin-bottom: 8px;
  position: sticky; top: 0; z-index: 20; background: color-mix(in srgb, var(--background) 80%,
  transparent); backdrop-filter: blur(16px); }}
.st-key-header [data-testid="stHorizontalBlock"] {{ align-items: center; }}
.crumb h1 {{ font-size: 20px !important; font-weight: 600 !important; letter-spacing: -.01em;
  margin: 2px 0 0 !important; padding: 0 !important; color: var(--foreground) !important; }}
.hdr-right {{ display: flex; align-items: center; justify-content: flex-end; gap: 10px; flex-wrap: wrap; }}
.chip {{ display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; padding: 6px 12px;
  font-size: 12px; border: 1px solid var(--border); background: var(--card);
  color: var(--muted-foreground); white-space: nowrap; }}
.chip.live-chip {{ background: var(--accent); color: var(--accent-foreground); font-weight: 500;
  border-color: color-mix(in srgb, var(--primary) 30%, transparent); }}
.st-key-day_select label {{ display: none; }}
.st-key-day_select [data-baseweb="select"] > div {{ border-radius: 999px; background: var(--card);
  border: 1px solid var(--border); min-height: 34px; font-family: var(--mono); font-size: 12px; }}
.st-key-day_select [data-baseweb="select"] * {{ font-family: var(--mono) !important; font-size: 12px; }}

/* pills: zone, anomaly type, theme */
[data-testid="stButtonGroup"] {{ gap: 4px; }}
[data-testid="stBaseButton-pills"], [data-testid="stBaseButton-pillsActive"],
[data-testid="stBaseButton-segmented_control"], [data-testid="stBaseButton-segmented_controlActive"] {{
  border-radius: 999px !important; padding: 4px 10px !important; min-height: 0 !important;
  font-size: 12px !important; font-weight: 500; border: none !important;
  background: transparent !important; color: var(--muted-foreground) !important; }}
[data-testid="stBaseButton-pills"] p, [data-testid="stBaseButton-pillsActive"] p {{ font-size: 12px; }}
[data-testid="stBaseButton-pills"]:hover {{ background: var(--muted) !important;
  color: var(--foreground) !important; }}
[data-testid="stBaseButton-pillsActive"] {{ background: var(--foreground) !important;
  color: var(--background) !important; }}
.st-key-theme_ctl {{ display: flex; justify-content: flex-end; }}
.st-key-theme_ctl [data-testid="stButtonGroup"] {{ width: fit-content; flex-wrap: nowrap; margin-left: auto; border: 1px solid var(--border); border-radius: 999px;
  padding: 3px; background: color-mix(in srgb, var(--muted) 60%, transparent); }}
.st-key-theme_ctl [data-testid="stBaseButton-segmented_controlActive"] {{ background: var(--{active_bg})
  !important; color: var(--{active_fg}) !important; }}
.st-key-theme_ctl label {{ display: none; }}

/* panels: keyed containers styled as cards */
[class*="st-key-panel"] {{ background: var(--card); border: 1px solid var(--border);
  border-radius: 16px; padding: 22px 24px; }}
[class*="st-key-panel"] [data-testid="stVerticalBlock"] {{ gap: 14px; }}
.panel-head {{ display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between;
  gap: 12px; }}
.panel-head h2 {{ font-size: 16px !important; font-weight: 600 !important; letter-spacing: -.01em;
  margin: 0 !important; padding: 0 !important; color: var(--foreground) !important; }}
.card {{ background: var(--card); border: 1px solid var(--border); border-radius: 16px; padding: 20px; }}
.kpis {{ display: grid; gap: 16px; grid-template-columns: repeat(4, minmax(0, 1fr)); }}
.kpi {{ transition: transform .15s, border-color .15s; }}
.kpi:hover {{ transform: translateY(-2px); border-color: color-mix(in srgb, var(--primary) 40%,
  transparent); }}
.kpi .top {{ display: flex; justify-content: space-between; gap: 8px; align-items: flex-start; }}
.kpi .lbl {{ font-size: 14px !important; color: var(--muted-foreground); }}
.kpi .val {{ font-family: var(--mono) !important; font-size: 30px !important; font-weight: 600; letter-spacing: -.02em; }}
.kpi .row {{ margin-top: 12px; display: flex; justify-content: space-between; align-items: flex-end; gap: 8px; }}
.kpi .sub {{ margin-top: 8px; font-size: 12px !important; color: var(--muted-foreground); }}
.delta {{ display: inline-flex; align-items: center; gap: 2px; border-radius: 999px; padding: 2px 8px;
  font-family: var(--mono) !important; font-size: 11px; font-weight: 500; white-space: nowrap; }}
.tone-success {{ background: color-mix(in srgb, var(--success) 15%, transparent); color: var(--success); }}
.tone-warning {{ background: color-mix(in srgb, var(--warning) 15%, transparent); color: var(--warning); }}
.tone-destructive {{ background: color-mix(in srgb, var(--destructive) 15%, transparent);
  color: var(--destructive); }}
.tone-chart2 {{ background: color-mix(in srgb, var(--chart-2) 15%, transparent); color: var(--chart-2); }}
.tone-muted {{ background: var(--muted); color: var(--muted-foreground); }}

/* hero */
.hero {{ position: relative; overflow: hidden; border-radius: 24px; border: 1px solid var(--border);
  background: var(--card); }}
.bg-grid {{ position: absolute; inset: 0; opacity: .7; background-size: 28px 28px; background-image:
  linear-gradient(to right, color-mix(in srgb, var(--foreground) 6%, transparent) 1px, transparent 1px),
  linear-gradient(to bottom, color-mix(in srgb, var(--foreground) 6%, transparent) 1px, transparent 1px);
  -webkit-mask-image: radial-gradient(ellipse at top right, black, transparent 70%);
  mask-image: radial-gradient(ellipse at top right, black, transparent 70%); }}
.hero .blob {{ position: absolute; right: -96px; top: -96px; width: 320px; height: 320px;
  border-radius: 999px; background: var(--primary); opacity: .4; filter: blur(64px); }}
.hero svg.pulse {{ position: absolute; left: 0; right: 0; bottom: 0; width: 100%; height: 112px; opacity: .6; }}
.pulse-line {{ stroke-dasharray: 1400; stroke-dashoffset: 1400; animation: pulse-draw 4.5s linear infinite; }}
@keyframes pulse-draw {{ to {{ stroke-dashoffset: 0; }} }}
.hero .inner {{ position: relative; display: grid; gap: 32px; padding: 32px 32px 112px;
  grid-template-columns: 1.3fr 1fr; }}
.hero .big {{ font-size: 72px !important; font-weight: 700; letter-spacing: -.05em; line-height: 1;
  font-variant-numeric: tabular-nums; }}
.hero .big span {{ font-size: 30px; font-weight: 600; color: var(--muted-foreground); letter-spacing: 0; }}
.hero .lead {{ margin-top: 16px; max-width: 28rem; font-size: 14px !important; line-height: 1.6;
  color: var(--muted-foreground); }}
.tiles {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-self: start; }}
.tile {{ border-radius: 16px; border: 1px solid var(--border); padding: 16px; backdrop-filter: blur(8px);
  background: color-mix(in srgb, var(--background) 60%, transparent); }}
.tile dt {{ font-size: 12px; color: var(--muted-foreground); }}
.tile dd {{ margin: 4px 0 0; font-family: var(--mono) !important; font-size: 24px; font-weight: 600; }}
.glow {{ box-shadow: 0 0 0 1px color-mix(in srgb, var(--primary) 30%, transparent),
  0 10px 40px -10px var(--glow); }}
.hatch {{ background-image: repeating-linear-gradient(-45deg, color-mix(in srgb, var(--destructive) 55%,
  transparent) 0 2px, transparent 2px 5px); }}
.spin {{ animation: spin 1s linear infinite; }} .spin-slow {{ animation: spin 2.5s linear infinite; }}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
@media (prefers-reduced-motion: reduce) {{ .pulse-line {{ animation: none; stroke-dashoffset: 0; }}
  .live::before, .spin, .spin-slow {{ animation: none; }} }}

/* lists, tables, heatmap */
.legend {{ display: flex; align-items: center; gap: 16px; font-size: 12px; color: var(--muted-foreground);
  flex-wrap: wrap; }}
.legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
.feed {{ display: flex; flex-direction: column; gap: 8px; }}
.feed-row {{ display: flex; align-items: center; gap: 16px; border-radius: 12px; padding: 12px;
  border: 1px solid transparent; }}
.feed-row:hover {{ border-color: var(--border); background: color-mix(in srgb, var(--muted) 50%, transparent); }}
.ico {{ display: inline-flex; align-items: center; justify-content: center; flex: none; border-radius: 10px; }}
.sev {{ border-radius: 999px; border: 1px solid; padding: 2px 8px; font-family: var(--mono) !important;
  font-size: 10px; text-transform: uppercase; }}
.sev.critical {{ border-color: color-mix(in srgb, var(--destructive) 40%, transparent);
  background: color-mix(in srgb, var(--destructive) 10%, transparent); color: var(--destructive); }}
.sev.high {{ border-color: color-mix(in srgb, var(--warning) 40%, transparent);
  background: color-mix(in srgb, var(--warning) 10%, transparent); color: var(--warning); }}
.sev.medium {{ border-color: var(--border); background: var(--muted); color: var(--muted-foreground); }}
.trunc {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
table.gp {{ width: 100%; min-width: 560px; border-collapse: collapse; font-size: 14px; text-align: left; }}
table.gp th {{ font-family: var(--mono) !important; font-size: 11px; text-transform: uppercase;
  letter-spacing: .06em; color: var(--muted-foreground); font-weight: 500; padding: 0 0 12px;
  border-bottom: 1px solid var(--border); }}
table.gp td {{ padding: 12px 0; border-bottom: 1px solid var(--border); }}
table.gp tr:last-child td {{ border-bottom: none; }}
table.gp tbody tr:hover {{ background: color-mix(in srgb, var(--muted) 40%, transparent); }}
.r {{ text-align: right !important; }}
.scroll-x {{ overflow-x: auto; }}
.heat {{ display: grid; grid-template-columns: 56px repeat(24, minmax(0, 1fr)); gap: 3px; min-width: 720px; }}
.heat .c {{ height: 16px; border-radius: 4px; transition: transform .1s; }}
.heat .c:hover {{ transform: scale(1.25); }}
.heat .c.gap {{ border: 1px solid color-mix(in srgb, var(--destructive) 50%, transparent); }}
.heat .lab {{ font-family: var(--mono) !important; font-size: 11px; color: var(--muted-foreground);
  display: flex; align-items: center; }}
.heat .hr {{ font-family: var(--mono) !important; font-size: 9px; color: var(--muted-foreground);
  text-align: center; }}
.bar {{ position: relative; height: 10px; border-radius: 999px; background: var(--muted); }}
.bar > i {{ display: block; height: 100%; border-radius: 999px; }}
.bar > b {{ position: absolute; top: -4px; left: 90%; width: 2px; height: 18px; border-radius: 2px;
  background: color-mix(in srgb, var(--foreground) 60%, transparent); }}
.note-box {{ border-radius: 12px; background: color-mix(in srgb, var(--muted) 70%, transparent);
  padding: 12px; font-family: var(--mono) !important; font-size: 11px; line-height: 1.6;
  color: var(--muted-foreground); }}
.empty {{ border: 1px dashed var(--border); border-radius: 12px; padding: 24px; text-align: center;
  color: var(--muted-foreground); font-size: 13px; }}

@media (max-width: 1100px) {{ .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .hero .inner {{ grid-template-columns: 1fr; }} }}
@media (max-width: 640px) {{ .kpis {{ grid-template-columns: 1fr; }}
  [data-testid="stMainBlockContainer"], .block-container {{ padding: 0 1rem 2rem; }}
  .hero .big {{ font-size: 48px; }} }}
"""


def css(theme: str, view: str) -> str:
    t = THEMES[theme]
    tokens = " ".join(f"--{k}: {v};" for k, v in t.items())
    active_bg, active_fg = (
        ("primary", "primary-foreground") if theme == "dark" else ("card", "foreground")
    )
    nav_active = (
        f".st-key-nav_{view} button {{ background: var(--sidebar-accent) !important; "
        "color: var(--foreground) !important; }}"
        f".st-key-nav_{view} button p {{ color: var(--foreground) !important; }}"
    )
    body = BASE_CSS.format(fonts=FONTS, tokens=tokens, active_bg=active_bg, active_fg=active_fg)
    return f"<style>{body}{nav_active}</style>"


def plotly_layout(theme: str, height: int) -> dict[str, Any]:
    t = THEMES[theme]
    return {
        "height": height,
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "Space Grotesk, sans-serif", "size": 11, "color": t["muted-foreground"]},
        "margin": {"l": 8, "r": 8, "t": 8, "b": 8},
        "showlegend": False,
        "hovermode": "x unified",
        "hoverlabel": {
            "bgcolor": t["popover"],
            "bordercolor": t["border"],
            "font": {"family": "JetBrains Mono, monospace", "size": 12, "color": t["foreground"]},
        },
        "xaxis": {
            "showgrid": False,
            "zeroline": False,
            "showline": False,
            "ticks": "",
            "fixedrange": True,
        },
        "yaxis": {
            "showgrid": True,
            "gridcolor": t["border"],
            "griddash": "dot",
            "zeroline": False,
            "showline": False,
            "ticks": "",
            "fixedrange": True,
        },
        "bargap": 0.25,
    }


PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}
