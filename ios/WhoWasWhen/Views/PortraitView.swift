import SwiftUI

/// A circular Wikipedia thumbnail for a ruler or event, falling back to the
/// result's SF Symbol while loading, offline, or when the page has no image.
struct PortraitView: View {
    let result: SearchResult
    var size: CGFloat = 40

    @State private var thumbnailURL: URL?

    var body: some View {
        Group {
            if let thumbnailURL {
                AsyncImage(url: thumbnailURL) { phase in
                    switch phase {
                    case .success(let image):
                        image.resizable().scaledToFill()
                    default:
                        fallback
                    }
                }
            } else {
                fallback
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .task(id: result.wikipediaURL) {
            guard let url = result.wikipediaURL else { return }
            thumbnailURL = await WikipediaClient.shared.summary(for: url)?.thumbnailURL
        }
    }

    private var fallback: some View {
        ZStack {
            Circle().fill(Icon.tint(for: result).opacity(0.12))
            Image(systemName: Icon.symbol(for: result))
                .font(.system(size: size * 0.45))
                .foregroundStyle(Icon.tint(for: result))
        }
    }
}
