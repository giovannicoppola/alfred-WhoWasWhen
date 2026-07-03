import SwiftUI

/// The Quiz tab: pick a category, answer a 10-question multiple-choice round
/// generated on the fly from the database.
struct QuizView: View {
    @Environment(AppModel.self) private var app

    private enum Phase { case picking, loading, playing, finished }
    @State private var phase: Phase = .picking
    @State private var category: QuizCategory = .mixed
    @State private var titles: [TitleInfo] = []
    @State private var hasPeople = false
    @State private var questions: [QuizQuestion] = []
    @State private var index = 0
    @State private var selection: Int?
    @State private var score = 0
    @State private var newBest = false
    @State private var subjectDetail: SearchResult?
    @State private var trophyScale: CGFloat = 0.3

    var body: some View {
        NavigationStack {
            Group {
                switch phase {
                case .picking:
                    categoryPicker
                case .loading:
                    ProgressView("Preparing questions…")
                case .playing:
                    questionScreen
                case .finished:
                    scoreScreen
                }
            }
            .navigationTitle("Quiz")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if phase == .playing {
                    ToolbarItem(placement: .topBarLeading) {
                        Button("End") { phase = .picking }
                    }
                }
            }
            .task {
                print("[WWW] quiz tab task: awaiting db…")
                await app.load()   // wait for the database on a cold tab open
                titles = await app.quizTitles()
                // Older databases predate the notable people; hide the
                // category rather than offer an empty round.
                hasPeople = !(await app.holders(ofTitle: Database.lifespanTitles[0])).isEmpty
                print("[WWW] quiz titles loaded: \(titles.count)")
                #if DEBUG
                // Automation hooks: jump straight into a round (WWW_QUIZ=1|
                // events|rulers) or onto a new-best score screen (WWW_SCORE)
                // for screenshots.
                if let hook = ProcessInfo.processInfo.environment["WWW_QUIZ"], phase == .picking {
                    switch hook {
                    case "events": await start(.events)
                    case "rulers": await start(.rulers)
                    case "people": await start(.people)
                    default: await start(.mixed)
                    }
                }
                if ProcessInfo.processInfo.environment["WWW_SCORE"] != nil, phase == .playing {
                    score = 9
                    newBest = true
                    phase = .finished
                }
                #endif
            }
            .sheet(item: $subjectDetail) { result in
                ResultDetailView(result: result).presentationDetents([.medium, .large])
            }
        }
        .toastOverlay(app.toast)
    }

    // MARK: - Category picker

    private var categoryPicker: some View {
        List {
            Section("Play") {
                categoryRow(.mixed, subtitle: "Rulers and events from all of history",
                            symbol: "sparkles")
                categoryRow(.rulers, subtitle: "Who ruled when, across every title",
                            symbol: "crown.fill")
                categoryRow(.events, subtitle: "When did it happen?",
                            symbol: "calendar")
                if hasPeople {
                    categoryRow(.people, subtitle: "Artists, writers, scientists — when they lived",
                                symbol: "person.2.fill")
                }
            }
            Section("By title") {
                ForEach(titles) { t in
                    categoryRow(.title(t),
                                subtitle: "\(formatNumber(t.maxCount)) \(titlePluralOrDefault(t.titlePlural, title: t.title))",
                                symbol: "crown.fill")
                }
            }
            if QuizStats.gamesPlayed > 0 {
                Section {
                    HStack {
                        Label("\(QuizStats.gamesPlayed) rounds played", systemImage: "gamecontroller")
                        Spacer()
                        if QuizStats.totalAnswered > 0 {
                            Text("\(QuizStats.totalCorrect * 100 / QuizStats.totalAnswered)% correct")
                                .foregroundStyle(.secondary)
                        }
                    }
                    .font(.footnote)
                }
            }
        }
    }

    private func categoryRow(_ cat: QuizCategory, subtitle: String, symbol: String) -> some View {
        Button {
            Task { await start(cat) }
        } label: {
            HStack(spacing: 12) {
                Image(systemName: symbol)
                    .foregroundStyle(.indigo)
                    .frame(width: 28)
                VStack(alignment: .leading, spacing: 2) {
                    Text(cat.label).font(.body.weight(.medium))
                    Text(subtitle).font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                let best = QuizStats.bestScore(for: cat)
                if best > 0 {
                    Text("Best \(best)/\(QuizEngine.roundSize)")
                        .font(.caption2.weight(.semibold))
                        .padding(.horizontal, 6).padding(.vertical, 2)
                        .background(Capsule().fill(.yellow.opacity(0.25)))
                }
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.tertiary)
            }
        }
        .buttonStyle(.plain)
    }

    private func start(_ cat: QuizCategory) async {
        category = cat
        phase = .loading
        let round = await QuizEngine.buildRound(category: cat, app: app)
        guard round.count >= 3 else {
            phase = .picking
            app.showToast("Couldn't build a quiz for that category")
            return
        }
        questions = round
        index = 0
        score = 0
        selection = nil
        newBest = false
        trophyScale = 0.3
        phase = .playing
    }

    // MARK: - Question screen

    private var questionScreen: some View {
        let q = questions[index]
        return ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                ProgressView(value: Double(index), total: Double(questions.count))
                    .tint(.indigo)
                HStack {
                    Text("Question \(index + 1) of \(questions.count)")
                        .font(.subheadline).foregroundStyle(.secondary)
                    Spacer()
                    Label("\(score)", systemImage: "star.fill")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.yellow)
                }
                // Event questions read as two lines: a generic "When did
                // this begin?" and then the event itself, undecorated.
                VStack(alignment: .leading, spacing: 6) {
                    Text(q.prompt)
                        .font(q.subject == nil ? .title3.weight(.semibold) : .headline)
                        .foregroundStyle(q.subject == nil ? .primary : .secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    if let subject = q.subject {
                        Text(subject)
                            .font(.title3.weight(.semibold))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }

                VStack(spacing: 10) {
                    ForEach(q.options.indices, id: \.self) { i in
                        optionButton(q, i)
                    }
                }

                if selection != nil {
                    revealRow(q)
                    Button(index + 1 < questions.count ? "Next question" : "See score") {
                        advance()
                    }
                    .buttonStyle(.borderedProminent)
                    .frame(maxWidth: .infinity)
                }
            }
            .padding()
        }
    }

    private func optionButton(_ q: QuizQuestion, _ i: Int) -> some View {
        Button {
            select(i, in: q)
        } label: {
            HStack {
                if q.centerOptions { Spacer(minLength: 0) }
                Text(q.options[i])
                    .multilineTextAlignment(q.centerOptions ? .center : .leading)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: q.centerOptions ? 0 : 8)
                if !q.centerOptions { statusIcon(q, i) }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 12).fill(optionFill(q, i)))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.secondary.opacity(0.25), lineWidth: 1))
            // Centered options (years) keep their symmetry: the verdict icon
            // floats at the trailing edge instead of sitting in the row.
            .overlay(alignment: .trailing) {
                if q.centerOptions { statusIcon(q, i).padding(.trailing, 14) }
            }
        }
        .buttonStyle(.plain)
        .disabled(selection != nil)
    }

    @ViewBuilder private func statusIcon(_ q: QuizQuestion, _ i: Int) -> some View {
        if selection != nil {
            if i == q.correctIndex {
                Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
            } else if i == selection {
                Image(systemName: "xmark.circle.fill").foregroundStyle(.red)
            }
        }
    }

    /// The post-answer explanation; tappable when we know which ruler or
    /// event it is about, opening the same detail sheet as a search result.
    @ViewBuilder private func revealRow(_ q: QuizQuestion) -> some View {
        if q.subjectID != nil {
            Button {
                Task { await openSubject(q) }
            } label: {
                HStack(spacing: 8) {
                    Text(q.explanation)
                        .multilineTextAlignment(.leading)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 8)
                    Image(systemName: "chevron.right")
                        .foregroundStyle(.tertiary)
                }
                .font(.footnote)
                .foregroundStyle(.secondary)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
        } else {
            Text(q.explanation)
                .font(.footnote)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func openSubject(_ q: QuizQuestion) async {
        switch q.subjectID {
        case .ruler(let id): subjectDetail = await app.ruler(byID: id)
        case .event(let id): subjectDetail = await app.event(byID: id)
        case nil: break
        }
    }

    private func optionFill(_ q: QuizQuestion, _ i: Int) -> Color {
        guard selection != nil else { return Color(.secondarySystemBackground) }
        if i == q.correctIndex { return .green.opacity(0.22) }
        if i == selection { return .red.opacity(0.22) }
        return Color(.secondarySystemBackground)
    }

    private func select(_ i: Int, in q: QuizQuestion) {
        selection = i
        if i == q.correctIndex {
            score += 1
            UINotificationFeedbackGenerator().notificationOccurred(.success)
        } else {
            UINotificationFeedbackGenerator().notificationOccurred(.error)
        }
    }

    private func advance() {
        if index + 1 < questions.count {
            index += 1
            selection = nil
        } else {
            newBest = QuizStats.recordRound(score: score, outOf: questions.count,
                                            category: category)
            phase = .finished
        }
    }

    // MARK: - Score screen

    private var scoreScreen: some View {
        VStack(spacing: 20) {
            Spacer()
            Text(scoreEmoji)
                .font(.system(size: 64))
            Text("\(score) / \(questions.count)")
                .font(.system(size: 44, weight: .bold, design: .rounded))
                .monospacedDigit()
            if newBest {
                Label("New best for \(category.label)!", systemImage: "trophy.fill")
                    .font(.headline)
                    .foregroundStyle(.yellow)
                    .scaleEffect(trophyScale)
                    .onAppear {
                        withAnimation(.spring(response: 0.45, dampingFraction: 0.5)
                            .delay(0.2)) { trophyScale = 1 }
                        UINotificationFeedbackGenerator().notificationOccurred(.success)
                    }
            } else {
                Text("Best for \(category.label): \(QuizStats.bestScore(for: category))/\(QuizEngine.roundSize)")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            VStack(spacing: 12) {
                Button {
                    Task { await start(category) }
                } label: {
                    Text("Play again").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                Button {
                    phase = .picking
                } label: {
                    Text("Categories").frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
            }
            .padding(.horizontal, 32)
            .padding(.bottom, 24)
        }
        .overlay {
            if newBest { ConfettiView().ignoresSafeArea() }
        }
    }

    private var scoreEmoji: String {
        switch Double(score) / Double(max(questions.count, 1)) {
        case 0.9...: "👑"
        case 0.7..<0.9: "🏛️"
        case 0.4..<0.7: "📜"
        default: "🏺"
        }
    }
}

/// A short, dependency-free confetti burst for new personal records: colored
/// flakes fall, drift, and spin across the screen for ~3 seconds.
private struct ConfettiView: View {
    private struct Flake {
        let x: Double          // 0...1 across the width
        let delay: Double
        let duration: Double
        let drift: Double      // horizontal wander, in points
        let size: Double
        let spin: Double       // total rotation over the fall, in radians
        let color: Color
    }

    private let flakes: [Flake]
    private let start = Date()

    init(count: Int = 48) {
        let palette: [Color] = [.yellow, .indigo, .teal, .pink, .orange, .green]
        flakes = (0..<count).map { _ in
            Flake(x: .random(in: 0...1),
                  delay: .random(in: 0...0.7),
                  duration: .random(in: 1.8...3.0),
                  drift: .random(in: -70...70),
                  size: .random(in: 6...11),
                  spin: .random(in: -6...6),
                  color: palette.randomElement()!)
        }
    }

    var body: some View {
        TimelineView(.animation) { timeline in
            Canvas { context, size in
                let t = timeline.date.timeIntervalSince(start)
                for flake in flakes {
                    let life = (t - flake.delay) / flake.duration
                    guard life > 0, life < 1 else { continue }
                    let x = flake.x * size.width + flake.drift * life
                    let y = life * life * (size.height + 60) - 30
                    var layer = context
                    layer.opacity = life > 0.75 ? (1 - life) / 0.25 : 1
                    layer.translateBy(x: x, y: y)
                    layer.rotate(by: .radians(flake.spin * life))
                    let rect = CGRect(x: -flake.size / 2, y: -flake.size * 0.3,
                                      width: flake.size, height: flake.size * 0.6)
                    layer.fill(Path(rect), with: .color(flake.color))
                }
            }
        }
        .allowsHitTesting(false)
    }
}
