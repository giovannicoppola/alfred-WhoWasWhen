import Foundation

/// The parts of a Wikipedia page summary the app uses.
struct WikipediaSummary: Sendable {
    var thumbnailURL: URL?
    var extract: String?
}

/// Fetches page summaries (portrait thumbnail + first-paragraph extract) from
/// the Wikipedia REST API, keyed by the article URL stored in the database.
/// Results are cached in memory and de-duplicated while in flight; any
/// failure returns nil and the UI falls back to SF Symbols and the bundled
/// one-line biography — the app never *requires* the network.
actor WikipediaClient {
    static let shared = WikipediaClient()

    private var cache: [URL: WikipediaSummary] = [:]
    private var inFlight: [URL: Task<WikipediaSummary?, Never>] = [:]

    func summary(for articleURL: URL) async -> WikipediaSummary? {
        if let hit = cache[articleURL] { return hit }
        if let running = inFlight[articleURL] { return await running.value }

        let task = Task { await Self.fetch(articleURL) }
        inFlight[articleURL] = task
        let value = await task.value
        inFlight[articleURL] = nil
        if let value { cache[articleURL] = value }
        return value
    }

    private static func fetch(_ articleURL: URL) async -> WikipediaSummary? {
        guard let endpoint = summaryEndpoint(for: articleURL) else { return nil }
        var request = URLRequest(url: endpoint)
        // Wikimedia asks API clients to identify themselves.
        request.setValue("WhoWasWhen-iOS/1.1 (https://github.com/giovannicoppola/alfred-WhoWasWhen)",
                         forHTTPHeaderField: "User-Agent")

        guard let (data, response) = try? await URLSession.shared.data(for: request),
              (response as? HTTPURLResponse)?.statusCode == 200 else { return nil }

        struct Payload: Decodable {
            struct Thumb: Decodable { let source: String }
            let thumbnail: Thumb?
            let extract: String?
            let type: String?
        }
        guard let payload = try? JSONDecoder().decode(Payload.self, from: data) else { return nil }
        // A bare name with no stored link can resolve to a disambiguation page
        // ("Frederick II may refer to: …") — its extract is a list of unrelated
        // people, so drop it rather than show it as an "About" summary.
        let extract = payload.type == "disambiguation" ? nil : payload.extract
        return WikipediaSummary(
            thumbnailURL: payload.thumbnail.flatMap { URL(string: $0.source) },
            extract: extract)
    }

    /// `…wikipedia.org/wiki/Julius_Caesar` → that host's
    /// `/api/rest_v1/page/summary/Julius_Caesar`. Keeping the article's own
    /// host means non-English links keep working.
    static func summaryEndpoint(for articleURL: URL) -> URL? {
        guard let host = articleURL.host, host.hasSuffix("wikipedia.org") else { return nil }
        let title = articleURL.lastPathComponent
        guard !title.isEmpty, title != "/" else { return nil }
        // `lastPathComponent` decodes percent escapes; re-encode for the API path.
        guard let encoded = title.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed)
        else { return nil }
        return URL(string: "https://\(host)/api/rest_v1/page/summary/\(encoded)")
    }
}
