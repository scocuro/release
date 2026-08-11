"""
배리어 여유율 추이 차트 (메일 인라인 임베드용 PNG).

한글 폰트 함정
  GitHub Actions 우분투 러너에는 한글 폰트가 없어 축 레이블이 전부 두부(□□□)로 나온다.
  워크플로에서 fonts-nanum을 설치하고, 여기서 실제로 잡혔는지 확인한다.
  못 잡으면 영문 레이블로 자동 폴백해서 최소한 읽히게 한다.
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
    matplotlib의 ttflist는 .ttc를 놓치는 경우가 있다.
    (Noto Sans CJK가 딱 이 케이스 — 설치돼 있는데 목록에 안 뜬다)
    폰트 디렉터리를 직접 훑어 CJK 파일을 등록한다.
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



def level_chart(view, history, days: int = 400) -> bytes | None:
    """
    One chart per product, showing EVERY underlying (not just worst-of).

    worst-of can switch from day to day, so drawing only that line produces
    a series that silently jumps between tickers. Plot them all.

    y = close / strike, so the trigger and KI become flat horizontal lines
    and the reading matches the bar in the email exactly.
    """
    ko = setup_font()

    plotted = []
    for leg in view.legs:
        s = series(history, view.id, leg.ticker, "level_pct")
        if len(s) < 2:
            continue
        s = s[-days:]
        label = (leg.display if ko else leg.ticker) + (" (worst)" if leg.is_worst else "")
        plotted.append((label, [parse_date(d) for d, _ in s],
                        [y for _, y in s], leg.is_worst))
    if not plotted:
        return None

    trig = view.barrier
    ki = next((l.ki_px / l.strike for l in view.legs if l.ki_px and l.strike), None)

    fig, ax = plt.subplots(figsize=(7.4, 3.4), dpi=150)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    # y축은 실제 데이터 + 트리거로만 잡는다.
    # KI를 무조건 포함시키면(35% 등) 정작 중요한 구간이 눌려서 안 보인다.
    ys_all = [y for _, _, ys, _ in plotted for y in ys]
    lo = min(ys_all + ([trig] if trig else []))
    hi = max(ys_all)
    pad = (hi - lo) * 0.14 or 0.05
    ymin, ymax = lo - pad, hi + pad

    ki_visible = ki is not None and ki >= ymin
    if ki_visible:                      # KI가 코앞이면 축을 넓혀서라도 보여준다
        ymin = min(ymin, ki - pad * 0.5)
    ax.set_ylim(ymin, ymax)

    # 트리거 아래 = 조기상환 불가 구간
    if trig:
        ax.axhspan(ymin, trig, facecolor="#B23A2E", alpha=0.05, zorder=0)
        ax.axhline(trig, color="#12171F", lw=1.1, ls=(0, (5, 3)), zorder=2)
        ax.annotate(("트리거 " if ko else "trigger ") + f"{trig*100:.0f}%",
                    (0.005, trig), xycoords=("axes fraction", "data"),
                    fontsize=8, color="#12171F", va="bottom", ha="left", zorder=5)
    if ki_visible:
        ax.axhline(ki, color="#3A2E4A", lw=1.1, ls=(0, (2, 3)), zorder=2)
        ax.annotate(f"KI {ki*100:.0f}%", (0.005, ki),
                    xycoords=("axes fraction", "data"),
                    fontsize=8, color="#3A2E4A", va="bottom", ha="left", zorder=5)
    elif ki is not None:                # 화면 밖이면 글자로만 알린다
        ax.annotate(f"KI {ki*100:.0f}% (범위 밖)" if ko else f"KI {ki*100:.0f}% (off-chart)",
                    (0.005, 0.03), xycoords="axes fraction",
                    fontsize=7.5, color="#6A7280", ha="left", zorder=5)

    for i, (label, xs, ys, is_worst) in enumerate(plotted):
        c = PALETTE[i % len(PALETTE)]
        ax.plot(xs, ys, lw=2.2 if is_worst else 1.4, color=c, label=label,
                alpha=1.0 if is_worst else 0.75, zorder=4 if is_worst else 3)
        ax.scatter([xs[-1]], [ys[-1]], s=24, color=c, zorder=5)
        ax.annotate(f"{ys[-1]*100:.0f}%", (xs[-1], ys[-1]),
                    textcoords="offset points", xytext=(6, 0),
                    fontsize=8.5, color=c, fontweight="bold", va="center")

    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y*100:.0f}%"))
    ax.grid(axis="y", color="#DCE0DA", lw=0.7, zorder=1)
    ax.tick_params(labelsize=8.5, colors="#6A7280")
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#DCE0DA")
    ax.margins(x=0.07)
    lg = ax.legend(fontsize=8.5, frameon=False, loc="upper left",
                   bbox_to_anchor=(0, -0.13), ncol=min(len(plotted), 3),
                   handlelength=1.5, columnspacing=1.5, borderpad=0)
    for t in lg.get_texts():
        t.set_color("#12171F")
    fig.autofmt_xdate(rotation=0, ha="center")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="#FFFFFF")
    plt.close(fig)
    return buf.getvalue()


def product_charts(views, history) -> dict:
    """상품 id -> PNG bytes"""
    out = {}
    for v in views:
        try:
            png = level_chart(v, history)
        except Exception as e:                    # noqa: BLE001
            print(f"  [FAIL] 차트 {v.id}: {e}")
            continue
        if png:
            out[v.id] = png
    return out


def save_png(data: bytes, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
