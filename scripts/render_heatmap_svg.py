from pathlib import Path
import json
import html
from datetime import datetime


INPUT = Path("data/contributions.json")
OUTPUT = Path("contrib-heatmap.svg")


# =========================================================
# SETTINGS
# =========================================================

CELL = 12
GAP = 4

# 53 weeks × 7 days
WEEKS = 53
DAYS = 7

PADDING_LEFT = 20
PADDING_TOP = 42
PADDING_RIGHT = 20
PADDING_BOTTOM = 28

WIDTH = (
    PADDING_LEFT
    + WEEKS * (CELL + GAP)
    + PADDING_RIGHT
)

HEIGHT = (
    PADDING_TOP
    + DAYS * (CELL + GAP)
    + PADDING_BOTTOM
)


# GitHub-like palette
COLORS = {
    0: "#161b22",
    1: "#0e4429",
    2: "#006d32",
    3: "#26a641",
    4: "#39d353",
}


def load_data():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    return data["days"]


def build_calendar(days):
    """
    Convert contribution list into:
    week -> weekday -> contribution level
    """

    calendar = {}

    for item in days:
        date = datetime.strptime(item["date"], "%Y-%m-%d")

        # Monday = 0 ... Sunday = 6
        weekday = date.weekday()

        # Calculate week index from first date.
        first_date = datetime.strptime(days[0]["date"], "%Y-%m-%d")

        delta_days = (date - first_date).days
        week = delta_days // 7

        if week >= WEEKS:
            continue

        if week not in calendar:
            calendar[week] = {}

        calendar[week][weekday] = {
            "date": item["date"],
            "level": item["level"],
        }

    return calendar


def esc(value):
    return html.escape(str(value))


def render(days):

    calendar = build_calendar(days)

    svg = []

    svg.append(
        f'''<svg xmlns="http://www.w3.org/2000/svg"
        width="{WIDTH}"
        height="{HEIGHT}"
        viewBox="0 0 {WIDTH} {HEIGHT}"
        role="img"
        aria-label="GitHub contribution activity">'''
    )

    # =====================================================
    # BACKGROUND
    # =====================================================

    svg.append(
        f'''
        <rect
            width="100%"
            height="100%"
            rx="12"
            fill="#0d1117"
        />
        '''
    )

    # =====================================================
    # TITLE
    # =====================================================

    svg.append(
        '''
        <text
            x="20"
            y="25"
            fill="#8b949e"
            font-family="monospace"
            font-size="13"
        >
            CONTRIBUTION ACTIVITY
        </text>
        '''
    )

    # =====================================================
    # CELLS
    # =====================================================

    cell_index = 0

    for week in range(WEEKS):

        for weekday in range(DAYS):

            x = (
                PADDING_LEFT
                + week * (CELL + GAP)
            )

            y = (
                PADDING_TOP
                + weekday * (CELL + GAP)
            )

            item = calendar.get(week, {}).get(weekday)

            if item:
                level = item["level"]
                date = item["date"]

                color = COLORS.get(level, COLORS[0])

                tooltip = (
                    f'{date} — contribution level {level}'
                )

            else:
                color = COLORS[0]
                tooltip = ""

            delay = cell_index * 8

            svg.append(
                f'''
                <g>
                    <title>{esc(tooltip)}</title>

                    <rect
                        x="{x}"
                        y="{y}"
                        width="{CELL}"
                        height="{CELL}"
                        rx="2"
                        fill="{color}"
                        opacity="0"
                    >
                        <animate
                            attributeName="opacity"
                            from="0"
                            to="1"
                            dur="0.35s"
                            begin="{delay}ms"
                            fill="freeze"
                        />
                    </rect>
                </g>
                '''
            )

            cell_index += 1

    # =====================================================
    # LEGEND
    # =====================================================

    legend_x = WIDTH - 180
    legend_y = HEIGHT - 18

    svg.append(
        f'''
        <text
            x="{legend_x - 35}"
            y="{legend_y + 10}"
            fill="#8b949e"
            font-family="monospace"
            font-size="10"
        >
            Less
        </text>
        '''
    )

    for level in range(5):

        x = legend_x + level * 18

        svg.append(
            f'''
            <rect
                x="{x}"
                y="{legend_y}"
                width="12"
                height="12"
                rx="2"
                fill="{COLORS[level]}"
            />
            '''
        )

    svg.append(
        f'''
        <text
            x="{legend_x + 102}"
            y="{legend_y + 10}"
            fill="#8b949e"
            font-family="monospace"
            font-size="10"
        >
            More
        </text>
        '''
    )

    svg.append("</svg>")

    OUTPUT.write_text(
        "\n".join(svg),
        encoding="utf-8",
    )

    print(f"Generated: {OUTPUT}")
    print(f"Size: {WIDTH} × {HEIGHT}")


if __name__ == "__main__":
    days = load_data()
    render(days)