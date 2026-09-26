' Deep links arrive two ways: as launch args (Roku search / voice / home-screen tiles) and as
' roInput events while the app is already running. Both go to MainScene.deepLink.
sub Main(args as dynamic)
    refreshCatalog()
    screen = CreateObject("roSGScreen")
    port = CreateObject("roMessagePort")
    screen.setMessagePort(port)
    scene = screen.CreateScene("MainScene")
    screen.show()

    input = CreateObject("roInput")
    input.setMessagePort(port)

    if args <> invalid and args.contentId <> invalid and args.contentId <> ""
        scene.deepLink = { contentId: args.contentId, mediaType: args.mediaType }
    end if

    while true
        msg = wait(0, port)
        t = type(msg)
        if t = "roSGScreenEvent" and msg.isScreenClosed()
            return
        else if t = "roInputEvent" and msg.isInput()
            info = msg.getInfo()
            if info.contentId <> invalid and info.contentId <> ""
                scene.deepLink = { contentId: info.contentId, mediaType: info.mediaType }
            end if
        end if
    end while
end sub

' Fetch the live catalog (max 4 s, while the splash screen shows) and keep it in cachefs: for
' MainScene. On any failure the previous cached copy, or the packaged one, is used instead.
sub refreshCatalog()
    xfer = CreateObject("roUrlTransfer")
    xfer.SetUrl("https://haukley.com/roku/catalog.json")
    xfer.SetCertificatesFile("common:/certs/ca-bundle.crt")
    xfer.InitClientCertificates()
    port = CreateObject("roMessagePort")
    xfer.SetMessagePort(port)
    if not xfer.AsyncGetToString() then return
    msg = wait(4000, port)
    if type(msg) = "roUrlEvent" and msg.GetResponseCode() = 200
        body = msg.GetString()
        parsed = ParseJson(body)
        if parsed <> invalid and parsed.titles <> invalid and parsed.rows <> invalid
            WriteAsciiFile("cachefs:/catalog.json", body)
        end if
    else
        xfer.AsyncCancel()
    end if
end sub
