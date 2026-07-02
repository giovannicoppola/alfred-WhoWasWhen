import SwiftUI

/// A circular Wikipedia thumbnail for a ruler or event, falling back to the
/// result's SF Symbol while loading, offline, or when the page has no image.
/// Images are face-centered by PortraitLoader so heads stay in the circle.
struct PortraitView: View {
    let result: SearchResult
    var size: CGFloat = 40

    @State private var portrait: UIImage?

    var body: some View {
        Group {
            if let portrait {
                Image(uiImage: portrait)
                    .resizable()
                    .scaledToFill()
            } else {
                fallback
            }
        }
        .frame(width: size, height: size)
        .clipShape(Circle())
        .task(id: result.wikipediaURL) {
            portrait = nil
            guard let page = result.wikipediaURL,
                  let thumb = await WikipediaClient.shared.summary(for: page)?.thumbnailURL
            else { return }
            portrait = await PortraitLoader.shared.image(for: thumb)
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
