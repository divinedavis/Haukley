sub init()
    m.art = m.top.findNode("art")
    m.ring = m.top.findNode("ring")
    m.placeholder = m.top.findNode("placeholder")
    m.poster = m.top.findNode("poster")
    m.progTrack = m.top.findNode("progTrack")
    m.progFill = m.top.findNode("progFill")
    m.rank = m.top.findNode("rank")
    m.label = m.top.findNode("label")
    m.sub = m.top.findNode("sub")
end sub

sub onSize()
    w = m.top.width
    h = m.top.height
    m.poster.width = w
    m.poster.height = h
    m.placeholder.width = w
    m.placeholder.height = h
    m.ring.width = w + 12
    m.ring.height = h + 12
    m.ring.translation = [-6, -6]
    m.art.scaleRotateCenter = [w / 2, h / 2]
    m.progTrack.translation = [18, h - 22]
    m.progTrack.width = w - 36
    m.progFill.translation = [18, h - 22]
    layoutLabels()
    updateProgress()
end sub

sub onContent()
    c = m.top.itemContent
    if c = invalid then return
    m.poster.uri = c.HDPosterUrl
    m.label.text = c.label
    m.sub.text = c.subLabel
    if c.rank > 0
        m.rank.text = c.rank.ToStr()
        m.rank.visible = true
    else
        m.rank.visible = false
    end if
    layoutLabels()
    updateProgress()
end sub

sub layoutLabels()
    y = m.top.height + 22
    x = 0
    if m.rank.visible
        m.rank.translation = [0, y]
        x = 40
    end if
    m.label.translation = [x, y]
    m.label.width = m.top.width - x
    m.sub.translation = [x, y + 32]
    m.sub.width = m.top.width - x
end sub

sub updateProgress()
    c = m.top.itemContent
    if c = invalid or c.progress <= 0
        m.progTrack.visible = false
        m.progFill.visible = false
        return
    end if
    m.progTrack.visible = true
    m.progFill.visible = true
    fill = c.progress
    if fill < 0.03 then fill = 0.03
    m.progFill.width = (m.top.width - 36) * fill
end sub

sub onFocus()
    p = m.top.focusPercent
    if not m.top.rowListHasFocus then p = 0
    s = 1 + 0.08 * p
    m.art.scale = [s, s]
    m.ring.opacity = p
    if p > 0.5
        m.label.color = "0xFFFFFFFF"
    else
        m.label.color = "0xFFFFFF9E"
    end if
    ' Push labels down as the art grows, like tvOS.
    y = m.top.height + 22 + 14 * p
    m.rank.translation = [0, y]
    x = 0
    if m.rank.visible then x = 40
    m.label.translation = [x, y]
    m.sub.translation = [x, y + 32]
end sub
