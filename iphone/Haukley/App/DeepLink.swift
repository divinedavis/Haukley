import Foundation

/// haukley:// links (App Store In-App Events, owner-approved 2026-10-10):
///   haukley://row/<row key>   Home, scrolled to that catalog row (e.g. haukley://row/horror)
///   haukley://title/<id>      that title's page (e.g. haukley://title/nosferatu)
/// Anything else (unknown host, missing key) is nil and the app just opens.
enum DeepLink: Equatable {
    case row(String)
    case title(String)

    init?(url: URL) {
        guard url.scheme?.lowercased() == "haukley", let host = url.host?.lowercased() else { return nil }
        let key = url.pathComponents.first { $0 != "/" }?.trimmingCharacters(in: .whitespaces) ?? ""
        guard !key.isEmpty, key.range(of: #"^[A-Za-z0-9-]+$"#, options: .regularExpression) != nil else { return nil }
        switch host {
        case "row": self = .row(key.lowercased())
        case "title": self = .title(key.lowercased())
        default: return nil
        }
    }
}
