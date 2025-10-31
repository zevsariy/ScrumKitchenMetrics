"""Populate the second column of a CSV file with owners from a CODEOWNERS file.

Dependencies:
    pip install pathspec

Example:
    python scripts\populate_codeowners.py --csv-in files.csv \
        --codeowners CODEOWNERS --csv-out files_with_owners.csv
"""

import argparse
import csv
from pathlib import PurePosixPath
from typing import Iterable, List, Sequence, Tuple

from pathspec.patterns.gitwildmatch import GitWildMatchPattern


Rule = Tuple[GitWildMatchPattern, Sequence[str]]


def load_codeowners(codeowners_path: str) -> List[Rule]:
    """Parse CODEOWNERS rules into GitWildMatchPattern objects."""
    rules: List[Rule] = []
    with open(codeowners_path, encoding="utf-8") as handle:
        for lineno, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            tokens = line.split()
            if len(tokens) < 2:
                continue
            pattern_token, owners = tokens[0], tokens[1:]
            matcher = GitWildMatchPattern.from_line(
                pattern_token, lineno=lineno, filename=codeowners_path
            )
            rules.append((matcher, owners))
    return rules


def match_owners(rules: Iterable[Rule], path: str) -> List[str]:
    """Collect unique owners for the provided file path while preserving rule order."""
    owners: List[str] = []
    seen = set()
    for matcher, owner_list in rules:
        if matcher.match_file(path):
            for owner in owner_list:
                if owner not in seen:
                    seen.add(owner)
                    owners.append(owner)
    return owners


def enrich_csv(csv_in: str, codeowners_path: str, csv_out: str) -> None:
    """Populate the owner column of the CSV using CODEOWNERS rules."""
    rules = load_codeowners(codeowners_path)

    with open(csv_in, newline="", encoding="utf-8") as source, open(
        csv_out, "w", newline="", encoding="utf-8"
    ) as target:
        reader = csv.reader(source)
        writer = csv.writer(target)

        for row in reader:
            if not row:
                continue
            rel_path = PurePosixPath(row[0].strip().replace("\\", "/")).as_posix()
            owners = match_owners(rules, rel_path)
            if len(row) < 2:
                row.append(" ".join(owners))
            else:
                row[1] = " ".join(owners)
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate CSV owner column based on CODEOWNERS rules."
    )
    parser.add_argument(
        "--csv-in",
        required=True,
        help="Path to the input CSV file containing file paths in the first column.",
    )
    parser.add_argument(
        "--codeowners",
        required=True,
        help="Path to the CODEOWNERS file.",
    )
    parser.add_argument(
        "--csv-out",
        required=True,
        help="Path to write the enriched CSV output.",
    )

    args = parser.parse_args()
    enrich_csv(args.csv_in, args.codeowners, args.csv_out)


if __name__ == "__main__":
    main()
