sub init()
    m.top.functionName = "playWithAds"
end sub

sub playWithAds()
    video = m.top.video
    view = video.getParent()
    m.pending = []
    m.lastPosition = 0
    m.session = CreateObject("roDeviceInfo").GetRandomUUID()
    m.ticket = invalid
    m.seq = 1

    ' No ads on Roku while the store listing is non-monetized (2026-10-11: Roku blocks
    ' publishing a monetized app until Partner Payouts enrollment works, and its payout page
    ' errors). To bring ads back: restore the RAF block from git history (commit 30d81eb),
    ' Library "Roku_Ads.brs", bs_libs_required=roku_ads_lib, and set Monetization to ads.
    adIface = invalid

    ' Only ad events carrying the server-signed ticket count toward filmmaker payouts.
    if adIface <> invalid then m.ticket = fetchTicket()

    keepPlaying = true
    if adIface <> invalid
        keepPlaying = playPods(adIface, adIface.getAds(), view)
    end if
    if keepPlaying then playContent(adIface, video, view)

    ' Remember where the viewer stopped (cleared automatically near the end).
    if m.top.bookmark
        ' The last position seen while playing; after "stop" the node may already report 0.
        saveBookmark(m.top.titleId, m.top.episode, Int(m.lastPosition), Int(video.duration))
    end if
    flushEvents()
    m.top.done = true
end sub

' Main content loop: watches position for mid-roll cue points and plays the post-roll at the end.
sub playContent(adIface as dynamic, video as object, view as object)
    port = CreateObject("roMessagePort")
    video.observeField("position", port)
    video.observeField("state", port)
    video.visible = true
    video.control = "play"
    video.setFocus(true)

    position = 0
    pods = invalid
    postroll = false
    while true
        msg = wait(0, port)
        if type(msg) = "roSGNodeEvent"
            field = msg.getField()
            if field = "position"
                position = msg.getData()
                m.lastPosition = position
                if adIface <> invalid
                    pods = adIface.getAds(msg)
                    ' Stopping the video hands the break to the "stopped" branch below.
                    if pods <> invalid and pods.count() > 0 then video.control = "stop"
                end if
            else if field = "state"
                state = msg.getData()
                if state = "stopped"
                    ' A stop with no pending break means the viewer pressed Back.
                    if pods = invalid or pods.count() = 0 then return
                    keepPlaying = playPods(adIface, pods, view)
                    pods = invalid
                    if postroll or not keepPlaying then return
                    video.visible = true
                    video.seek = position
                    video.control = "play"
                    video.setFocus(true)
                else if state = "finished"
                    if adIface = invalid then return
                    pods = adIface.getAds(msg)
                    if pods = invalid or pods.count() = 0 then return
                    postroll = true
                    video.control = "stop"
                else if state = "error"
                    return
                end if
            end if
        end if
    end while
end sub

' Shows one ad break, then sends the events it produced. Returns false if the viewer backed out.
function playPods(adIface as object, pods as dynamic, view as object) as boolean
    if pods = invalid or pods.count() = 0 then return true
    m.top.video.visible = false
    result = adIface.showAds(pods, invalid, view)
    flushEvents()
    return result
end function

' RAF tracking callback. Buffered because HTTP here would stall ad rendering.
sub onAdTracking(obj = invalid as dynamic, eventType = invalid as dynamic, ctx = invalid as dynamic)
    if eventType = "Impression"
        obj.pending.push("ad_started")
    else if eventType = "Complete"
        obj.pending.push("ad_completed")
    end if
end sub

' Asks start_playback for a signed playback ticket ({session_id, token}); invalid on any
' failure or after 3 s, in which case events are still sent (stored, not counted).
function fetchTicket() as dynamic
    url = startPlaybackUrl(m.top.trackingUrl)
    if url = "" then return invalid
    port = CreateObject("roMessagePort")
    http = CreateObject("roUrlTransfer")
    http.SetMessagePort(port)
    http.SetUrl(url)
    http.SetCertificatesFile("common:/certs/ca-bundle.crt")
    http.InitClientCertificates()
    http.AddHeader("apikey", m.top.apiKey)
    http.AddHeader("Content-Type", "application/json")
    if not http.AsyncPostFromString(FormatJson({ title_id: m.top.titleId, episode: m.top.episode, platform: "roku" })) then return invalid
    msg = wait(3000, port)
    if type(msg) <> "roUrlEvent" then
        http.AsyncCancel()
        return invalid
    end if
    if msg.GetResponseCode() < 200 or msg.GetResponseCode() > 299 then return invalid
    t = ParseJson(msg.GetString())
    if t = invalid or type(t) <> "roAssociativeArray" or t.session_id = invalid or t.token = invalid then return invalid
    return t
end function

sub flushEvents()
    if m.pending.count() = 0 or m.top.trackingUrl = "" then return
    rows = adEventRows(m.pending, m.top.titleId, m.top.episode, m.ticket, m.session, m.seq)
    m.seq = m.seq + m.pending.count()
    m.pending = []
    http = CreateObject("roUrlTransfer")
    http.SetUrl(m.top.trackingUrl)
    http.SetCertificatesFile("common:/certs/ca-bundle.crt")
    http.InitClientCertificates()
    http.AddHeader("apikey", m.top.apiKey)
    http.AddHeader("Content-Type", "application/json")
    http.AddHeader("Prefer", "return=minimal")
    code = http.PostFromString(FormatJson(rows))
    if code < 200 or code > 299 then print "Ad tracking post failed: "; code
end sub
