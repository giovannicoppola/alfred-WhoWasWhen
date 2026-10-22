import SwiftUI

/// XCUITest has to attach to an app of its own; the tour drives INRange, not this.
@main
struct TourHost: App {
    var body: some Scene { WindowGroup { Text("INRange tour runner") } }
}
