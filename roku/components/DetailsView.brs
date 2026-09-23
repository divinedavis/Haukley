sub init()
    m.backdrop = m.top.findNode("backdrop")
    m.eyebrow = m.top.findNode("eyebrow")
    m.title = m.top.findNode("title")
    m.meta = m.top.findNode("meta")
    m.tagline = m.top.findNode("tagline")
    m.desc = m.top.findNode("desc")
    m.credits = m.top.findNode("credits")
    m.buttonGroup = m.top.findNode("buttons")
    m.shelf = m.top.findNode("shelf")
    m.shelf.observeField("rowItemSelected", "onShelfSelected")
    m.buttons = []
    m.btn = 0
    m.area = "buttons"
end sub

sub onData()
    d = m.top.data
    t = d.title
    m.t = t
    m.backdrop.uri = t.backdrop
    if t.kind = "show"
        m.eyebrow.text = "STREAMTV ORIGINAL SERIES"
    else
        m.eyebrow.text = "STREAMTV ORIGINAL FILM"
    end if
    m.title.text = t.title
    m.meta.text = metaLine(t) + "  ·  4K  ·  HDR  ·  CC"
    m.tagline.text = t.tagline
    m.desc.text = t.description
    m.credits.text = t.credits

    playLabel = "Play"
    playUrl = t.stream
    playTitle = t.title
    if t.kind = "show"
        playLabel = "Play S1, E1"
        playUrl = t.episodes[0].stream
        playTitle = t.title + " · Episode 1"
    end if
    m.actions = [
        { type: "play", url: playUrl, title: playTitle }
        { type: "play", url: t.stream, title: t.title + " · Trailer" }
    ]
    buildButtons([playLabel, "Trailer"])

    root = CreateObject("roSGNode", "ContentNode")
    row = root.createChild("ContentNode")
    if t.kind = "show"
        row.title = "Season 1"
        m.shelf.rowItemSize = [[400, 225]]
    else
        row.title = "More Like This"
        m.shelf.rowItemSize = [[400, 225]]
    end if
    for each s in d.shelf
        f = { label: s.label, subLabel: s.subLabel, action: s.action }
        if s.url <> invalid then f.url = s.url
        if s.playTitle <> invalid then f.playTitle = s.playTitle
        if s.titleId <> invalid then f.titleId = s.titleId
        addTile(row, s.poster, f)
    end for
    m.shelf.content = root
    m.shelf.jumpToRowItem = [0, 0]

    m.area = "buttons"
    m.btn = 0
    updateButtons()
end sub

' Pill buttons: a white rounded 9-patch that is translucent at rest and solid when focused.
sub buildButtons(labels as object)
    m.buttonGroup.removeChildrenIndex(m.buttonGroup.getChildCount(), 0)
    m.buttons = []
    x = 0
    for each text in labels
        g = m.buttonGroup.createChild("Group")
        g.translation = [x, 0]
        w = 60 + Len(text) * 17
        bg = g.createChild("Poster")
        bg.uri = "pkg:/images/pill.9.png"
        bg.width = w
        bg.height = 76
        lbl = g.createChild("Label")
        lbl.text = text
        lbl.width = w
        lbl.height = 76
        lbl.horizAlign = "center"
        lbl.vertAlign = "center"
        f = CreateObject("roSGNode", "Font")
        f.uri = "pkg:/fonts/Poppins-SemiBold.ttf"
        f.size = 28
        lbl.font = f
        m.buttons.push({ bg: bg, label: lbl })
        x = x + w + 20
    end for
end sub

sub updateButtons()
    for i = 0 to m.buttons.count() - 1
        b = m.buttons[i]
        if m.area = "buttons" and i = m.btn
            b.bg.opacity = 1.0
            b.label.color = "0x000000FF"
        else
            b.bg.opacity = 0.18
            b.label.color = "0xFFFFFFFF"
        end if
    end for
end sub

sub onShelfSelected()
    rc = m.shelf.rowItemSelected
    tile = m.shelf.content.getChild(rc[0]).getChild(rc[1])
    if tile.action = "play"
        m.top.action = { type: "play", url: tile.url, title: tile.playTitle }
    else
        m.top.action = { type: "open", id: tile.titleId }
    end if
end sub

function onKeyEvent(key as string, press as boolean) as boolean
    if not press then return false
    if m.area = "buttons"
        if key = "left" and m.btn > 0
            m.btn = m.btn - 1
            updateButtons()
            return true
        else if key = "right" and m.btn < m.buttons.count() - 1
            m.btn = m.btn + 1
            updateButtons()
            return true
        else if key = "down"
            m.area = "shelf"
            updateButtons()
            m.shelf.setFocus(true)
            return true
        else if key = "OK"
            m.top.action = m.actions[m.btn]
            return true
        end if
    else if m.area = "shelf" and key = "up"
        m.area = "buttons"
        updateButtons()
        m.top.setFocus(true)
        return true
    end if
    return false
end function
