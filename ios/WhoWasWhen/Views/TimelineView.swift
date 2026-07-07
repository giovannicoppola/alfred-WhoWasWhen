import SwiftUI

/// A vertical timeline rendering of a title's lineage: one node per reign,
/// linked by a rail, with century markers where the era changes. The focused
/// ruler (🌟 in the list rendering) gets a highlighted node.
struct LineageTimelineView: View {
    let results: [SearchResult]
    var scrollToID: SearchResult.ID?

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 0) {
                    ForEach(Array(results.enumerated()), id: \.element.id) { idx, result in
                        if showsCenturyMarker(at: idx) {
                            CenturyMarker(year: centuryStart(results[idx].startYear))
                        }
                        TimelineEntry(result: result,
                                      isFirst: idx == 0 && !showsCenturyMarker(at: 0),
                                      isLast: idx == results.count - 1)
                            .id(result.id)
                    }
                }
                .padding(.horizontal)
                .padding(.vertical, 8)
            }
            .onAppear {
                if let scrollToID {
                    proxy.scrollTo(scrollToID, anchor: .center)
                }
            }
        }
    }

    /// A marker appears before the first entry and wherever the century of
    /// `startYear` changes from the previous entry.
    private func showsCenturyMarker(at idx: Int) -> Bool {
        guard idx > 0 else { return true }
        return centuryStart(results[idx].startYear) != centuryStart(results[idx - 1].startYear)
    }

    private func centuryStart(_ year: Int) -> Int {
        Int((Double(year) / 100).rounded(.down)) * 100
    }
}

/// The "1500 —" era divider on the timeline rail.
private struct CenturyMarker: View {
    let year: Int

    var body: some View {
        HStack(spacing: 10) {
            Text(formatYear(year))
                .font(.caption.weight(.bold))
                .monospacedDigit()
                .foregroundStyle(.indigo)
                .frame(width: 64, alignment: .trailing)
            Rectangle()
                .fill(.indigo.opacity(0.35))
                .frame(height: 1)
        }
        .padding(.vertical, 6)
    }
}

/// One reign on the timeline: rail + node on the left, tappable card on the
/// right. The node is scaled/filled for the focused ruler.
private struct TimelineEntry: View {
    let result: SearchResult
    let isFirst: Bool
    let isLast: Bool
    @State private var showDetail = false

    /// Reign length in years, floored at 1 (single-year consulships).
    private var reignLength: Int { max(1, result.endYear - result.startYear) }

    var body: some View {
        Button { showDetail = true } label: { content }
            .buttonStyle(.plain)
            .sheet(isPresented: $showDetail) {
                ResultDetailView(result: result).presentationDetents([.medium, .large])
            }
    }

    private var content: some View {
        HStack(alignment: .top, spacing: 10) {
            // Years column.
            Text(yearLabel)
                .font(.caption2.weight(.semibold))
                .monospacedDigit()
                .foregroundStyle(.secondary)
                .frame(width: 64, alignment: .trailing)
                .padding(.top, 12)

            // Rail + node.
            VStack(spacing: 0) {
                Rectangle()
                    .fill(.indigo.opacity(isFirst ? 0 : 0.3))
                    .frame(width: 2, height: 14)
                Circle()
                    .fill(result.isCurrent ? Color.yellow : .indigo)
                    .frame(width: result.isCurrent ? 14 : 9,
                           height: result.isCurrent ? 14 : 9)
                    .overlay {
                        if result.isCurrent {
                            Circle().stroke(.yellow.opacity(0.35), lineWidth: 5)
                        }
                    }
                Rectangle()
                    .fill(.indigo.opacity(isLast ? 0 : 0.3))
                    .frame(width: 2)
                    .frame(maxHeight: .infinity)
            }

            // Card.
            VStack(alignment: .leading, spacing: 4) {
                Text(result.title)
                    .font(.subheadline.weight(result.isCurrent ? .bold : .medium))
                    .multilineTextAlignment(.leading)
                if !result.subtitle.isEmpty {
                    Text(result.subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)
                }
                // Reign-length bar: longer reign, longer bar (capped at 60y).
                Capsule()
                    .fill(.indigo.opacity(0.45))
                    .frame(width: 30 + 130 * min(CGFloat(reignLength), 60) / 60,
                           height: 4)
            }
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 10)
                    .fill(result.isCurrent
                          ? Color.yellow.opacity(0.14)
                          : Color(.secondarySystemBackground)))
            .padding(.vertical, 4)
        }
        .contentShape(Rectangle())
    }

    private var yearLabel: String {
        result.startYear == result.endYear
            ? formatYear(result.startYear)
            : "\(formatYear(result.startYear))–\(formatYear(result.endYear))"
    }
}

/// A compact horizontal bar placing one reign inside the title's whole era —
/// shown in the detail sheet ("where in Pope history does this pope sit?").
struct ReignSpanBar: View {
    /// Center label, e.g. "all Popes" (already pluralized by the caller).
    let eraLabel: String
    let reignStart: Int
    let reignEnd: Int
    let era: ClosedRange<Int>

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            GeometryReader { geo in
                let span = max(1, era.upperBound - era.lowerBound)
                let x0 = CGFloat(reignStart - era.lowerBound) / CGFloat(span) * geo.size.width
                let x1 = CGFloat(max(reignEnd, reignStart) - era.lowerBound) / CGFloat(span) * geo.size.width
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color.secondary.opacity(0.18))
                        .frame(height: 8)
                    Capsule()
                        .fill(.indigo)
                        // Keep even one-year reigns visible.
                        .frame(width: max(6, x1 - x0), height: 8)
                        .offset(x: min(x0, geo.size.width - 6))
                }
            }
            .frame(height: 8)
            HStack {
                Text(formatYear(era.lowerBound))
                Spacer()
                Text(eraLabel)
                Spacer()
                Text(formatYear(era.upperBound))
            }
            .font(.caption2)
            .monospacedDigit()
            .foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Reign from \(formatYear(reignStart)) to \(formatYear(reignEnd)), within \(eraLabel), \(formatYear(era.lowerBound)) to \(formatYear(era.upperBound))")
    }
}
