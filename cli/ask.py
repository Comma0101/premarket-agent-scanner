"""CLI: ask the premarket scanner a natural-language question.

Requires the 'anthropic' package and ANTHROPIC_API_KEY in the environment.
Until those are set, use the structured commands (scan_premarket, list_universes).

Examples:
    python -m cli.ask "Which MAG7 names are gapping up over 1% premarket?"
    python -m cli.ask "What is NVDA doing premarket?"
"""

from __future__ import annotations

import typer

app = typer.Typer(add_completion=False, help="Ask the scanner in plain English.")


@app.command()
def main(
    question: str = typer.Argument(..., help="Your question about premarket movers."),
    model: str = typer.Option("claude-opus-4-8", "--model", help="Claude model id."),
) -> None:
    try:
        from agent_tools.runner import PremarketAgent
    except ImportError as exc:
        typer.echo(f"Agent runner unavailable: {exc}", err=True)
        raise typer.Exit(1)

    try:
        agent = PremarketAgent(model=model)
        answer = agent.ask(question)
    except RuntimeError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    typer.echo(answer)


if __name__ == "__main__":
    app()
