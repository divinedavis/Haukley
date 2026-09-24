' Deep links arrive two ways: as launch args (Roku search / voice / home-screen tiles) and as
' roInput events while the app is already running. Both go to MainScene.deepLink.
sub Main(args as dynamic)
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
