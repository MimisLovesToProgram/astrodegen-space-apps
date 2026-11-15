"""Start the full prototype pipeline.

Stage 1 (DataPopulateEngine): generate synthetic packets, parse them, and
store accepted readings in PocketBase sensor_readings.
Stage 2 (assessmentEngine): read the stored readings back, score the four
health domains, and post domain_assessments records.
"""

import json

import DataPopulateEngine
import assessmentEngine


def print_art(ascii_art):
    # Classic 6-stripe Pride flag truecolor ANSI codes
    pride_colors = [
        "\033[38;2;228;3;3m",    # Red
        "\033[38;2;255;140;0m",  # Orange
        "\033[38;2;255;237;0m",  # Yellow
        "\033[38;2;0;128;38m",   # Green
        "\033[38;2;0;76;255m",   # Blue
        "\033[38;2;117;7;135m"   # Purple
    ]
    reset = "\033[0m"

    # Split the art into individual lines and apply a pride color to each line
    lines = ascii_art.strip("\n").split("\n")
    for i, line in enumerate(lines):
        color = pride_colors[i % len(pride_colors)]
        print(f"{color}{line}{reset}")


# Your ASCII art
art = """░█▀█░█▀▀░▀█▀░█▀▄░█▀█░█▀▄░█▀▀░█▀▀░█▀▀░█▀█░░░█▀▀░█▀▀░█▀▄░█░█░█▀▀░█▀▄
░█▀█░▀▀█░░█░░█▀▄░█░█░█░█░█▀▀░█░█░█▀▀░█░█░░░▀▀█░█▀▀░█▀▄░▀▄▀░█▀▀░█▀▄
░▀░▀░▀▀▀░░▀░░▀░▀░▀▀▀░▀▀░░▀▀▀░▀▀▀░▀▀▀░▀░▀░░░▀▀▀░▀▀▀░▀░▀░░▀░░▀▀▀░▀░▀"""


def main():
    print_art(art)

    store = DataPopulateEngine.PocketBaseStore.from_environment()

    # Stage 1: populate sensor_readings from the synthetic mission.
    ingestion = DataPopulateEngine.populate_story(store)
    print(json.dumps({"ingestion": ingestion}, indent=2))

    # Stage 2: assess every crew member from stored readings and post results.
    assessments = assessmentEngine.assess_all(store)
    print(json.dumps({"assessments": assessments}, indent=2))


if __name__ == "__main__":
    main()
