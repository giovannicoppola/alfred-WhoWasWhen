import SwiftUI

/// Builds pre-filled "report an issue" links (email + GitHub) so users can
/// flag data errors. No data is collected or transmitted by the app — the
/// user composes and sends from their own Mail/browser.
enum Reporting {
    static let email = "giovannicoppola@gmail.com"
    static let repo = "https://github.com/giovannicoppola/alfred-WhoWasWhen"

    static var appVersion: String {
        let info = Bundle.main.infoDictionary
        let v = info?["CFBundleShortVersionString"] as? String ?? "?"
        let b = info?["CFBundleVersion"] as? String ?? "?"
        return "\(v) (\(b))"
    }

    /// Subject + body, pre-filled with the entry's identifying details when
    /// reporting a specific result (so it can be located in the source sheet).
    private static func subjectAndBody(for result: SearchResult?) -> (String, String) {
        var subject = "WhoWasWhen feedback"
        var lines: [String] = []
        if let r = result {
            subject = "WhoWasWhen data issue: \(r.title)"
            lines.append("Entry: \(r.title)")
            if !r.subtitle.isEmpty { lines.append("Details: \(r.subtitle)") }
            lines.append("Type: \(r.kind == .ruler ? "Ruler" : "Event")")
            if let id = r.rulerID {
                var ref = "rulerID=\(id)"
                if let p = r.progrTitle { ref += ", progrTitle=\(p)" }
                if let t = r.titleName, !t.isEmpty { ref += ", title=\(t)" }
                lines.append("Reference: \(ref)")
            }
        }
        lines.append("App: WhoWasWhen \(appVersion)")
        lines.append("")
        lines.append("Describe the problem:")
        lines.append("")
        return (subject, lines.joined(separator: "\n"))
    }

    /// Percent-encodes everything except RFC 3986 unreserved characters, which
    /// is safe for both mailto and https query values.
    private static func encode(_ s: String) -> String {
        var allowed = CharacterSet.alphanumerics
        allowed.insert(charactersIn: "-._~")
        return s.addingPercentEncoding(withAllowedCharacters: allowed) ?? s
    }

    static func emailURL(for result: SearchResult?) -> URL? {
        let (subject, body) = subjectAndBody(for: result)
        return URL(string: "mailto:\(email)?subject=\(encode(subject))&body=\(encode(body))")
    }

    static func githubURL(for result: SearchResult?) -> URL? {
        let (subject, body) = subjectAndBody(for: result)
        return URL(string: "\(repo)/issues/new?title=\(encode(subject))&body=\(encode(body))")
    }
}

/// A single "Report an issue" control that expands to Email / GitHub choices.
/// Pass a `result` for a per-entry report, or nil for general feedback.
struct ReportMenu: View {
    var result: SearchResult? = nil
    @Environment(\.openURL) private var openURL

    var body: some View {
        Menu {
            if let url = Reporting.emailURL(for: result) {
                Button { openURL(url) } label: { Label("By email", systemImage: "envelope") }
            }
            if let url = Reporting.githubURL(for: result) {
                Button { openURL(url) } label: { Label("On GitHub", systemImage: "ladybug") }
            }
        } label: {
            Label("Report an issue", systemImage: "flag")
        }
    }
}
