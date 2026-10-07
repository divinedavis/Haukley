' Run: npx -p brs-node brs-cli components/Content.brs tests/adtracking_test.brs  (from roku/)
sub Main()
    check("start_playback url", startPlaybackUrl("https://x.supabase.co/rest/v1/rpc/log_ad_events") = "https://x.supabase.co/rest/v1/rpc/start_playback")
    check("other url shapes give empty", startPlaybackUrl("https://x.supabase.co/rest/v1/ad_events") = "")
    ticket = { session_id: "srv", token: "1790000000.abc" }
    rows = adEventRows(["ad_started", "ad_completed"], "metropolis", 0, ticket, "local", 3)
    check("one row per event", rows.Count() = 2)
    check("ticketed rows use the server session", rows[0].session_id = "srv" and rows[1].session_id = "srv")
    check("ticketed rows carry the token", rows[0].token = "1790000000.abc")
    check("seq counts up from seqStart", rows[0].seq = 3 and rows[1].seq = 4)
    check("platform is roku", rows[1].platform = "roku" and rows[1].event = "ad_completed")
    bare = adEventRows(["ad_started"], "metropolis", 2, invalid, "local", 1)
    check("no ticket: local session, no token, no seq", bare[0].session_id = "local" and bare[0].token = invalid and bare[0].seq = invalid)
    check("episode kept", bare[0].episode = 2)
    print "ADTRACKING TESTS DONE"
end sub

sub check(name as string, ok as boolean)
    if ok then print "PASS "; name else print "FAIL "; name
end sub
