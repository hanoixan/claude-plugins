-- Turns the reader's classed Divs into calls of the layout functions in screenplay.typ for the PDF.
-- For every other format (the EPUB) the Divs stay as they are and the stylesheet styles their classes.
local KINDS = {
  ["scene-heading"] = "sp-heading", action = "sp-action", character = "sp-character",
  dialogue = "sp-dialogue", parenthetical = "sp-parenthetical", transition = "sp-transition",
  centered = "sp-centered", ["act-marker"] = "sp-act",
}

function Pandoc(doc)
  if not FORMAT:match("typst") then
    -- Without a heading before the script pandoc files it under the title and lists that in the contents.
    -- Give it an unlisted heading of its own; the stylesheet hides it.
    local out = {pandoc.Header(1, {pandoc.Str("Screenplay")}, pandoc.Attr("script", {"unlisted", "unnumbered"}))}
    -- The title page lines pandoc's own title page does not show.
    for _, key in ipairs({"based_on", "draft", "contact"}) do
      local v = doc.meta[key]
      if v and pandoc.utils.stringify(v) ~= "" then
        out[#out + 1] = pandoc.Div({pandoc.Para({pandoc.Str(pandoc.utils.stringify(v))})}, pandoc.Attr("", {"title-line"}))
      end
    end
    for _, b in ipairs(doc.blocks) do out[#out + 1] = b end
    doc.blocks = out
    return doc
  end
  local out = {}
  for _, b in ipairs(doc.blocks) do
    local class = b.t == "Div" and b.classes[1]
    if class == "pagebreak" then
      out[#out + 1] = pandoc.RawBlock("typst", "#pagebreak()")
    elseif class and KINDS[class] then
      out[#out + 1] = pandoc.RawBlock("typst", "#" .. KINDS[class] .. "[")
      for _, inner in ipairs(b.content) do out[#out + 1] = inner end
      out[#out + 1] = pandoc.RawBlock("typst", "]")
    else
      out[#out + 1] = b
    end
  end
  doc.blocks = out
  return doc
end
