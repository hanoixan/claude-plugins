-- A pandoc custom reader for wrist's plain verse. An optional first line "# Title" followed by a blank line
-- is the title (a Div of class title). Stanzas are the runs of lines between blank lines; each is a Div of
-- class stanza holding one LineBlock, a line of verse per line. Nothing in a line is markup. Each leading
-- space (a tab counts as four) becomes one en space, U+2002. A run of spaces inside a line reads as one
-- space. The rules here must stay the same as wrist_verse.py; tests/verse_cases.json is checked against both.
local EN = "\u{2002}"

local function is_blank(l) return l == nil or l:match("^[ \t\r\f\v]*$") ~= nil end

local function line_inlines(line)
  local lead = line:match("^[ \t]*")
  local body = line:sub(#lead + 1):gsub("%s+$", "")
  local indent = lead:gsub("\t", "    "):gsub(" ", EN)
  local out, first = {}, true
  for word in body:gmatch("%S+") do
    if not first then out[#out + 1] = pandoc.Space() end
    out[#out + 1] = pandoc.Str(first and (indent .. word) or word)
    first = false
  end
  return out
end

function Reader(input)
  local text = tostring(input):gsub("\r\n", "\n"):gsub("^\u{FEFF}", "")
  local lines = {}
  for l in (text .. "\n"):gmatch("(.-)\n") do lines[#lines + 1] = l end
  local blocks, i, n = {}, 1, #lines
  while i <= n and is_blank(lines[i]) do i = i + 1 end
  if i <= n and lines[i]:match("^# ") and is_blank(lines[i + 1]) and i + 1 <= n then
    local title = lines[i]:gsub("^# ", ""):gsub("%s+$", "")
    blocks[#blocks + 1] = pandoc.Div({pandoc.Para({pandoc.Str(title)})}, pandoc.Attr("", {"title"}))
    i = i + 1
  end
  local stanza = {}
  local function flush()
    if #stanza > 0 then
      blocks[#blocks + 1] = pandoc.Div({pandoc.LineBlock(stanza)}, pandoc.Attr("", {"stanza"}))
      stanza = {}
    end
  end
  while i <= n do
    if is_blank(lines[i]) then flush() else stanza[#stanza + 1] = line_inlines(lines[i]) end
    i = i + 1
  end
  flush()
  return pandoc.Pandoc(blocks)
end
