import XCTest

/// The landing page's app tour, as a script. Not a test of anything: tools/tour/record.mjs films
/// the simulator while this runs and reads the `TOUR` lines it prints, one per caption and touch,
/// stamped with the wall clock the recording shares. It drives the WhoWasWhen already installed,
/// by bundle id. "On this day" and Discover change with the date and the dice, by design.
@MainActor
final class TourTests: XCTestCase {
    private let app = XCUIApplication(bundleIdentifier: "com.giovannicoppola.WhoWasWhen")

    func testTour() throws {
        continueAfterFailure = false
        app.launch()
        XCTAssert(app.searchFields.firstMatch.waitForExistence(timeout: 30))
        pause(1.5)

        caption("Who was when?", "A year, a ruler or an event, in one search box.")
        hold(4.4)

        caption("Who ruled in 1789", "Everyone in office that year, and how old they were.")
        tap(field("Year, ruler, or event"), hold: 0.6)
        type("1789\n")
        hold(2.2)
        drag(by: 320)
        hold(2.4)

        caption("Beyond rulers", "1888 artist: van Gogh at 35, beside Monet and Degas.")
        tap("Clear text", hold: 0.4)
        type("1888 artist\n")
        hold(1.6)
        drag(by: 330)
        hold(2.0)

        caption("Who they were", "A portrait, a lifespan, and a summary from Wikipedia.")
        tap(button(containing: "Vincent van Gogh (1853-1890)"), hold: 2.4)
        grow()
        hold(2.6)

        caption("Travel through time", "Jump to the year van Gogh was born.")
        tap("Travel to 1853", hold: 3.6)

        caption("Every holder of a title", "All the English monarchs, as a timeline.")
        tap(button(containing: "Victoria (1837-1901)"), hold: 1.4)
        grow()
        hold(0.6)
        tap("Show all English Monarchs", hold: 1.8)
        tap("chart.bar.doc.horizontal", hold: 3.4)

        caption("Discover", "What happened 100, 200, 300 years ago.")
        tap(tab("Discover"), hold: 2.2)
        tap("Surprise me", hold: 2.6)

        caption("Quiz yourself", "Endless questions from the same history.")
        tap(tab("Quiz"), hold: 1.0)
        tap(button(beginning: "Mixed"), hold: 2.2)
        tap(answer(), hold: 3.4)

        log("end")
        hold(5.0)
    }

    // MARK: - Finding things

    /// Every button and text field on screen, from one snapshot of the hierarchy. Querying
    /// elements one by one is slow, and a sheet over a screen leaves two buttons with one label
    /// whose indexes shift between queries; one snapshot answers both, and taps by position.
    private func frames(_ type: XCUIElement.ElementType, _ what: String, where match: (String) -> Bool) -> [CGRect] {
        var found: [CGRect] = []
        func walk(_ s: XCUIElementSnapshot) {
            if s.elementType == type && match(s.label) && !s.frame.isEmpty { found.append(s.frame) }
            s.children.forEach(walk)
        }
        for _ in 0..<20 {
            if let snap = try? app.snapshot() { walk(snap) }
            if !found.isEmpty { return found }
            pause(0.5)
        }
        XCTFail("nothing on screen matches \(what)")
        return []
    }

    /// The topmost match: a sheet's own button sits above the same-named one on the screen below.
    private func button(_ label: String) -> CGRect {
        frames(.button, label) { $0 == label }.min { $0.minY < $1.minY }!
    }

    private func button(beginning prefix: String) -> CGRect {
        frames(.button, prefix + "…") { $0.hasPrefix(prefix) }.min { $0.minY < $1.minY }!
    }

    private func button(containing text: String) -> CGRect {
        frames(.button, "…" + text + "…") { $0.contains(text) }.min { $0.minY < $1.minY }!
    }

    private func field(_ placeholder: String) -> CGRect {
        frames(.searchField, placeholder) { _ in true }.min { $0.minY < $1.minY }!
    }

    /// Tab bar buttons sit at the bottom; a list row can share their label.
    private func tab(_ label: String) -> CGRect {
        frames(.button, label) { $0 == label }.max { $0.minY < $1.minY }!
    }

    /// The first answer under the question: right or wrong, the explanation is the point.
    private func answer() -> CGRect {
        let question = frames(.staticText, "the question number") { $0.hasPrefix("Question ") }[0]
        let tabBar = tab("Quiz").minY
        return frames(.button, "an answer") { !$0.isEmpty }
            .filter { $0.minY > question.maxY + 30 && $0.maxY < tabBar - 10 }
            .min { $0.minY < $1.minY }!
    }

    // MARK: - Moves

    /// Every move says how long it should stay on screen (`hold`); plan.py keeps the moving
    /// stretches of the film and trims the still ones, so the runner's stalls never show.
    private func tap(_ frame: CGRect, hold seconds: TimeInterval) {
        log("tap", ["x": frame.midX, "y": frame.midY, "hold": 0.3 + seconds])
        pause(0.3)
        app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: frame.midX, dy: frame.midY)).tap()
        pause(seconds)
    }

    private func tap(_ label: String, hold seconds: TimeInterval) { tap(button(label), hold: seconds) }

    private func type(_ text: String) {
        log("hold", ["hold": 1.0])
        app.typeText(text)
    }

    /// Pulls a half-height Details sheet up to full height, where its actions are.
    private func grow() {
        let grabber = button("Sheet Grabber")
        log("hold", ["hold": 0.8])
        let start = app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: grabber.midX, dy: grabber.midY))
        start.press(forDuration: 0.05, thenDragTo: start.withOffset(CGVector(dx: 0, dy: -380)), withVelocity: 900, thenHoldForDuration: 0.1)
    }

    /// Scrolls a list by a fixed distance: a flick would land wherever its momentum ran out.
    private func drag(by distance: CGFloat) {
        log("hold", ["hold": 0.8])
        let start = app.coordinate(withNormalizedOffset: .zero).withOffset(CGVector(dx: 201, dy: 640))
        start.press(forDuration: 0.05, thenDragTo: start.withOffset(CGVector(dx: 0, dy: -distance)), withVelocity: 600, thenHoldForDuration: 0.1)
    }

    private func hold(_ seconds: TimeInterval) {
        log("hold", ["hold": seconds])
        pause(seconds)
    }

    private func pause(_ seconds: TimeInterval) { Thread.sleep(forTimeInterval: seconds) }

    // MARK: - The log record.mjs reads

    private func caption(_ title: String, _ sub: String) { log("caption", ["title": title, "sub": sub]) }

    private func log(_ type: String, _ fields: [String: Any] = [:]) {
        var event = fields
        event["type"] = type
        event["t"] = Date().timeIntervalSince1970
        let data = try! JSONSerialization.data(withJSONObject: event, options: [.sortedKeys])
        print("TOUR " + String(decoding: data, as: UTF8.self))
    }
}
