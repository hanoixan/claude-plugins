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

-- The heading fields go into the document as Plain blocks, so pandoc escapes a leading list or heading
-- marker ("- ", "1. ", "= ") as it does in a verse line, instead of the template reading it as markup.
local function words(text)
  local out = {}
  for w in text:gmatch("%S+") do
    if #out > 0 then out[#out + 1] = pandoc.Space() end
    out[#out + 1] = pandoc.Str(w)
  end
  return out
end

local function heading_blocks(meta)
  local out = {}
  local function emit(fn, text)
    if text ~= "" then
      out[#out + 1] = pandoc.RawBlock("typst", "#" .. fn .. "[")
      out[#out + 1] = pandoc.Plain(words(text))
      out[#out + 1] = pandoc.RawBlock("typst", "]")
    end
  end
  emit("poem-dedication", text_of(meta, "dedication"))
  if titled(meta) then emit("poem-title", text_of(meta, "title")) end
  local authors = {}
  if meta.author and meta.author.t == "MetaList" then
    for _, a in ipairs(meta.author) do authors[#authors + 1] = pandoc.utils.stringify(a) end
  else
    authors[1] = text_of(meta, "author")
  end
  emit("poem-byline", table.concat(authors, ", "))
  emit("poem-epigraph", text_of(meta, "epigraph"))
  return out
end

function Pandoc(doc)
  local blocks = {}
  for _, b in ipairs(doc.blocks) do
    if not (b.t == "Div" and b.classes[1] == "title") then blocks[#blocks + 1] = b end
  end
  if FORMAT:match("typst") then
    local out = heading_blocks(doc.meta)
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
