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
    ' These titles aren't exclusive, and they stream in HD/SD without captions yet: no
    ' "Original", 4K, HDR or CC claims.
    if isLive(t)
        m.eyebrow.text = "LIVE CHANNEL · FREE"
    else if t.kind = "show"
        m.eyebrow.text = "STREAMING FREE · SERIES"
    else
        m.eyebrow.text = "STREAMING FREE"
    end if
    m.title.text = t.title
    m.meta.text = metaLine(t)
    ' A content advisory takes the tagline's place, so it's the first thing read under the title.
    if t.advisory <> invalid and t.advisory <> ""
        m.tagline.text = "Advisory: " + t.advisory
    else
        m.tagline.text = t.tagline
    end if
    m.desc.text = t.description
    ' Creative Commons titles must show their attribution; public domain ones don't need a line.
    credits = t.credits
    if t.license <> invalid and t.license <> "" and Instr(1, t.license, "Public domain") = 0
        credits = credits + chr(10) + t.license
    end if
    m.credits.text = credits

    primary = primaryPlay(t)
    r = d.resume
    if r <> invalid
        ' Bookmarked: Resume first, then start over from the same item.
        resumeLabel = "Resume " + formatClock(r.at)
        if r.episode > 0 then resumeLabel = "Resume E" + r.episode.ToStr() + " · " + formatClock(r.at)
        m.actions = [
            { type: "play", url: r.url, title: r.title, id: t.id, episode: r.episode, ads: true, startAt: r.at }
            { type: "play", url: r.url, title: r.title, id: t.id, episode: r.episode, ads: true, startAt: 0 }
        ]
        buildButtons([resumeLabel, "Play from Beginning"])
    else
        m.actions = [primary.action]
        buildButtons([primary.label])
    end if

    root = CreateObject("roSGNode", "ContentNode")
    row = root.createChild("ContentNode")
    if t.kind = "show"
        row.title = "Episodes"
        m.shelf.rowItemSize = [[400, 225]]
    else if isLive(t)
        row.title = "More to Watch"
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
        if s.episode <> invalid then f.episode = s.episode
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
        m.top.action = { type: "play", url: tile.url, title: tile.playTitle, id: tile.titleId, episode: tile.episode, ads: true, startAt: bookmarkFor(tile.titleId, tile.episode) }
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
