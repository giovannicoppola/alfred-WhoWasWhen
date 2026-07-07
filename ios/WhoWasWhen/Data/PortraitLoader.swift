import UIKit
import Vision
import CryptoKit

/// Downloads portrait thumbnails and crops them to a face-centered square.
/// Historical portraits are tall with the head near the top, so the naive
/// center crop routinely decapitates them (Henry VIII); Vision face detection
/// re-centers the crop, and images with no detectable face fall back to a
/// top-anchored crop. The cropped result is cached on disk, so the download and
/// the (expensive) face detection run at most once per image *per device* —
/// after that every launch reuses the finished crop.
actor PortraitLoader {
    static let shared = PortraitLoader()

    private var cache: [URL: UIImage] = [:]
    private var inFlight: [URL: Task<UIImage?, Never>] = [:]

    func image(for url: URL) async -> UIImage? {
        if let hit = cache[url] { return hit }
        if let running = inFlight[url] { return await running.value }
        let task = Task<UIImage?, Never> { await Self.load(url) }
        inFlight[url] = task
        let image = await task.value
        inFlight[url] = nil
        if let image { cache[url] = image }
        return image
    }

    /// A dedicated queue for image decoding + Vision face detection + disk I/O.
    /// This work is synchronous and CPU-bound; running it directly in an `async`
    /// function would block a thread in Swift's small cooperative pool — the same
    /// pool the `Database` actor runs on. On the iOS 27 concurrency runtime
    /// (which no longer over-commits threads) a screenful of portraits starves
    /// that pool, so every subsequent query — search, quiz, Discover — hangs
    /// while the already-rendered results stay on screen. Keeping the blocking
    /// work on this GCD queue leaves the cooperative pool free for the actor.
    private static let processingQueue = DispatchQueue(
        label: "PortraitLoader.processing", qos: .userInitiated, attributes: .concurrent)

    /// The cropped-portrait cache directory, in Caches so the system can reclaim
    /// it under storage pressure (it's all re-derivable from Wikipedia).
    private static let cacheDirectory: URL = {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        let dir = base.appendingPathComponent("Portraits", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }()

    /// A stable on-disk filename for a source image URL.
    private nonisolated static func cacheURL(for url: URL) -> URL {
        let digest = SHA256.hash(data: Data(url.absoluteString.utf8))
        let name = digest.map { String(format: "%02x", $0) }.joined()
        return cacheDirectory.appendingPathComponent(name).appendingPathExtension("jpg")
    }

    /// Returns the face-cropped portrait: decoded from disk when it was already
    /// processed on a previous run, otherwise downloaded, cropped, and written
    /// to disk so the next run (and next launch) skips the network and Vision.
    private nonisolated static func load(_ url: URL) async -> UIImage? {
        let fileURL = cacheURL(for: url)
        if let cached = await decodeOnProcessingQueue({ try? Data(contentsOf: fileURL) }) {
            return cached
        }
        guard let (data, _) = try? await URLSession.shared.data(from: url) else { return nil }
        return await withCheckedContinuation { continuation in
            processingQueue.async {
                guard let image = UIImage(data: data) else {
                    continuation.resume(returning: nil); return
                }
                let cropped = squareCrop(image)
                if let jpeg = cropped.jpegData(compressionQuality: 0.9) {
                    try? jpeg.write(to: fileURL, options: .atomic)
                }
                continuation.resume(returning: cropped)
            }
        }
    }

    /// Decodes image data (produced by `dataProvider`) into a `UIImage` on the
    /// processing queue, off the cooperative pool. Returns nil when the provider
    /// yields no data (e.g. the disk cache miss) or the bytes aren't an image.
    private nonisolated static func decodeOnProcessingQueue(
        _ dataProvider: @escaping @Sendable () -> Data?) async -> UIImage? {
        await withCheckedContinuation { continuation in
            processingQueue.async {
                guard let data = dataProvider(), let image = UIImage(data: data) else {
                    continuation.resume(returning: nil); return
                }
                continuation.resume(returning: image)
            }
        }
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
