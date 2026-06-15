import SwiftUI

/// Maps a result to an SF Symbol, echoing the workflow's per-title icons.
enum Icon {
    static func symbol(for result: SearchResult) -> String {
        if result.kind == .event { return "calendar" }
        let t = (result.titleName ?? "").lowercased()
        if t.contains("pope") || t.contains("patriarch") || t.contains("antipope") { return "cross.fill" }
        if t.contains("president") { return "person.crop.square.fill" }
        if t.contains("prime minister") || t.contains("chancellor") || t.contains("premier") { return "building.columns.fill" }
        if t.contains("consul") || t.contains("tribune") || t.contains("dictator") { return "laurel.leading" }
        return "crown.fill"
    }

    static func tint(for result: SearchResult) -> Color {
        result.kind == .event ? .orange : .indigo
    }
}
