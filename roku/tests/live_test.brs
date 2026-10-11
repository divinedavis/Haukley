' Run: npx -p brs-node brs-cli components/Content.brs tests/live_test.brs  (from roku/)
' or tests/run_fast.sh from the repo root, which fails on any FAIL line.
sub Main()
    live = { kind: "live", id: "haukley-weather", title: "Haukley Weather", genre: "Weather", year: 2026, rating: "TV-G", length: "Live 24/7", stream: "https://haukley.com/live/weather/index.m3u8" }
    film = { kind: "movie", id: "metropolis", title: "Metropolis", genre: "Sci-Fi", year: 1927, rating: "NR", length: "2 hr 33 min", stream: "https://cdn/x/master.m3u8" }
    show = { kind: "show", id: "caminandes", title: "Caminandes", genre: "Animation", year: 2013, rating: "TV-G", length: "1 Season", episodes: [{ stream: "https://cdn/e1.m3u8" }] }

    check("live is live", isLive(live) and not isLive(film) and not isLive(show))
    check("live meta says LIVE, not a runtime", Left(metaLine(live), 4) = "LIVE" and Instr(1, metaLine(live), "2026") = 0)
    check("film meta keeps its runtime", Instr(1, metaLine(film), "2 hr 33 min") > 0)

    p = primaryPlay(live)
    check("live button is Watch Live", p.label = "Watch Live")
    check("live plays without ads", p.action.ads = false)
    check("live never resumes", p.action.startAt = 0 and p.action.episode = 0)
    check("live plays the channel stream", p.action.url = live.stream)
    check("film button is Play with ads", primaryPlay(film).label = "Play" and primaryPlay(film).action.ads = true)
    check("show button is Play E1", primaryPlay(show).label = "Play E1" and primaryPlay(show).action.url = "https://cdn/e1.m3u8")
    ' RAF setContentLength (certification RAF 1.3)
    check("film length in seconds", contentSeconds(film, 0) = 2 * 3600 + 33 * 60)
    check("minutes-only length", contentSeconds({ length: "46 min" }, 0) = 46 * 60)
    check("episode uses its minutes", contentSeconds({ length: "1 Season", episodes: [{ minutes: 25 }] }, 1) = 1500)
    check("live has no length", contentSeconds(live, 0) = 0)
    print "LIVE TESTS DONE"
end sub

sub check(name as string, ok as boolean)
    if ok then print "PASS "; name else print "FAIL "; name
end sub
