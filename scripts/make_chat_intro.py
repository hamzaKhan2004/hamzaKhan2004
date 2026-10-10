#!/usr/bin/env python3
"""
Generate an animated SVG chatbot typing response for the GitHub Profile README.
Reveals text word-by-word with ~38ms delay, subtle blinking cursor,
and finishes within ~1.85 seconds.
"""

from pathlib import Path

OUTPUT = Path("chat-intro.svg")

WIDTH = 680
HEIGHT = 115

LINES = [
    {
        "words": ["Hi,", "I'm", "Hamza", "Khan."],
        "color": "#58a6ff",
        "weight": "600",
        "size": 15,
        "y": 42,
        "start_time": 0.05,
    },
    {
        "words": ["I", "build", "full-stack", "applications", "and", "AI-powered", "systems."],
        "color": "#e6edf3",
        "weight": "400",
        "size": 14,
        "y": 68,
        "start_time": 0.28,
    },
    {
        "words": ["Currently", "exploring", "scalable", "backends", "and", "AI", "engineering."],
        "color": "#8b949e",
        "weight": "400",
        "size": 14,
        "y": 94,
        "start_time": 0.63,
    },
]

WORD_DELAY = 0.038  # ~38ms per word


def generate_svg() -> str:
    css_rules = [
        "/* Base text styles */",
        ".txt { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }",
        ".w { opacity: 0; animation: wordReveal 0.02s ease-out forwards; }",
        ".cursor { opacity: 0; fill: #58a6ff; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: 700; }",
        "",
        "@keyframes wordReveal {",
        "  0% { opacity: 0; }",
        "  100% { opacity: 1; }",
        "}",
        "",
        "/* Line 1 Cursor */",
        "@keyframes cur1 {",
        "  0%, 10% { opacity: 0; }",
        "  15%, 85% { opacity: 1; }",
        "  90%, 100% { opacity: 0; }",
        "}",
        ".c1 { animation: cur1 0.23s steps(1) 0.04s forwards; }",
        "",
        "/* Line 2 Cursor */",
        "@keyframes cur2 {",
        "  0%, 10% { opacity: 0; }",
        "  15%, 85% { opacity: 1; }",
        "  90%, 100% { opacity: 0; }",
        "}",
        ".c2 { animation: cur2 0.32s steps(1) 0.28s forwards; }",
        "",
        "/* Line 3 Cursor (blinks and fades out at 1.85s) */",
        "@keyframes cur3 {",
        "  0% { opacity: 0; }",
        "  10%, 25% { opacity: 1; }",
        "  30%, 45% { opacity: 0; }",
        "  50%, 65% { opacity: 1; }",
        "  70%, 85% { opacity: 0; }",
        "  90%, 98% { opacity: 1; }",
        "  100% { opacity: 0; }",
        "}",
        ".c3 { animation: cur3 1.25s linear 0.60s forwards; }",
        "",
        "/* Reduced motion fallback: show all text immediately without cursors */",
        "@media (prefers-reduced-motion: reduce) {",
        "  .w { opacity: 1 !important; animation: none !important; }",
        "  .cursor { display: none !important; }",
        "}",
    ]

    word_idx = 0
    svg_elements = []

    # Background card
    svg_elements.append(
        f'  <rect width="{WIDTH}" height="{HEIGHT}" rx="8" fill="#0d1117" stroke="#30363d" stroke-width="1"/>'
    )

    # Subtle prompt / chatbot dot and header
    svg_elements.append(
        '  <circle cx="20" cy="18" r="3.5" fill="#58a6ff"/>'
    )
    svg_elements.append(
        '  <text class="txt" x="30" y="21" font-size="10" font-weight="600" fill="#58a6ff" letter-spacing="0.5">HAMZA // INTRO</text>'
    )

    for line_num, line in enumerate(LINES, start=1):
        words = line["words"]
        start_t = line["start_time"]
        tspans = []

        for i, word in enumerate(words):
            delay = start_t + (i * WORD_DELAY)
            css_rules.append(f".w{word_idx} {{ animation-delay: {delay:.3f}s; }}")
            tspans.append(f'<tspan class="w w{word_idx}">{word} </tspan>')
            word_idx += 1

        # Cursor at end of line
        cursor_class = f"cursor c{line_num}"
        tspans.append(f'<tspan class="{cursor_class}">▎</tspan>')

        svg_elements.append(
            f'  <text class="txt" x="20" y="{line["y"]}" font-size="{line["size"]}" '
            f'font-weight="{line["weight"]}" fill="{line["color"]}" xml:space="preserve">'
            + "".join(tspans)
            + "</text>"
        )

    svg_content = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" fill="none">',
        "<style>",
        "\n".join(css_rules),
        "</style>",
        "\n".join(svg_elements),
        "</svg>",
    ]

    return "\n".join(svg_content)


def main():
    svg_str = generate_svg()
    OUTPUT.write_text(svg_str, encoding="utf-8")
    print(f"Generated: {OUTPUT} ({len(svg_str)} bytes)")


if __name__ == "__main__":
    main()
