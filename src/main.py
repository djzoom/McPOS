"""
Entry point for Kat Records Studio.
"""

from pathlib import Path


def main() -> None:
    """Bootstrap Kat Records Studio application."""
    project_root = Path(__file__).resolve().parents[1]
    project_name = project_root.name
    print(f"Welcome to Kat Records Studio — {project_name}!")


if __name__ == "__main__":
    main()
