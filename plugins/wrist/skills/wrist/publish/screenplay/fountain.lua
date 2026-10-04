-- A pandoc custom reader for Fountain 1.1, the plain-text screenplay format. It emits one Div per
-- element with the element's name as its class: scene-heading, action, character, dialogue, parenthetical,
-- transition, centered, act-marker. A page break is an empty Div with class pagebreak.
-- The rules here must stay the same as wrist_lint.py; tests/fountain_cases.json is checked against both.
local OPTS = "markdown-smart-citations-raw_html-raw_tex-tex_math_dollars-autolink_bare_uris-fancy_lists"

-- Inline text is read as restricted markdown so *emphasis* works. A line that does not read as a single
-- paragraph (it looks like a list or a heading) is kept literally.
local function inlines(text)
  local blocks = pandoc.read(text, OPTS).blocks
  if #blocks == 1 and (blocks[1].t == "Para" or blocks[1].t == "Plain") then return blocks[1].content end
  return {pandoc.Str(text)}
end

local function is_blank(l) return l == nil or l:match("^%s*$") ~= nil end

local function upper_name(line)
  local core = line:gsub("%s*%b()%s*$", "")
  return core:match("%a") ~= nil and core == core:upper() and core:match("%S") ~= nil
end

local SCENE_STARTS = {"INT%./EXT", "INT/EXT", "INT", "EXT", "EST", "I/E"}
local function natural_heading(line)
  local up = line:upper()
  for _, s in ipairs(SCENE_STARTS) do
    local a, b = up:find("^" .. s)
    if a and (up:sub(b + 1, b + 1):match("[%. ]") ~= nil) then return true end
  end
  return false
end

local function div(class, text)
  return pandoc.Div({pandoc.Para(inlines(text))}, pandoc.Attr("", {class}))
end

function Reader(input)
  local text = tostring(input):gsub("\r\n", "\n"):gsub("/%*.-%*/", ""):gsub("%[%[.-%]%]", "")
  local lines = {}
  for l in (text .. "\n"):gmatch("(.-)\n") do lines[#lines + 1] = l end
  local blocks, i, n = {}, 1, #lines
  while i <= n do
    local line = lines[i]
    local prev_blank, next_blank = (i == 1) or is_blank(lines[i - 1]), is_blank(lines[i + 1])
    if is_blank(line) then
      i = i + 1
    elseif line:match("^===+%s*$") then
      blocks[#blocks + 1] = pandoc.Div({}, pandoc.Attr("", {"pagebreak"})); i = i + 1
    elseif line:match("^@@ACT .-@@%s*$") then
      blocks[#blocks + 1] = div("act-marker", line:match("^@@(ACT .-)@@%s*$")); i = i + 1
    elseif line:match("^#") or (line:match("^=") and not line:match("^===")) then
      i = i + 1                                                   -- sections and synopses are dropped
    elseif line:match("^%.[^%.]") or (natural_heading(line) and prev_blank and next_blank) then
      local t = line:gsub("^%.", ""):gsub("%s*#[%w%.%-]+#%s*$", "")
      blocks[#blocks + 1] = div("scene-heading", t); i = i + 1
    elseif line:match("^>%s*.-%s*<%s*$") then
      blocks[#blocks + 1] = div("centered", line:match("^>%s*(.-)%s*<%s*$")); i = i + 1
    elseif line:match("^>") or (upper_name(line) and line:match("TO:%s*$") and prev_blank and next_blank) then
      blocks[#blocks + 1] = div("transition", (line:gsub("^>%s*", ""))); i = i + 1
    elseif line:match("^!") then
      blocks[#blocks + 1] = div("action", (line:gsub("^!", ""))); i = i + 1
    elseif prev_blank and not next_blank and (line:match("^@") or (upper_name(line) and not line:match("TO:%s*$"))) then
      blocks[#blocks + 1] = div("character", (line:gsub("^@", ""):gsub("%^%s*$", ""))); i = i + 1
      local buf = {}
      local function flush()
        if #buf > 0 then blocks[#blocks + 1] = div("dialogue", table.concat(buf, "\n")); buf = {} end
      end
      while i <= n and not is_blank(lines[i]) do
        if lines[i]:match("^%s*%(.*%)%s*$") then
          flush(); blocks[#blocks + 1] = div("parenthetical", (lines[i]:gsub("^%s+", ""):gsub("%s+$", "")))
        else buf[#buf + 1] = lines[i] end
        i = i + 1
      end
      flush()
    else
      local buf = {}
      while i <= n and not is_blank(lines[i]) do buf[#buf + 1] = lines[i]; i = i + 1 end
      blocks[#blocks + 1] = div("action", table.concat(buf, "\n"))
    end
  end
  return pandoc.Pandoc(blocks)
end
