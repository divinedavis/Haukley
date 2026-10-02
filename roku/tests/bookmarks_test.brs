' Run: npx -p brs-node brs-cli components/Content.brs tests/bookmarks_test.brs  (from roku/)
' or tests/run_fast.sh from the repo root, which fails on any FAIL line.
sub Main()
    CreateObject("roRegistrySection", "bookmarks").Delete("all")
    check("empty store resumes from 0", bookmarkFor("night-line", 0) = 0)
    saveBookmark("night-line", 0, 754, 3600)
    check("mid-film position is kept", bookmarkFor("night-line", 0) = 754)
    saveBookmark("borough", 3, 1200, 2700)
    check("episodes are keyed separately", bookmarkFor("borough", 3) = 1200 and bookmarkFor("borough", 1) = 0)
    saveBookmark("night-line", 0, 5, 3600)
    check("under 10s clears the bookmark", bookmarkFor("night-line", 0) = 0)
    saveBookmark("borough", 3, 2650, 2700)
    check("past 95% clears the bookmark", bookmarkFor("borough", 3) = 0)
    for i = 1 to 160
        saveBookmark("t" + i.ToStr(), 0, 100, 3600)
    end for
    check("store is capped at 150 entries", loadBookmarks().Count() <= 150)
    check("the newest mark survives the cap", bookmarkFor("t160", 0) = 100)
    check("formatClock m:ss", formatClock(754) = "12:34")
    check("formatClock h:mm:ss", formatClock(3725) = "1:02:05")
    CreateObject("roRegistrySection", "bookmarks").Delete("all")
    print "BOOKMARK TESTS DONE"
end sub

sub check(name as string, ok as boolean)
    if ok then print "PASS "; name else print "FAIL "; name
end sub
