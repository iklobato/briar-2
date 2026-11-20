"""briar2 CLI — argparse entry point.

Usage:
    briar2 serve <company>       # run one company
    briar2 serve --all           # run all companies in config dir
    briar2 --version
    briar2 --help
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from briar2 import __version__


@dataclass(frozen=True)
class CliArgs:
    """Parsed CLI arguments (D7)."""

    command: str
    company: str | None = None
    all_companies: bool = False
    config_dir: str = "companies"


class _Cli:
    """Command-line interface.

    Every function lives inside this class (D6, D7).
    """

    def main(self, argv: list[str] | None = None) -> int:
        """Entry point bound to the `briar2` console script."""
        args = self._parse(argv)
        if args.command == "serve":
            return self._cmd_serve(args)
        return 1

    def _parse(self, argv: list[str] | None) -> CliArgs:
        parser = self._build_parser()
        parsed = parser.parse_args(argv)
        return CliArgs(
            command=parsed.command,
            company=parsed.company,
            all_companies=parsed.all,
            config_dir=parsed.config_dir,
        )

    def _build_parser(self) -> argparse.ArgumentParser:
        root = argparse.ArgumentParser(
            prog="briar2",
            description="Multi-company event-driven CLI: poll, queue, agent, action",
        )
        root.add_argument(
            "--version", action="version", version=f"%(prog)s {__version__}"
        )
        self._add_serve_parser(root)
        return root

    def _add_serve_parser(self, root: argparse.ArgumentParser) -> None:
        """Add the serve subcommand to the root parser."""
        sub = root.add_subparsers(dest="command")
        serve = sub.add_parser("serve", help="Run the event orchestrator for a company")
        serve.add_argument(
            "company", nargs="?", help="Company name (directory under companies/)"
        )
        serve.add_argument(
            "--all", action="store_true", help="Run all configured companies"
        )
        serve.add_argument(
            "--config-dir",
            default="companies",
            help="Directory containing per-company config dirs (default: companies/)",
        )

    def _cmd_serve(self, args: CliArgs) -> int:
        from briar2.logging import BriarLogger
        from briar2.orchestrator import Orchestrator

        log = BriarLogger.build("serve")
        orch = Orchestrator(args.config_dir, log=log)

        if args.all_companies and args.company:
            log.error("specify either <company> or --all, not both")
            return 1
        if args.all_companies:
            orch.run_all()
            return 0
        company = args.company
        if not company:
            log.error("specify <company> or --all")
            return 1
        orch.run_company(company)
        return 0


MAIN = _Cli().main


if __name__ == "__main__":
    raise SystemExit(MAIN())
