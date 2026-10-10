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
    m.top.observeField("deepLink", "onDeepLink")

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
                addTile(row, t.card, { titleId: t.id, label: t.title, subLabel: it.label, progress: it.progress, action: "play", url: url, playTitle: playTitle, episode: it.episode })
            else if r.type = "ranked"
                addTile(row, t.poster, { titleId: t.id, label: t.title, subLabel: t.genre, rank: rank })
            else if landscape
                subLabel = t.genre + " · " + t.year.ToStr()
                if isLive(t) then subLabel = "Live 24/7 · " + t.genre
                addTile(row, t.card, { titleId: t.id, label: t.title, subLabel: subLabel })
            else
                addTile(row, t.poster, { titleId: t.id })
            end if
        end for
        if landscape
            sizes.push([440, 248])
            ' 248 tile + title + caption + gap: at 400 the caption sat on the next row's heading
            heights.push(440)
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
    if isLive(t)
        m.heroEyebrow.text = "LIVE NOW"
    else if t.kind = "show"
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
        playVideo(tile.url, tile.playTitle, tile.titleId, tile.episode, true, bookmarkFor(tile.titleId, tile.episode))
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
            shelf.push({ poster: ep.still, label: ep.number.ToStr() + ". " + ep.name, subLabel: ep.minutes.ToStr() + " min", action: "play", url: ep.stream, playTitle: t.title + " · Episode " + ep.number.ToStr(), titleId: t.id, episode: ep.number })
        end for
    else
        for each key in m.titles
            other = m.titles[key]
            if other.kind = "movie" and other.id <> id and shelf.count() < 8
                shelf.push({ poster: other.card, label: other.title, subLabel: other.genre, action: "open", titleId: other.id })
            end if
        end for
    end if
    m.details.data = { title: t, shelf: shelf, resume: resumeTarget(t) }
    m.home.visible = false
    m.details.visible = true
    m.details.setFocus(true)
end sub

sub onDetailsAction()
    a = m.details.action
    if a = invalid then return
    if a.type = "play"
        playVideo(a.url, a.title, a.id, a.episode, a.ads, a.startAt)
    else if a.type = "open"
        openDetails(a.id, true)
    end if
end sub

' The details page offers "Resume" for the most recently bookmarked movie or episode.
function resumeTarget(t as object) as dynamic
    if isLive(t) then return invalid
    if t.kind <> "show"
        at = bookmarkFor(t.id, 0)
        if at > 0 then return { episode: 0, at: at, url: t.stream, title: t.title }
        return invalid
    end if
    marks = loadBookmarks()
    best = invalid
    for each ep in t.episodes
        mark = marks[bookmarkKey(t.id, ep.number)]
        if mark <> invalid and (best = invalid or mark.t > best.t)
            best = { episode: ep.number, at: mark.p, url: ep.stream, title: t.title + " · Episode " + ep.number.ToStr(), t: mark.t }
        end if
    end for
    return best
end function

sub playVideo(url as string, title as string, titleId as string, episode as integer, withAds as boolean, startAt = 0 as integer)
    t = m.titles[titleId]
    live = isLive(t)
    if live
        withAds = false
        startAt = 0
    end if
    c = videoContent(url, title, live)
    ' Bookmark resume (Roku certification: long-form VOD resumes where the viewer stopped).
    if startAt > 0 then c.PlayStart = startAt
    ' Side-loaded captions when the catalog has them; HLS-embedded captions are picked up by
    ' the Video node, which also applies the viewer's global caption settings and exposes
    ' On / Off / On replay / On mute in its options (*) menu.
    if t.captions <> invalid and t.captions <> ""
        c.SubtitleTracks = [{ Language: "eng", TrackName: t.captions, Description: "English" }]
    end if
    m.video.content = c

    adUrl = ""
    if withAds
        ' title_id rides in the ad request so the ad server can report revenue per film.
        adUrl = m.catalog.ads.adTagTemplate.Replace("{TITLE_ID}", titleId).Replace("{KIND}", t.kind)
        adUrl = adUrl.Replace("{CORRELATOR}", CreateObject("roDateTime").AsSeconds().ToStr())
    end if
    m.player = CreateObject("roSGNode", "PlayerTask")
    m.player.video = m.video
    m.player.adUrl = adUrl
    m.player.titleId = titleId
    m.player.genre = t.genre
    m.player.episode = episode
    ' Trailers and live channels don't leave a bookmark.
    m.player.bookmark = withAds and not live
    m.player.trackingUrl = m.catalog.ads.trackingUrl
    m.player.apiKey = m.catalog.ads.publishableKey
    m.player.observeField("done", "onPlayerDone")
    m.player.control = "RUN"
end sub

' ---- Deep linking ----------------------------------------------------------------------
' contentId is a title id ("night-line") or an episode id ("borough-e3"), the same ids the
' Roku Search feed will publish. Playable media types go straight to playback (Direct to
' Play, resuming from any bookmark); series/season open the title page. Unknown ids leave
' the viewer on Home.
sub onDeepLink()
    link = m.top.deepLink
    if link = invalid then return
    ' A deep link can arrive mid-playback (roInput); finish closing the player first.
    if m.video.visible
        m.pendingLink = link
        m.video.control = "stop"
        return
    end if
    handleDeepLink(link)
end sub

sub handleDeepLink(link as object)
    id = link.contentId
    mediaType = ""
    if link.mediaType <> invalid then mediaType = LCase(link.mediaType)
    episode = 0
    parts = CreateObject("roRegex", "^(.+)-e([0-9]+)$", "").Match(id)
    if parts.Count() = 3 and m.titles[parts[1]] <> invalid
        id = parts[1]
        episode = parts[2].ToInt()
    end if
    t = m.titles[id]
    if t = invalid
        print "deep link: unknown contentId "; link.contentId
        return
    end if

    m.history = []
    if mediaType = "series" or mediaType = "season" or (t.kind = "show" and episode = 0 and mediaType <> "episode")
        openDetails(t.id, true)
        return
    end if

    if isLive(t)
        playVideo(t.stream, t.title, t.id, 0, false, 0)
    else if t.kind = "show"
        if episode < 1 or episode > t.episodes.Count() then episode = 1
        ep = t.episodes[episode - 1]
        playVideo(ep.stream, t.title + " · Episode " + episode.ToStr(), t.id, episode, true, bookmarkFor(t.id, episode))
    else
        playVideo(t.stream, t.title, t.id, 0, true, bookmarkFor(t.id, 0))
    end if
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

' The task ends on content end, a Back press during ads, or an error.
sub onPlayerDone()
    closeVideo()
    if m.pendingLink <> invalid
        link = m.pendingLink
        m.pendingLink = invalid
        handleDeepLink(link)
    end if
end sub

sub onVideoState()
    if m.video.state = "error" then print "Video error: "; m.video.errorMsg
end sub

function onKeyEvent(key as string, press as boolean) as boolean
    if not press or key <> "back" then return false
    if m.video.visible
        ' Stopping the video lets PlayerTask exit; it reports done and closeVideo runs.
        m.video.control = "stop"
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
