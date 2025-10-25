"""
Entry point for the Vibe Coding Infra template.
"""

from pathlib import Path


def main() -> None:
    """Bootstrap the template application."""
    project_root = Path(__file__).resolve().parents[1]
    project_name = project_root.name
    print(f"Welcome to {project_name} — powered by Vibe Coding Infra!")


if __name__ == "__main__":
    main()
