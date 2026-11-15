"""Start the full prototype pipeline.

Stage 1 (DataPopulateEngine): generate synthetic packets, parse them, and
store accepted readings in PocketBase sensor_readings.
Stage 2 (assessmentEngine): read the stored readings back, score the four
health domains, and post domain_assessments records.

After the pipeline run, an interactive console is available for manual
stage commands (populate, assess, history, ...).
"""

import json
import logging

from libs import commands

import engine_conf

logger = logging.getLogger(__name__)

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


_store = None


def get_store():
    """Lazily build the shared PocketBase store for console commands."""
    global _store
    if _store is None:
        _store = DataPopulateEngine.PocketBaseStore.from_environment()
    return _store


def main():
    engine_conf.setup_logging()
    print_art(art)

    store = get_store()
    logger.info("=== Stage 1: populate sensor_readings ===")

    # Stage 1: populate sensor_readings from the synthetic mission.
    ingestion = DataPopulateEngine.populate_story(store)
    print(json.dumps({"ingestion": ingestion}, indent=2))

    logger.info("=== Stage 2: assess crew and post domain_assessments ===")

    # Stage 2: assess every crew member from stored readings and post results.
    assessments = assessmentEngine.assess_all(store)
    print(json.dumps({"assessments": assessments}, indent=2))
    logger.info("Pipeline complete")


# ---------------------------------------------------------
# Console commands (manual stage control)
# ---------------------------------------------------------

@commands.command
def populate():
    """Ingest the 7-day story mission into sensor_readings."""
    print(json.dumps(DataPopulateEngine.populate_story(get_store()), indent=2))


@commands.command
def populate_noise(ticks=5, interval=0):
    """Stream noise-mode generator ticks into sensor_readings."""
    ticks = int(ticks)
    results = DataPopulateEngine.populate_ticks(
        get_store(), "noise", ticks, float(interval))
    print(json.dumps({"ticks": len(results), "last": results[-1] if results else None}, indent=2))


@commands.command
def assess_all():
    """Assess every crew member from stored readings and post results."""
    print(json.dumps(assessmentEngine.assess_all(get_store()), indent=2))


@commands.command
def assess(crew):
    """Assess one crew member (a, b, or c) and post results."""
    print(json.dumps(assessmentEngine.assess_crew(crew, get_store()), indent=2))


@commands.command
def history(crew):
    """Show how many stored readings group into daily packets for a crew."""
    packets = assessmentEngine.load_history(crew, get_store())
    print(json.dumps({
        "crew_id": crew,
        "daily_packets": len(packets),
        "mission_days": sorted({p["mission_day"] for p in packets}),
        "metrics_per_packet": sorted(
            {k for p in packets for k in p if k not in
             ("crew_id", "mission_day", "timestamp")}),
    }, indent=2))


if __name__ == "__main__":
    main()
    commands.start_console()
