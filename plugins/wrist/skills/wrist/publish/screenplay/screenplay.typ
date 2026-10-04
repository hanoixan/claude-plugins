// wrist screenplay template for `pandoc --pdf-engine=typst`. US letter (or the trim size), 12 pt
// monospace, about 55 lines and about a minute a page. Needs typst 0.12 or later.
#set document(title: [$title$])
#set text(
  font: ($if(mainfont)$"$mainfont$", $endif$"Courier Prime", "Courier New", "DejaVu Sans Mono"),
  size: 12pt,
  lang: "$if(lang)$$lang$$else$en$endif$",
  top-edge: 0.8em,
  bottom-edge: -0.2em,
)
#set par(leading: 0pt, spacing: 0pt, justify: false)
#show strong: set text(weight: "bold")

#let sp-heading(body) = block(above: 24pt, below: 0pt, sticky: true, width: 100%)[#strong(upper(body))]
#let sp-action(body) = block(above: 12pt, below: 0pt, width: 100%)[#body]
#let sp-character(body) = block(above: 12pt, below: 0pt, sticky: true, width: 100%, inset: (left: 2.2in))[#upper(body)]
#let sp-parenthetical(body) = block(above: 0pt, below: 0pt, sticky: true, width: 100%, inset: (left: 1.6in, right: 2.0in))[#body]
#let sp-dialogue(body) = block(above: 0pt, below: 0pt, width: 100%, inset: (left: 1.0in, right: 1.5in))[#body]
#let sp-transition(body) = block(above: 12pt, below: 0pt, width: 100%)[#align(right)[#upper(body)]]
#let sp-centered(body) = block(above: 12pt, below: 0pt, width: 100%)[#align(center)[#body]]
#let sp-act(body) = {
  pagebreak(weak: true)
  align(center)[#strong(upper(body))]
  v(24pt)
}

// Title page: no number.
#page(paper: "$if(papersize)$$papersize$$else$us-letter$endif$", margin: (left: 1.5in, right: 1in, top: 1in, bottom: 1in),
      numbering: none, header: none)[
  #v(3in)
  #align(center)[
    #strong(upper[$title$])
    #v(2em)
    Written by
    #v(1em)
    $for(author)$$author$$sep$, $endfor$
    $if(based_on)$
    #v(3em)
    $based_on$
    $endif$
  ]
  $if(contact)$
  #place(bottom + left)[$contact$]
  $endif$
  $if(draft)$
  #place(bottom + right)[$draft$]
  $endif$
  #counter(page).update(0)
]

#set page(
  paper: "$if(papersize)$$papersize$$else$us-letter$endif$",
  margin: (left: 1.5in, right: 1in, top: 1in, bottom: 1in),
  header: context {
    // The first script page carries no number; later pages show it top right as "2."
    if counter(page).get().first() > 1 { align(right)[#counter(page).display("1.")] }
  },
  header-ascent: 50%,
)

$body$
