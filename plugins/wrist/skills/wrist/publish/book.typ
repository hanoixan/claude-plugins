// wrist book template for `pandoc --pdf-engine=typst`.
// Needs typst 0.12 or later. Fonts: Libertinus Serif ships inside typst, so a PDF embeds it
// without anything installed; pass `font` in PREMISE.md for another family.
#let horizontalrule = align(center)[#v(0.9em) #text(tracking: 0.7em)[\*\*\*] #v(0.9em)]
#show terms: it => it.children.map(child => [#strong[#child.term]\ #pad(left: 1.2em)[#child.description]]).join(parbreak())
$if(highlighting-definitions)$
$highlighting-definitions$
$endif$

#set document(title: [$title$])
#set text(
  font: "$if(mainfont)$$mainfont$$else$Libertinus Serif$endif$",
  size: 10.5pt,
  lang: "$if(lang)$$lang$$else$en$endif$",
  hyphenate: true,
)
#set par(justify: true, leading: 0.62em, spacing: 0.62em, first-line-indent: 1.2em)

// Title page: no number, no running head.
#page(paper: "$if(papersize)$$papersize$$else$a5$endif$", margin: 22mm, header: none, footer: none)[
  #align(center + horizon)[
    #text(size: 2.4em, weight: "bold")[$title$]
    #v(1.4em)
    #text(size: 1.15em)[$for(author)$$author$$sep$, $endfor$]
  ]
]

#set page(
  paper: "$if(papersize)$$papersize$$else$a5$endif$",
  margin: (inside: 22mm, outside: 18mm, top: 22mm, bottom: 24mm),
  header: context {
    if counter(page).get().first() > 1 {
      if calc.odd(here().page()) {
        align(right, text(size: 0.85em, style: "italic")[$title$])
      } else {
        align(left, text(size: 0.85em, style: "italic")[$for(author)$$author$$sep$, $endfor$])
      }
    }
  },
  footer: context align(center, text(size: 0.9em)[#counter(page).display()]),
)
#counter(page).update(1)

#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  v(18%)
  align(center, text(size: 1.5em, weight: "bold", it.body))
  v(1.6em)
}
#show heading.where(level: 2): it => {
  v(1.2em)
  align(center, text(size: 1.1em, weight: "bold", it.body))
  v(0.6em)
}

$body$
