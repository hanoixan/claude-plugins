-- Builds a book's front matter from metadata, per output format. Metadata read: copyright,
-- dedication, epigraph (text), and wrist-contents (set when a contents page is wanted in the PDF;
-- the EPUB gets its contents from pandoc's --toc).
local function text_of(meta, key)
  local v = meta[key]
  if v == nil or pandoc.utils.stringify(v) == "" then return nil end
  return pandoc.Para(pandoc.utils.blocks_to_inlines({pandoc.Plain(v)}))
end

local function page(open, para, close)
  return {pandoc.RawBlock("typst", open), para, pandoc.RawBlock("typst", close)}
end

function Pandoc(doc)
  local meta = doc.meta
  local is_typst = FORMAT:match("typst") ~= nil
  local front = {}
  local function add(blocks) for _, b in ipairs(blocks) do front[#front + 1] = b end end

  local copyright = text_of(meta, "copyright")
  if copyright then
    if is_typst then
      add(page("#pagebreak(weak: true)\n#align(bottom)[#set par(first-line-indent: 0pt)\n#text(size: 0.8em)[",
               copyright, "]]"))
    else
      add({pandoc.Div({copyright}, pandoc.Attr("", {"copyright"}))})
    end
  end
  for _, key in ipairs({"dedication", "epigraph"}) do
    local para = text_of(meta, key)
    if para then
      if is_typst then
        add(page("#pagebreak(weak: true)\n#align(center + horizon)[#set par(first-line-indent: 0pt)\n#emph[",
                 para, "]]"))
      else
        add({pandoc.Div({para}, pandoc.Attr("", {key}))})
      end
    end
  end
  if is_typst and meta["wrist-contents"] then
    add({pandoc.RawBlock("typst", "#pagebreak(weak: true)\n#outline(title: [Contents], depth: 1)")})
  end

  local out = {}
  for _, b in ipairs(front) do out[#out + 1] = b end
  for _, b in ipairs(doc.blocks) do out[#out + 1] = b end
  doc.blocks = out
  return doc
end
