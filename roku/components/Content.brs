' Helpers shared by MainScene and DetailsView for building RowList content.

' main.brs saves the live catalog (haukley.com/roku/catalog.json) to cachefs: before the scene
' starts; fall back to the copy in the package when there isn't one or it doesn't parse.
function loadCatalog() as object
    live = ParseJson(ReadAsciiFile("cachefs:/catalog.json"))
    if live <> invalid and live.titles <> invalid and live.rows <> invalid and live.rows.Count() > 0
        return live
    end if
    return ParseJson(ReadAsciiFile("pkg:/data/catalog.json"))
end function

' Adds one artwork tile to a row ContentNode.
function addTile(row as object, poster as string, fields as object) as object
    node = row.createChild("ContentNode")
    node.HDPosterUrl = poster
    base = { titleId: "", label: "", subLabel: "", rank: 0, progress: 0.0, episode: 0, action: "open", url: "", playTitle: "" }
    base.append(fields)
    node.addFields(base)
    return node
end function

function metaLine(t as object) as string
    return t.genre + "  ·  " + t.year.ToStr() + "  ·  " + t.rating + "  ·  " + t.length
end function

' ---- Bookmarks (resume position) -------------------------------------------------------
' Roku certification: long-form VOD must resume where the viewer stopped, and bookmarks must
' be kept at least 30 days. Stored in the registry as one JSON map keyed "<titleId>|<episode>".

function bookmarkKey(titleId as string, episode as integer) as string
    return titleId + "|" + episode.ToStr()
end function

function loadBookmarks() as object
    raw = CreateObject("roRegistrySection", "bookmarks").Read("all")
    if raw = "" then return {}
    marks = ParseJson(raw)
    if marks = invalid then return {}
    return marks
end function

' Seconds to resume from, or 0 when there is nothing worth resuming.
function bookmarkFor(titleId as string, episode as integer) as integer
    mark = loadBookmarks()[bookmarkKey(titleId, episode)]
    if mark = invalid then return 0
    return mark.p
end function

sub saveBookmark(titleId as string, episode as integer, position as integer, duration as integer)
    marks = loadBookmarks()
    key = bookmarkKey(titleId, episode)
    ' Finished (or barely started) titles start over next time.
    if position < 10 or (duration > 0 and position > duration * 0.95)
        marks.Delete(key)
    else
        marks[key] = { p: position, d: duration, t: CreateObject("roDateTime").AsSeconds() }
    end if
    ' Roku requires at least 30 days: drop only marks older than 60 days, and past 150 entries
    ' (registry space is limited) the oldest one.
    now = CreateObject("roDateTime").AsSeconds()
    for each k in marks.Keys()
        if now - marks[k].t > 60 * 86400 then marks.Delete(k)
    end for
    if marks.Count() > 150
        ' Start above "now" and skip the mark just written: saves within the same second all
        ' share one timestamp, and a strict "< now" never picked any of them, so the cap
        ' silently stopped holding (caught by tests/bookmarks_test.brs).
        oldestKey = ""
        oldest = now + 1
        for each k in marks
            if k <> key and marks[k].t < oldest
                oldest = marks[k].t
                oldestKey = k
            end if
        end for
        marks.Delete(oldestKey)
    end if
    sec = CreateObject("roRegistrySection", "bookmarks")
    sec.Write("all", FormatJson(marks))
    sec.Flush()
end sub

function twoDigits(n as integer) as string
    if n < 10 then return "0" + n.ToStr()
    return n.ToStr()
end function

function formatClock(seconds as integer) as string
    h = seconds \ 3600
    mnt = (seconds mod 3600) \ 60
    s = seconds mod 60
    if h > 0 then return h.ToStr() + ":" + twoDigits(mnt) + ":" + twoDigits(s)
    return mnt.ToStr() + ":" + twoDigits(s)
end function

' ---- ad tracking (PlayerTask) ----
' start_playback lives next to log_ad_events; "" when the tracking URL has another shape.
function startPlaybackUrl(trackingUrl as string) as string
    suffix = "log_ad_events"
    if Len(trackingUrl) <= Len(suffix) or Right(trackingUrl, Len(suffix)) <> suffix then return ""
    return Left(trackingUrl, Len(trackingUrl) - Len(suffix)) + "start_playback"
end function

' Rows for one log_ad_events batch. With a server ticket each row carries the signed token
' and its own seq (so a re-sent batch is never counted twice); without one the rows are
' stored but don't count toward payouts. seqStart is the seq of the first row.
function adEventRows(pending as object, titleId as string, episode as integer, ticket as dynamic, fallbackSession as string, seqStart as integer) as object
    rows = []
    seq = seqStart
    for each e in pending
        row = { title_id: titleId, episode: episode, platform: "roku", event: e }
        if ticket <> invalid
            row.session_id = ticket.session_id
            row.token = ticket.token
            row.seq = seq
        else
            row.session_id = fallbackSession
        end if
        rows.push(row)
        seq = seq + 1
    end for
    return rows
end function
