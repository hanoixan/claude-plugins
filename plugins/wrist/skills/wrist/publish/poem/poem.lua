-- Turns the reader's stanza Divs into calls of the layout functions in poem.typ for the PDF, and builds
-- the heading block for the EPUB. The title Div the reader emits is dropped: the title is the PREMISE title,
-- printed only when the poem is titled.
local EN = "\u{2002}"
local KEEP_MAX = 16          -- a stanza of up to this many lines is kept whole on a page

local function titled(meta)
  return meta.titled ~= nil and (meta.titled == true or pandoc.utils.stringify(meta.titled) == "true")
end

local function text_of(meta, key)
  local v = meta[key]
  return v and pandoc.utils.stringify(v) or ""
end

-- A leading run of en spaces is measured and removed: the layout function turns it into a Typst horizontal
-- space (half an em each), so the typesetter cannot trim it, and hangs wrapped lines past it.
local function split_indent(inlines)
  local out, lead = {}, 0
  for i, inline in ipairs(inlines) do
    if i == 1 and inline.t == "Str" then
      local rest = inline.text
      while rest:sub(1, #EN) == EN do lead = lead + 1; rest = rest:sub(#EN + 1) end
      out[#out + 1] = pandoc.Str(rest)
    else
      out[#out + 1] = inline
    end
  end
  return out, lead * 0.5
end

function Pandoc(doc)
  local blocks = {}
  for _, b in ipairs(doc.blocks) do
    if not (b.t == "Div" and b.classes[1] == "title") then blocks[#blocks + 1] = b end
  end
  if FORMAT:match("typst") then
    local out = {}
    for _, b in ipairs(blocks) do
      if b.t == "Div" and b.classes[1] == "stanza" then
        local lines = b.content[1].content
        out[#out + 1] = pandoc.RawBlock("typst", "#stanza(" .. (#lines <= KEEP_MAX and "true" or "false") .. ")[")
        for _, line in ipairs(lines) do
          local inlines, lead = split_indent(line)
          out[#out + 1] = pandoc.RawBlock("typst", "#vl(" .. lead .. "em)[")
          out[#out + 1] = pandoc.Plain(inlines)
          out[#out + 1] = pandoc.RawBlock("typst", "]")
        end
        out[#out + 1] = pandoc.RawBlock("typst", "]")
      else
        out[#out + 1] = b
      end
    end
    doc.blocks = out
    return doc
  end
  -- EPUB: a heading is required for the contents, and it must come first or pandoc files what precedes it
  -- in a section of its own. A titled poem shows it; an untitled one gets a hidden heading named after
  -- the working title. The dedication follows it here (the PDF sets it above the title).
  local head = {}
  local title = text_of(doc.meta, "title")
  local dedication, epigraph, author = text_of(doc.meta, "dedication"), text_of(doc.meta, "epigraph"), text_of(doc.meta, "author")
  head[#head + 1] = pandoc.Header(1, {pandoc.Str(title)}, pandoc.Attr(titled(doc.meta) and "poem-title" or "poem-hidden-title", {"unnumbered"}))
  if dedication ~= "" then
    head[#head + 1] = pandoc.Div({pandoc.Para({pandoc.Str(dedication)})}, pandoc.Attr("", {"dedication"}))
  end
  if author ~= "" then
    head[#head + 1] = pandoc.Div({pandoc.Para({pandoc.Str(author)})}, pandoc.Attr("", {"byline"}))
  end
  if epigraph ~= "" then
    head[#head + 1] = pandoc.Div({pandoc.Para({pandoc.Str(epigraph)})}, pandoc.Attr("", {"epigraph"}))
  end
  for _, b in ipairs(blocks) do head[#head + 1] = b end
  doc.blocks = head
  return doc
end
