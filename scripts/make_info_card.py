from pathlib import Path
import html


OUTPUT = Path("info-card.svg")


# =========================================================
# PROFILE DATA
# =========================================================

NAME = "Hamza Khan"
USERNAME = "hamzaKhan2004"

ROLE = "Full Stack Developer"

STACK = "MERN / TypeScript"
AI_STACK = "RAG / LangGraph / Gemini"
BACKEND = "Node.js / Express / MongoDB"
CLOUD = "AWS / Docker"

PROJECTS = [
    "Nova Search",
    "CodeHub",
    "React-Dooms",
]


# =========================================================
# SVG SETTINGS
# =========================================================

WIDTH = 520

# Increased so nothing gets clipped.
HEIGHT = 520

BACKGROUND = "#0d1117"
BORDER = "#30363d"

TEXT = "#c9d1d9"
MUTED = "#8b949e"

GREEN = "#3fb950"
BLUE = "#58a6ff"
PURPLE = "#bc8cff"

FONT = (
    '"DejaVu Sans Mono",'
    '"Courier New",'
    'Consolas,'
    'monospace'
)


# =========================================================
# ANIMATION
# =========================================================

LINE_DELAY = 0.10
LINE_DURATION = 0.40


# =========================================================
# TEXT ELEMENT
# =========================================================

def text_element(
    text,
    x,
    y,
    size=14,
    color=TEXT,
    weight="400",
    delay=0,
):
    """
    Generate an animated SVG text element.
    """

    safe_text = html.escape(
        text,
        quote=False,
    )

    return f"""
<text
    x="{x}"
    y="{y}"
    class="line"
    style="animation-delay:{delay:.2f}s"
    font-size="{size}px"
    font-weight="{weight}"
    fill="{color}"
>
    {safe_text}
</text>
"""


# =========================================================
# MAIN
# =========================================================

def main():

    svg = []

    # =====================================================
    # SVG HEADER
    # =====================================================

    svg.append(
        f'''<svg
xmlns="http://www.w3.org/2000/svg"
width="{WIDTH}"
height="{HEIGHT}"
viewBox="0 0 {WIDTH} {HEIGHT}">'''
    )

    # =====================================================
    # CSS
    # =====================================================

    svg.append(
        f"""
<style>

.card {{
    fill: {BACKGROUND};
}}

.border {{
    fill: none;

    stroke: {BORDER};

    stroke-width: 1;
}}

.line {{
    font-family: {FONT};

    opacity: 0;

    transform:
        translateX(-10px);

    animation:
        reveal
        {LINE_DURATION}s
        ease-out
        forwards;
}}

@keyframes reveal {{

    0% {{
        opacity: 0;

        transform:
            translateX(-10px);
    }}

    100% {{
        opacity: 1;

        transform:
            translateX(0);
    }}

}}

</style>
"""
    )

    # =====================================================
    # CARD BACKGROUND
    # =====================================================

    svg.append(
        f'''
<rect
    class="card"
    x="0"
    y="0"
    width="{WIDTH}"
    height="{HEIGHT}"
    rx="14"
/>

<rect
    class="border"
    x="0.5"
    y="0.5"
    width="{WIDTH - 1}"
    height="{HEIGHT - 1}"
    rx="14"
/>
'''
    )

    # =====================================================
    # TERMINAL DOTS
    # =====================================================

    svg.append(
        text_element(
            "●  ●  ●",
            24,
            30,
            11,
            MUTED,
            delay=0,
        )
    )

    # =====================================================
    # TERMINAL COMMAND
    # =====================================================

    svg.append(
        text_element(
            f"{USERNAME} ~ $ whoami",
            24,
            62,
            16,
            GREEN,
            weight="600",
            delay=0.12,
        )
    )

    # =====================================================
    # NAME
    # =====================================================

    svg.append(
        text_element(
            NAME,
            24,
            100,
            24,
            TEXT,
            weight="700",
            delay=0.24,
        )
    )

    # =====================================================
    # ROLE
    # =====================================================

    svg.append(
        text_element(
            ROLE,
            24,
            124,
            13,
            MUTED,
            delay=0.34,
        )
    )

    # =====================================================
    # DIVIDER
    # =====================================================

    svg.append(
        f'''
<line
    x1="24"
    y1="145"
    x2="{WIDTH - 24}"
    y2="145"
    stroke="{BORDER}"
    stroke-width="1"
/>
'''
    )

    # =====================================================
    # TECHNICAL INFORMATION
    # =====================================================

    lines = [
        ("role", ROLE, GREEN),
        ("stack", STACK, BLUE),
        ("ai", AI_STACK, PURPLE),
        ("backend", BACKEND, BLUE),
        ("cloud", CLOUD, GREEN),
    ]

    y = 175

    for index, item in enumerate(lines):

        key = item[0]
        value = item[1]
        color = item[2]

        delay = (
            0.48
            + index * LINE_DELAY
        )

        # Key

        svg.append(
            text_element(
                f"> {key}",
                24,
                y,
                12,
                color,
                weight="600",
                delay=delay,
            )
        )

        # Value

        svg.append(
            text_element(
                value,
                125,
                y,
                12,
                TEXT,
                delay=delay + 0.03,
            )
        )

        y += 32

    # =====================================================
    # PROJECT SECTION
    # =====================================================

    y += 5

    project_delay = (
        0.48
        + len(lines) * LINE_DELAY
        + 0.15
    )

    svg.append(
        text_element(
            "projects",
            24,
            y,
            13,
            GREEN,
            weight="600",
            delay=project_delay,
        )
    )

    y += 28

    # =====================================================
    # PROJECTS
    # =====================================================

    for index, project in enumerate(PROJECTS):

        delay = (
            project_delay
            + 0.10
            + index * LINE_DELAY
        )

        svg.append(
            text_element(
                f"├─ {project}",
                24,
                y,
                12,
                TEXT,
                delay=delay,
            )
        )

        y += 25

    # =====================================================
    # SECOND DIVIDER
    # =====================================================

    y += 5

    svg.append(
        f'''
<line
    x1="24"
    y1="{y}"
    x2="{WIDTH - 24}"
    y2="{y}"
    stroke="{BORDER}"
    stroke-width="1"
/>
'''
    )

    # =====================================================
    # FOOTER
    # =====================================================

    y += 27

    svg.append(
        text_element(
            "status:",
            24,
            y,
            11,
            GREEN,
            weight="600",
            delay=1.55,
        )
    )

    svg.append(
        text_element(
            "building things that search.",
            90,
            y,
            11,
            MUTED,
            delay=1.60,
        )
    )

    # =====================================================
    # BOTTOM PROMPT
    # =====================================================

    y += 25

    svg.append(
        text_element(
            "hamza@github ~ $ _",
            24,
            y,
            11,
            GREEN,
            delay=1.70,
        )
    )

    # =====================================================
    # CLOSE SVG
    # =====================================================

    svg.append("</svg>")

    # =====================================================
    # WRITE
    # =====================================================

    OUTPUT.write_text(
        "\n".join(svg),
        encoding="utf-8",
    )

    print(
        f"Created: {OUTPUT}"
    )

    print(
        f"Size: {WIDTH} x {HEIGHT}"
    )


if __name__ == "__main__":
    main()