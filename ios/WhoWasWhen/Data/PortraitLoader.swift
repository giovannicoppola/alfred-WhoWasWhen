import UIKit
import Vision

/// Downloads portrait thumbnails and crops them to a face-centered square.
/// Historical portraits are tall with the head near the top, so the naive
/// center crop routinely decapitates them (Henry VIII); Vision face detection
/// re-centers the crop, and images with no detectable face fall back to a
/// top-anchored crop. Each image is fetched and analyzed once, then cached.
actor PortraitLoader {
    static let shared = PortraitLoader()

    private var cache: [URL: UIImage] = [:]
    private var inFlight: [URL: Task<UIImage?, Never>] = [:]

    func image(for url: URL) async -> UIImage? {
        if let hit = cache[url] { return hit }
        if let running = inFlight[url] { return await running.value }
        let task = Task<UIImage?, Never> { await Self.fetchAndCrop(url) }
        inFlight[url] = task
        let image = await task.value
        inFlight[url] = nil
        if let image { cache[url] = image }
        return image
    }

    private nonisolated static func fetchAndCrop(_ url: URL) async -> UIImage? {
        guard let (data, _) = try? await URLSession.shared.data(from: url),
              let image = UIImage(data: data) else { return nil }
        return squareCrop(image)
    }

    /// A square crop that keeps the face in frame: centered on the union of
    /// detected faces, else anchored to the top (faces live in the upper
    /// third of portrait paintings).
    nonisolated static func squareCrop(_ image: UIImage) -> UIImage {
        guard let cg = image.cgImage else { return image }
        let w = CGFloat(cg.width), h = CGFloat(cg.height)
        let side = min(w, h)
        guard side > 0, w != h else { return image }
        var origin = CGPoint(x: (w - side) / 2, y: 0)

        if let face = faceUnion(cg) {
            // Vision's normalized rects use a bottom-left origin.
            let faceRect = CGRect(x: face.minX * w, y: (1 - face.maxY) * h,
                                  width: face.width * w, height: face.height * h)
            origin.x = min(max(faceRect.midX - side / 2, 0), w - side)
            origin.y = min(max(faceRect.midY - side / 2, 0), h - side)
        }

        let square = CGRect(origin: origin, size: CGSize(width: side, height: side))
        guard let cropped = cg.cropping(to: square) else { return image }
        return UIImage(cgImage: cropped, scale: image.scale,
                       orientation: image.imageOrientation)
    }

    private nonisolated static func faceUnion(_ cg: CGImage) -> CGRect? {
        let request = VNDetectFaceRectanglesRequest()
        let handler = VNImageRequestHandler(cgImage: cg, options: [:])
        guard (try? handler.perform([request])) != nil,
              let faces = request.results, !faces.isEmpty else { return nil }
        return faces.dropFirst().reduce(faces[0].boundingBox) {
            $0.union($1.boundingBox)
        }
    }
}
