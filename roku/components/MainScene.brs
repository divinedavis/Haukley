sub init()
    m.catalog = loadCatalog()
    m.titles = m.catalog.titles

    m.home = m.top.findNode("home")
    m.rows = m.top.findNode("rows")
    m.heroBack = m.top.findNode("heroBack")
    m.heroFront = m.top.findNode("heroFront")
    m.heroFade = m.top.findNode("heroFade")
    m.heroEyebrow = m.top.findNode("heroEyebrow")
    m.heroTitle = m.top.findNode("heroTitle")
    m.heroMeta = m.top.findNode("heroMeta")
    m.heroDesc = m.top.findNode("heroDesc")
    m.details = m.top.findNode("details")
    m.video = m.top.findNode("video")

    m.history = []
    m.heroId = ""

    buildRows()
    m.rows.observeField("rowItemFocused", "onRowItemFocused")
    m.rows.observeField("rowItemSelected", "onRowItemSelected")
    m.heroFade.observeField("state", "onHeroFadeState")
    m.details.observeField("action", "onDetailsAction")
    m.video.observeField("state", "onVideoState")

    showHero(m.catalog.rows[0].items[0].id)
    m.rows.setFocus(true)
end sub

sub buildRows()
    root = CreateObject("roSGNode", "ContentNode")
    sizes = []
    heights = []
    for each r in m.catalog.rows
        row = root.createChild("ContentNode")
        row.title = r.title
        landscape = (r.type = "card" or r.type = "upNext")
        rank = 0
        for each it in r.items
            t = m.titles[it.id]
            rank = rank + 1
            if r.type = "upNext"
                url = t.stream
                playTitle = t.title
                if it.episode > 0 and t.episodes <> invalid
                    url = t.episodes[it.episode - 1].stream
                    playTitle = t.title + " · Episode " + it.episode.ToStr()
                end if
                addTile(row, t.card, { titleId: t.id, label: t.title, subLabel: it.label, progress: it.progress, action: "play", url: url, playTitle: playTitle })
            else if r.type = "ranked"
                addTile(row, t.poster, { titleId: t.id, label: t.title, subLabel: t.genre, rank: rank })
            else if landscape
                addTile(row, t.card, { titleId: t.id, label: t.title, subLabel: t.genre + " · " + t.year.ToStr() })
            else
                addTile(row, t.poster, { titleId: t.id })
            end if
        end for
        if landscape
            sizes.push([440, 248])
            heights.push(400)
        else if r.type = "ranked"
            sizes.push([240, 360])
            heights.push(520)
        else
            sizes.push([240, 360])
            heights.push(460)
        end if
    end for
    m.rows.rowItemSize = sizes
    m.rows.rowHeights = heights
    m.rows.content = root
end sub

sub showHero(id as string)
    if id = m.heroId then return
    m.heroId = id
    t = m.titles[id]
    if t.kind = "show"
        m.heroEyebrow.text = "NEW SEASON"
    else
        m.heroEyebrow.text = "NOW STREAMING"
    end if
    m.heroTitle.text = t.title
    m.heroMeta.text = metaLine(t)
    m.heroDesc.text = t.description
    m.heroFade.control = "stop"
    m.heroFront.opacity = 0
    m.heroFront.uri = t.backdrop
    m.heroFade.control = "start"
end sub

sub onHeroFadeState()
    if m.heroFade.state = "stopped" and m.heroFront.opacity >= 1
        m.heroBack.uri = m.heroFront.uri
    end if
end sub

function tileAt(rc as object) as object
    return m.rows.content.getChild(rc[0]).getChild(rc[1])
end function

sub onRowItemFocused()
    tile = tileAt(m.rows.rowItemFocused)
    if tile <> invalid then showHero(tile.titleId)
end sub

sub onRowItemSelected()
    tile = tileAt(m.rows.rowItemSelected)
    if tile = invalid then return
    if tile.action = "play"
        playVideo(tile.url, tile.playTitle)
    else
        openDetails(tile.titleId, true)
    end if
end sub

sub openDetails(id as string, push as boolean)
    if push then m.history.push(id)
    t = m.titles[id]
    shelf = []
    if t.kind = "show"
        for each ep in t.episodes
            shelf.push({ poster: ep.still, label: ep.number.ToStr() + ". " + ep.name, subLabel: ep.minutes.ToStr() + " min", action: "play", url: ep.stream, playTitle: t.title + " · Episode " + ep.number.ToStr() })
        end for
    else
        for each key in m.titles
            other = m.titles[key]
            if other.kind = "movie" and other.id <> id and shelf.count() < 8
                shelf.push({ poster: other.card, label: other.title, subLabel: other.genre, action: "open", titleId: other.id })
            end if
        end for
    end if
    m.details.data = { title: t, shelf: shelf }
    m.home.visible = false
    m.details.visible = true
    m.details.setFocus(true)
end sub

sub onDetailsAction()
    a = m.details.action
    if a = invalid then return
    if a.type = "play"
        playVideo(a.url, a.title)
    else if a.type = "open"
        openDetails(a.id, true)
    end if
end sub

sub playVideo(url as string, title as string)
    c = CreateObject("roSGNode", "ContentNode")
    c.url = url
    c.title = title
    c.streamFormat = "hls"
    m.video.content = c
    m.video.visible = true
    m.video.control = "play"
    m.video.setFocus(true)
end sub

sub closeVideo()
    m.video.control = "stop"
    m.video.visible = false
    if m.details.visible
        m.details.setFocus(true)
    else
        m.rows.setFocus(true)
    end if
end sub

sub onVideoState()
    s = m.video.state
    if s = "finished" or s = "error"
        if s = "error" then print "Video error: "; m.video.errorMsg
        closeVideo()
    end if
end sub

function onKeyEvent(key as string, press as boolean) as boolean
    if not press or key <> "back" then return false
    if m.video.visible
        closeVideo()
        return true
    end if
    if m.details.visible
        m.history.pop()
        if m.history.count() > 0
            openDetails(m.history.peek(), false)
        else
            m.details.visible = false
            m.home.visible = true
            m.rows.setFocus(true)
        end if
        return true
    end if
    ' Back on the home screen exits the app, as Roku certification requires.
    return false
end function
