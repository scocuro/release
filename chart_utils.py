"""
Buffer-to-barrier trend chart (inline PNG for the email).

Korean font trap:
  GitHub Actions Ubuntu runners ship no Korean font, so every axis label
  renders as tofu boxes. The workflow installs fonts-nanum; this module
  verifies it actually registered and falls back to English labels if not.
"""

from __future__ import annotations

import io
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib import font_manager                  # noqa: E402
from matplotlib.ticker import FuncFormatter          # noqa: E402

from store import parse_date, series                 # noqa: E402

_KO_CANDIDATES = ["NanumGothic", "NanumBarunGothic", "Malgun Gothic",
                  "AppleGothic", "Apple SD Gothic Neo", "Noto Sans CJK KR",
                  "Noto Sans KR", "UnDotum"]

PALETTE = ["#1F3A5F", "#B23A2E", "#0E7C6B", "#B5820A", "#5B4B8A"]

_FONT_DIRS = ["/usr/share/fonts", "/usr/local/share/fonts",
              os.path.expanduser("~/.fonts"), "C:/Windows/Fonts",
              "/System/Library/Fonts", "/Library/Fonts"]


def _register_cjk_files() -> None:
    """
    matplotlib's ttflist misses .ttc files (Noto Sans CJK is exactly this
    case - installed but absent from the list). Scan font dirs directly.
    """
    import glob
    pats = ("*Nanum*", "*NotoSansCJK*", "*NotoSansKR*", "*malgun*", "*AppleGothic*")
    for d in _FONT_DIRS:
        if not os.path.isdir(d):
            continue
        for pat in pats:
            for ext in ("ttf", "ttc", "otf"):
                for path in glob.glob(os.path.join(d, "**", f"{pat}.{ext}"), recursive=True):
                    try:
                        font_manager.fontManager.addfont(path)
                    except Exception:            # noqa: BLE001
                        pass


def setup_font() -> bool:
    plt.rcParams["axes.unicode_minus"] = False
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in _KO_CANDIDATES:
        if name in available:
            plt.rcParams["font.family"] = name
            return True

    _register_cjk_files()
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in _KO_CANDIDATES + ["Noto Sans CJK JP", "Noto Sans CJK SC"]:
        if name in available:
            plt.rcParams["font.family"] = name
            return True
    return False


def buffer_chart(views, history, days: int = 180) -> bytes | None:
    """
    Buffer-to-barrier time series for each product's worst-of.
    y=0 is the redemption threshold - above the line means redeemable.
    """
    ko = setup_font()
    T = (lambda k, e: k if ko else e)

    plotted = []
    for v in views:
        if not v.worst:
            continue
        s = series(history, v.id, v.worst.ticker, "buf_barrier")
        if len(s) < 2:
            continue
        s = s[-days:]
        label = (f"{v.id} · {v.worst.display}" if ko
                 else f"{v.id} · {v.worst.ticker}")
        plotted.append((label, [parse_date(d) for d, _ in s], [y for _, y in s]))

    if not plotted:
        return None

    fig, ax = plt.subplots(figsize=(7.6, 3.7), dpi=150)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    lo = min(min(ys) for _, _, ys in plotted)
    hi = max(max(ys) for _, _, ys in plotted)
    ax.axhspan(0, max(hi * 1.25, 0.05), facecolor="#0E7C6B", alpha=0.05, zorder=0)
    ax.axhspan(min(lo * 1.25, -0.05), 0, facecolor="#B23A2E", alpha=0.05, zorder=0)
    ax.axhline(0, color="#12171F", lw=1.2, zorder=2)

    for i, (label, xs, ys) in enumerate(plotted):
        c = PALETTE[i % len(PALETTE)]
        ax.plot(xs, ys, lw=1.9, color=c, label=label, zorder=3)
        ax.scatter([xs[-1]], [ys[-1]], s=26, color=c, zorder=4)
        ax.annotate(f"{ys[-1]*100:+.1f}%", (xs[-1], ys[-1]),
                    textcoords="offset points", xytext=(6, 0),
                    fontsize=9, color=c, fontweight="bold", va="center")

    ax.set_title(T("배리어 여유율 추이 (worst-of)  ·  0선 위 = 조기상환 구간",
                   "Buffer to barrier (worst-of)  ·  above 0 = redeemable"),
                 fontsize=11, fontweight="bold", color="#12171F", pad=10, loc="left")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y*100:.0f}%"))
    ax.grid(axis="y", color="#DCE0DA", lw=0.7, zorder=1)
    ax.tick_params(labelsize=8.5, colors="#6A7280")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#DCE0DA")
    ax.margins(x=0.06)
    leg = ax.legend(fontsize=8.5, frameon=False, loc="upper left",
                    bbox_to_anchor=(0, -0.14), ncol=max(len(plotted), 1),
                    handlelength=1.6, columnspacing=1.8, borderpad=0)
    for t in leg.get_texts():
        t.set_color("#12171F")
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="#FFFFFF")
    plt.close(fig)
    return buf.getvalue()


def save_png(data: bytes, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
