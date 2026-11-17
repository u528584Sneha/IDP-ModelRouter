"""Build cost-vs-accuracy frontier workbooks using the Method 5 (Router
scoring) logic from docs/Five_Point_Frontier_Scale_v2 1.pptx:

  - Frontier = models where no other model is both cheaper and more accurate.
  - Each frontier model gets an accuracy position and a cost position
    (0-100), cost measured in doublings since price ranges span orders of
    magnitude (Method 4/5, slide 3-4).
  - Five user choices score every frontier model: accuracy position minus a
    cost weight times cost position. Cost-optimized = cheapest; Cost-leaning
    = weight 2; Balanced = weight 1; Accuracy-leaning = weight 1/2;
    Accuracy-optimized = most accurate (slide 4).
  - On failure: exclude the failed model, redraw the frontier from what's
    left, and score again - this can surface a model that was previously
    hidden because it was only beaten by the one that just failed (slide 6).

Reads the existing docs/pareto/*.xlsx workbooks for (model, cost, accuracy)
and writes one workbook per dataset into docs/pareto/Cost_Accuracy_Pareto/.

Usage: python build_cost_accuracy_pareto.py
"""
import math
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import openpyxl
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

SRC_DIR = r"C:\Users\u528584\Documents\AI Research\HALO-ModelRouter\docs\pareto"
OUT_DIR = os.path.join(SRC_DIR, "Cost_Accuracy_Pareto")
os.makedirs(OUT_DIR, exist_ok=True)

SOURCES = ["Accord_pareto.xlsx", "AWB_pareto.xlsx", "BOL_pareto.xlsx", "Combined_pareto.xlsx"]

# Five user choices (slide 4): (label, cost weight, extreme rule)
LEVELS = [
    ("L1 - Lowest cost", "cost"),
    ("L2 - Cost-leaning", 2.0),
    ("L3 - Balanced", 1.0),
    ("L4 - Accuracy-leaning", 0.5),
    ("L5 - Highest accuracy", "accuracy"),
]

# dataviz skill palette
COLOR_PARETO = "#0ca30c"       # status: good
COLOR_NONPARETO = "#898781"    # muted ink
COLOR_LINE = "#2a78d6"         # categorical slot 1 (frontier line)
COLOR_GRID = "#e1e0d9"
COLOR_AXIS = "#c3c2b7"
COLOR_TEXT_PRIMARY = "#0b0b0b"
COLOR_TEXT_SECONDARY = "#52514e"
SURFACE = "#fcfcfb"

HEADER_FILL = PatternFill("solid", fgColor="2a78d6")
HEADER_FONT = Font(color="FFFFFF", bold=True)


def read_models(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Data"]
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[1] is None:
            continue
        rows.append({"model": r[1], "accuracy": float(r[2]), "cost": float(r[3])})
    return rows


def is_dominated(x, pool):
    for y in pool:
        if y is x:
            continue
        better_or_equal = y["cost"] <= x["cost"] and y["accuracy"] >= x["accuracy"]
        strictly_better = y["cost"] < x["cost"] or y["accuracy"] > x["accuracy"]
        if better_or_equal and strictly_better:
            return True
    return False


def compute_frontier(pool):
    """Frontier: no other model in pool is both cheaper and more accurate."""
    frontier = [r for r in pool if not is_dominated(r, pool)]
    return sorted(frontier, key=lambda r: r["cost"])


def add_positions(frontier):
    """Accuracy position (0-100, linear) and cost position (0-100, counted
    in doublings - slide 3) for each model on the frontier. Falls back to
    linear cost position if the cheapest frontier model is free (cost 0),
    since doublings from zero are undefined."""
    accs = [r["accuracy"] for r in frontier]
    costs = [r["cost"] for r in frontier]
    acc_min, acc_max = min(accs), max(accs)
    cost_min, cost_max = min(costs), max(costs)
    for r in frontier:
        r["acc_pos"] = 0.0 if acc_max == acc_min else (r["accuracy"] - acc_min) / (acc_max - acc_min) * 100
        if cost_max == cost_min:
            r["cost_pos"] = 0.0
        elif cost_min <= 0:
            r["cost_pos"] = (r["cost"] - cost_min) / (cost_max - cost_min) * 100
        else:
            max_doublings = math.log2(cost_max / cost_min)
            doublings = math.log2(r["cost"] / cost_min) if r["cost"] > 0 else 0.0
            r["cost_pos"] = doublings / max_doublings * 100
    return frontier


def pick_for_level(frontier, weight):
    if weight == "cost":
        return min(frontier, key=lambda r: (r["cost"], -r["accuracy"]))
    if weight == "accuracy":
        return max(frontier, key=lambda r: (r["accuracy"], -r["cost"]))
    return max(frontier, key=lambda r: (r["acc_pos"] - weight * r["cost_pos"], r["accuracy"]))


def score_for(r, weight):
    if weight in ("cost", "accuracy"):
        return None
    return round(r["acc_pos"] - weight * r["cost_pos"], 2)


def fail_chain(rows, weight):
    """Repeatedly redraw the frontier (fresh positions each time) and pick
    again: best choice, then (if it fails) the next, then the next -
    slide 6's rule, chained to exhaustion."""
    excluded = set()
    chain = []
    while True:
        pool = [r for r in rows if r["model"] not in excluded]
        if not pool:
            break
        frontier = add_positions(compute_frontier(pool))
        pick = pick_for_level(frontier, weight)
        chain.append(pick)
        excluded.add(pick["model"])
    return chain


def make_chart(rows, frontier, level_picks, title, out_png):
    others = [r for r in rows if r["model"] not in {f["model"] for f in frontier}]
    pick_models = {model: label for label, model in level_picks}

    fig, (ax, ax_legend) = plt.subplots(
        1, 2, figsize=(11.5, 6.5), dpi=150,
        gridspec_kw={"width_ratios": [3, 1.1]})
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax_legend.set_facecolor(SURFACE)
    ax_legend.axis("off")

    ax.scatter([r["cost"] for r in others], [r["accuracy"] for r in others],
               s=36, color=COLOR_NONPARETO, alpha=0.75, zorder=2, label="Not on frontier")
    ax.scatter([r["cost"] for r in frontier], [r["accuracy"] for r in frontier],
               s=90, color=COLOR_PARETO, edgecolor="white", linewidth=0.8,
               zorder=4, label="On frontier")
    if len(frontier) > 1:
        ax.plot([r["cost"] for r in frontier], [r["accuracy"] for r in frontier],
                 color=COLOR_LINE, linewidth=2, zorder=3)

    for i, r in enumerate(frontier, start=1):
        ax.annotate(str(i), (r["cost"], r["accuracy"]), ha="center", va="center",
                     fontsize=7.5, fontweight="bold", color="white", zorder=5)

    ax.set_xlabel("Cost", color=COLOR_TEXT_SECONDARY, fontsize=10)
    ax.set_ylabel("Accuracy (%)", color=COLOR_TEXT_SECONDARY, fontsize=10)
    ax.set_title(f"{title} — Cost vs Accuracy Frontier", color=COLOR_TEXT_PRIMARY,
                 fontsize=13, fontweight="bold", loc="left")
    ax.grid(True, color=COLOR_GRID, linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_color(COLOR_AXIS)
    ax.tick_params(colors=COLOR_TEXT_SECONDARY)
    legend = ax.legend(frameon=False, loc="lower right", fontsize=9)
    for text in legend.get_texts():
        text.set_color(COLOR_TEXT_SECONDARY)

    lines = ["Frontier (cheapest -> most accurate)", ""]
    for i, r in enumerate(frontier, start=1):
        tag = f"  [{pick_models[r['model']]}]" if r["model"] in pick_models else ""
        lines.append(f"{i}. {r['model']}{tag}")
        lines.append(f"    acc {r['accuracy']:.1f}%  ·  cost {r['cost']:.2f}")
    ax_legend.text(0, 1, "\n".join(lines), transform=ax_legend.transAxes,
                    fontsize=8.5, va="top", ha="left", color=COLOR_TEXT_PRIMARY,
                    linespacing=1.6)

    fig.tight_layout()
    fig.savefig(out_png, facecolor=SURFACE)
    plt.close(fig)


def autosize(ws):
    for col_cells in ws.columns:
        length = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells)
        ws.column_dimensions[get_column_letter(col_cells[0].column)].width = min(max(length + 2, 10), 60)


def write_header(ws, headers):
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
    ws.freeze_panes = "A2"


def build_workbook(name, rows, chart_png, out_path):
    frontier = add_positions(compute_frontier(rows))
    frontier_names = {r["model"] for r in frontier}
    level_picks = [(label, pick_for_level(frontier, weight)["model"]) for label, weight in LEVELS]

    wb = openpyxl.Workbook()

    ws = wb.active
    ws.title = "Data"
    write_header(ws, ["Rank", "Model", "Accuracy (%)", "Cost", "On Frontier"])
    for i, r in enumerate(sorted(rows, key=lambda r: -r["accuracy"]), start=1):
        ws.append([i, r["model"], round(r["accuracy"], 4), round(r["cost"], 4),
                    "Yes" if r["model"] in frontier_names else "No"])
    autosize(ws)

    ws_fr = wb.create_sheet("Frontier & Scores")
    headers = ["Position", "Model", "Accuracy (%)", "Cost", "Accuracy Position", "Cost Position"]
    headers += [label for label, w in LEVELS if w not in ("cost", "accuracy")]
    headers += ["First Choice For"]
    write_header(ws_fr, headers)
    picks_by_model = {}
    for label, model in level_picks:
        picks_by_model.setdefault(model, []).append(label)
    for r in frontier:
        row = [frontier.index(r) + 1, r["model"], round(r["accuracy"], 4), round(r["cost"], 4),
               round(r["acc_pos"], 1), round(r["cost_pos"], 1)]
        row += [score_for(r, w) for label, w in LEVELS if w not in ("cost", "accuracy")]
        row += [", ".join(picks_by_model.get(r["model"], [])) or "-"]
        ws_fr.append(row)
    autosize(ws_fr)

    ws_lp = wb.create_sheet("Level Picks")
    write_header(ws_lp, ["Level", "Model", "Accuracy (%)", "Cost"])
    for label, model in level_picks:
        m = next(r for r in frontier if r["model"] == model)
        ws_lp.append([label, m["model"], round(m["accuracy"], 4), round(m["cost"], 4)])
    autosize(ws_lp)

    ws_fc = wb.create_sheet("Fail Chain")
    write_header(ws_fc, ["Level", "Order", "Model", "Accuracy (%)", "Cost",
                          "Delta Accuracy vs Prior Pick", "Delta Cost vs Prior Pick",
                          "On Original Frontier?"])
    for label, weight in LEVELS:
        chain = fail_chain(rows, weight)
        prev = None
        for i, r in enumerate(chain, start=1):
            d_acc = "-" if prev is None else round(r["accuracy"] - prev["accuracy"], 4)
            d_cost = "-" if prev is None else round(r["cost"] - prev["cost"], 4)
            ws_fc.append([label, i, r["model"], round(r["accuracy"], 4), round(r["cost"], 4),
                          d_acc, d_cost,
                          "Yes" if r["model"] in frontier_names else "No (surfaced by redraw)"])
            prev = r
    autosize(ws_fc)

    ws_c = wb.create_sheet("Frontier Chart")
    img = XLImage(chart_png)
    ws_c.add_image(img, "A1")

    wb.save(out_path)


def main():
    for fname in SOURCES:
        src_path = os.path.join(SRC_DIR, fname)
        name = fname.replace("_pareto.xlsx", "")
        rows = read_models(src_path)
        frontier = add_positions(compute_frontier(rows))
        level_picks = [(label, pick_for_level(frontier, weight)["model"]) for label, weight in LEVELS]

        chart_png = os.path.join(OUT_DIR, f"{name}_cost_accuracy_chart.png")
        make_chart(rows, frontier, level_picks, name, chart_png)

        out_path = os.path.join(OUT_DIR, f"{name}_cost_accuracy_pareto.xlsx")
        build_workbook(name, rows, chart_png, out_path)
        print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
