import Foundation
import Testing
@testable import Haukley

/// Ad tracking: only events carrying the server-signed playback ticket count toward payouts.
@Suite struct AdsTrackerTests {
    @Test func startPlaybackSitsNextToLogAdEvents() {
        let url = Ads.startPlaybackURL(from: "https://x.supabase.co/rest/v1/rpc/log_ad_events")
        #expect(url?.absoluteString == "https://x.supabase.co/rest/v1/rpc/start_playback")
        #expect(Ads.startPlaybackURL(from: "https://x.supabase.co/rest/v1/ad_events") == nil)
    }

    @Test(arguments: [Ads.Event.started, .completed])
    func ticketedEventCarriesTokenAndSeq(_ event: Ads.Event) {
        let body = Ads.eventBody(event, titleID: "metropolis", episode: 2, session: "s-1",
                                 token: "1790000000.abc", seq: 7)
        #expect(body["event"] as? String == event.rawValue)
        #expect(body["platform"] as? String == "ios")
        #expect(body["session_id"] as? String == "s-1")
        #expect(body["token"] as? String == "1790000000.abc")
        #expect(body["seq"] as? Int == 7)
        #expect(body["episode"] as? Int == 2)
    }

    @Test func eventWithoutTicketIsTokenless() {
        let body = Ads.eventBody(.started, titleID: "metropolis", episode: 0, session: "local",
                                 token: nil, seq: 1)
        #expect(body["token"] == nil)
        #expect(body["seq"] == nil)
        #expect(body["session_id"] as? String == "local")
    }
}
