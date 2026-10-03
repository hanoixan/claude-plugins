#!/usr/bin/env python3
"""wrist_publish.py: tool preflight, command planning and building for output/<slug>.epub and .pdf.

Pandoc builds the EPUB and, with Typst as its PDF engine, the PDF. Commands are argument lists and
never go through a shell, so a title with quotes or an ampersand arrives as one argument.
"""
import os
import shutil
import subprocess

TOOLS = ("pandoc", "typst")
INSTALL = {
    "pandoc": "pandoc 3.2 or later: https://pandoc.org/installing.html "
              "(for example `brew install pandoc`, `sudo apt install pandoc`, `winget install JohnMacFarlane.Pandoc`)",
    "typst": "typst 0.12 or later: https://github.com/typst/typst#installation "
             "(for example `brew install typst`, `winget install --id Typst.Typst`, `cargo install --locked typst-cli`)",
}


class PublishError(Exception):
    pass


def missing_tools(path=None):
    return [t for t in TOOLS if shutil.which(t, path=path) is None]


def install_help(missing):
    lines = ["publishing needs these tools, which are not on the path:"]
    lines += [f"  - {INSTALL[t]}" for t in missing]
    return "\n".join(lines)


def plan_commands(sources, meta, out_dir, slug, publish_dir):
    """[(kind, argv)] for the EPUB and the PDF. `meta` has title, author, optional language, trim, font,
    and title_page (default True; False drops the title page and adds a byline under the first heading)."""
    common = ["pandoc", "--from", "markdown+smart", *sources,
              "--metadata", f"title={meta['title']}",
              "--metadata", f"author={meta['author']}",
              "--metadata", f"lang={meta.get('language') or 'en'}"]
    epub = common + ["--to", "epub3", "--css", os.path.join(publish_dir, "epub.css"),
                     "-o", f"{out_dir}/{slug}.epub"]
    pdf = common + ["--pdf-engine=typst", "--template", os.path.join(publish_dir, "book.typ")]
    if not meta.get("title_page", True):
        # The work's own heading is its title; a byline under it replaces the title page.
        byline = ["--lua-filter", os.path.join(publish_dir, "byline.lua")]
        epub = epub[:-2] + ["--epub-title-page=false"] + byline + epub[-2:]
        pdf += ["-V", "no-title-page=true"] + byline
    if meta.get("trim"):
        pdf += ["-V", f"papersize={meta['trim']}"]
    if meta.get("font"):
        pdf += ["-V", f"mainfont={meta['font']}"]
    pdf += ["-o", f"{out_dir}/{slug}.pdf"]
    return [("epub", epub), ("pdf", pdf)]


def run_commands(commands, cwd):
    for kind, argv in commands:
        target = argv[argv.index("-o") + 1]
        os.makedirs(os.path.dirname(os.path.join(cwd, target)), exist_ok=True)
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise PublishError(f"{kind} build failed (exit {proc.returncode}): "
                               f"{proc.stderr.strip() or proc.stdout.strip()}")
