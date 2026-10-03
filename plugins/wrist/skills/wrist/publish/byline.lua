-- Inserts the author as a byline under the first level-1 heading. Used when a work has no title page.
function Pandoc(doc)
  local author = doc.meta.author
  if not author then return doc end
  local name = pandoc.Para({pandoc.Str(pandoc.utils.stringify(author))})
  local block
  if FORMAT:match("typst") then
    block = {pandoc.RawBlock("typst", "#align(center)[#set par(first-line-indent: 0pt)\n#emph["), name,
             pandoc.RawBlock("typst", "]\n#v(1.2em)]")}
  else
    block = {pandoc.Div({name}, pandoc.Attr("", {"byline"}))}
  end
  for i, b in ipairs(doc.blocks) do
    if b.t == "Header" and b.level == 1 then
      for j = #block, 1, -1 do table.insert(doc.blocks, i + 1, block[j]) end
      break
    end
  end
  return doc
end
