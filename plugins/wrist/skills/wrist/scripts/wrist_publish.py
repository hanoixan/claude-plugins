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


MARKER_NAME = ".wrist-body.md"
MARKER = ('```{=typst}\n#in-body.update(true)\n#set page(numbering: "1")\n#counter(page).update(1)\n```\n')
FRONT_KEYS = ("copyright", "dedication", "epigraph")


def plan_commands(inputs, meta, out_dir, slug, publish_dir):
    """[(kind, argv)] for the EPUB and the PDF. `meta` has title, author, optional language, trim, font,
    title_page (default True; False drops the title page and adds a byline under the first heading) and
    front_matter (default False; True adds copyright, dedication, epigraph and a contents page)."""
    def common(files):
        return ["pandoc", "--from", "markdown+smart", *files,
                "--metadata", f"title={meta['title']}",
                "--metadata", f"author={meta['author']}",
                "--metadata", f"lang={meta.get('language') or 'en'}"]

    # The marker only switches the PDF's page numbering; in an EPUB it would become a section of its own.
    epub = common([i for i in inputs if not i.endswith(MARKER_NAME)]) + ["--to", "epub3", "--css", os.path.join(publish_dir, "epub.css"),
                     "-o", f"{out_dir}/{slug}.epub"]
    pdf = common(inputs) + ["--pdf-engine=typst", "--template", os.path.join(publish_dir, "book.typ")]
    if meta.get("trim"):
        pdf += ["-V", f"papersize={meta['trim']}"]
    if meta.get("font"):
        pdf += ["-V", f"mainfont={meta['font']}"]
    pdf += ["-o", f"{out_dir}/{slug}.pdf"]
    extra = {"epub": [], "pdf": []}
    if not meta.get("title_page", True):
        # The work's own heading is its title; a byline under it replaces the title page.
        extra["epub"] += ["--epub-title-page=false", "--lua-filter", os.path.join(publish_dir, "byline.lua")]
        extra["pdf"] += ["-V", "no-title-page=true", "--lua-filter", os.path.join(publish_dir, "byline.lua")]
    if meta.get("front_matter"):
        filt = ["--lua-filter", os.path.join(publish_dir, "frontmatter.lua")]
        for key in FRONT_KEYS:
            if meta.get(key):
                filt += ["--metadata", f"{key}={meta[key]}"]
        extra["epub"] += filt + ["--toc"]
        extra["pdf"] += filt + ["-V", "front-matter=true", "--metadata", "wrist-contents=true"]
    return [("epub", epub[:-2] + extra["epub"] + epub[-2:]), ("pdf", pdf[:-2] + extra["pdf"] + pdf[-2:])]


def with_marker(sources, first_body, out_dir, cwd):
    """The pandoc inputs with a marker file before the first body file, so the PDF switches from roman
    to arabic page numbers there. Returns (inputs, marker path or None)."""
    if first_body is None or first_body not in sources:
        return list(sources), None
    os.makedirs(os.path.join(cwd, out_dir), exist_ok=True)
    marker = f"{out_dir}/{MARKER_NAME}"
    with open(os.path.join(cwd, marker), "w", encoding="utf-8") as fh:
        fh.write(MARKER)
    inputs = list(sources)
    inputs.insert(inputs.index(first_body), marker)
    return inputs, marker


def remove_marker(marker, cwd):
    if marker:
        try:
            os.remove(os.path.join(cwd, marker))
        except FileNotFoundError:
            pass


def run_commands(commands, cwd):
    for kind, argv in commands:
        target = argv[argv.index("-o") + 1]
        os.makedirs(os.path.dirname(os.path.join(cwd, target)), exist_ok=True)
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise PublishError(f"{kind} build failed (exit {proc.returncode}): "
                               f"{proc.stderr.strip() or proc.stdout.strip()}")


STYLES = ("story", "book", "screenplay")
NUMBER_WORDS = ("ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN")
SCREENPLAY_KEYS = ("based_on", "draft", "contact")


def style_for(profile):
    """The publishing style: the profile's own, else `book` when it has a sequence function, else `story`."""
    style = getattr(profile, "publish_style", None)
    if style is None:
        return "book" if any(spec["sequence"] for spec in profile.functions.values()) else "story"
    if style not in STYLES:
        raise PublishError(f"unknown publishing style '{style}' (known: {', '.join(STYLES)})")
    return style


def with_act_markers(sources, act_files, out_dir, cwd):
    """The pandoc inputs with a one-line marker file before each act file, so the script can print
    ACT ONE, ACT TWO... Returns (inputs, marker paths)."""
    markers, inputs = [], []
    os.makedirs(os.path.join(cwd, out_dir), exist_ok=True)
    for source in sources:
        if source in act_files:
            n = act_files.index(source)
            marker = f"{out_dir}/.wrist-act-{n + 1}.md"
            with open(os.path.join(cwd, marker), "w", encoding="utf-8") as fh:
                fh.write(f"@@ACT {NUMBER_WORDS[n]}@@\n")
            markers.append(marker)
            inputs.append(marker)
        inputs.append(source)
    return inputs, markers


def remove_markers(markers, cwd):
    for marker in markers:
        remove_marker(marker, cwd)


def plan_screenplay(inputs, meta, out_dir, slug, publish_dir):
    """[(kind, argv)] for a screenplay: Fountain read by the custom reader, the Typst filter for the PDF.
    `meta` has title, author, optional language, trim, font, based_on, draft and contact."""
    folder = os.path.join(publish_dir, "screenplay")
    common = ["pandoc", "--from", os.path.join(folder, "fountain.lua"), *inputs,
              "--metadata", f"title={meta['title']}",
              "--metadata", f"author={meta['author']}",
              "--metadata", f"lang={meta.get('language') or 'en'}"]
    for key in SCREENPLAY_KEYS:
        if meta.get(key):
            common += ["--metadata", f"{key}={meta[key]}"]
    filt = ["--lua-filter", os.path.join(folder, "screenplay.lua")]
    epub = common + ["--to", "epub3", "--css", os.path.join(folder, "screenplay.css")] + filt \
        + ["-o", f"{out_dir}/{slug}.epub"]
    pdf = common + filt + ["--template", os.path.join(folder, "screenplay.typ"), "--pdf-engine=typst"]
    if meta.get("trim"):
        pdf += ["-V", f"papersize={meta['trim']}"]
    if meta.get("font"):
        pdf += ["-V", f"mainfont={meta['font']}"]
    pdf += ["-o", f"{out_dir}/{slug}.pdf"]
    return [("epub", epub), ("pdf", pdf)]
