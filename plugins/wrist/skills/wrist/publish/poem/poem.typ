// wrist poem template for `pandoc --pdf-engine=typst`. A5 (or the trim size), flush left, never justified.
// Needs typst 0.12 or later.
#set document(title: [$title$])
#set text(
  font: ($if(mainfont)$"$mainfont$", $endif$"Libertinus Serif", "DejaVu Serif"),
  size: 11pt,
  lang: "$if(lang)$$lang$$else$en$endif$",
)
#set par(justify: false, leading: 0.55em, spacing: 0.55em)
#set page(
  paper: "$if(papersize)$$papersize$$else$a5$endif$",
  margin: (x: 2.2cm, y: 2.4cm),
  numbering: none,
  footer: context {
    if counter(page).get().first() > 1 { align(center)[#counter(page).display("1")] }
  },
)

#let stanza(keep, body) = block(breakable: not keep, above: 0pt, below: 1.4em, width: 100%)[#body]
#let vl(lead, body) = block(above: 0pt, below: 0.55em, width: 100%)[#par(hanging-indent: lead + 1.5em)[#h(lead)#body]]

$if(dedication)$
#align(right)[#emph[$dedication$]]
#v(2em)
$endif$
$if(titled)$
#block(below: 0.6em)[#text(weight: "bold", size: 1.3em)[$title$]]
$endif$
$if(author)$
#block(below: 1.6em)[#emph[$for(author)$$author$$sep$, $endfor$]]
$endif$
$if(epigraph)$
#block(below: 1.8em, inset: (left: 1.5em))[#emph[$epigraph$]]
$endif$

$body$
