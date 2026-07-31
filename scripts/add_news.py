"""Script to generate news files"""

import argparse
from pathlib import Path

SECTIONS_LIST = ["Bug fixes", "Docs", "Enhancements", "Deprecations", "Other"]


def has_correct_format(filename: str):
    """New file name format must be followed"""
    if "/" in filename or "\\" in filename or filename.endswith(".md"):
        return False
    if "-" not in filename:
        return False
    pr_number, _ = filename.split("-", 1)
    return pr_number.isdigit()


def news_cli():
    """Logic for news file generator"""

    # configure parser
    parser = argparse.ArgumentParser(
        prog="News File Generator",
        description="Generate a news file with or without the news snippet, using the TEMPLATE in news/",
    )

    parser.add_argument("filename", help="Name of the news file")
    parser.add_argument(
        "--section", help="Section in the news template to be populated with the news snippet"
    )
    parser.add_argument(
        "--message", "-m", "--news", "--news-snippet", dest="message", help="News snippet to add"
    )

    args = parser.parse_args()

    # Both section and message must be provided together, or none.
    if bool(args.section) ^ bool(args.message):
        parser.error("Please provide both `--section` and `--message`")

    if not has_correct_format(args.filename):
        print("News file name must have correct format: <pr/issue_number-file-name>")
        return 1

    repo_root = Path(__file__).resolve().parent.parent
    news_dir = repo_root / "news"

    dest = news_dir / args.filename

    # Reject paths that escape or nest outside news/ directory
    if not dest.resolve().is_relative_to(news_dir.resolve()):
        print("News file must stay inside the `news/` directory")
        return 1

    # Don't overwrite news files
    if dest.exists():
        print("File with this name already exists. Choose a different name.")
        return 1

    # read the TEMPLATE file
    template = news_dir / "TEMPLATE"
    try:
        template_content = template.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        print("Error reading TEMPLATE file or file doesn't exist")
        return 1

    # Populate section with the provided news snippet
    if args.section:
        lines = template_content.splitlines()

        found = False
        for i, line in enumerate(lines):
            if line.lower() == f"### {(args.section).lower()}":
                lines[i + 2] = f"* {args.message}"
                found = True
                break
        if not found:
            print(f"No matching section found. Use one of the following: {SECTIONS_LIST}")
            return 1

        template_content = "\n".join(lines) + "\n"

    # create news file
    try:
        dest.write_text(template_content, encoding="utf-8")
    except OSError:
        print("Error writing to file.")
        return 1
    print(f"News file created: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(news_cli())
