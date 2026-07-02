import SwiftUI

/// The Quiz tab: pick a category, answer a 10-question multiple-choice round
/// generated on the fly from the database.
struct QuizView: View {
    @Environment(AppModel.self) private var app

    private enum Phase { case picking, loading, playing, finished }
    @State private var phase: Phase = .picking
    @State private var category: QuizCategory = .mixed
    @State private var titles: [TitleInfo] = []
    @State private var questions: [QuizQuestion] = []
    @State private var index = 0
    @State private var selection: Int?
    @State private var score = 0
    @State private var newBest = false

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
                await app.load()   // wait for the database on a cold tab open
                titles = await app.quizTitles()
                #if DEBUG
                // Automation hook: jump straight into a round for screenshots.
                if ProcessInfo.processInfo.environment["WWW_QUIZ"] != nil, phase == .picking {
                    await start(.mixed)
                }
                #endif
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
                categoryRow(.events, subtitle: "When did it happen?",
                            symbol: "calendar")
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
                Text(q.prompt)
                    .font(.title3.weight(.semibold))
                    .fixedSize(horizontal: false, vertical: true)

                VStack(spacing: 10) {
                    ForEach(q.options.indices, id: \.self) { i in
                        optionButton(q, i)
                    }
                }

                if selection != nil {
                    Text(q.explanation)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
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
                Text(q.options[i])
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 8)
                if selection != nil {
                    if i == q.correctIndex {
                        Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
                    } else if i == selection {
                        Image(systemName: "xmark.circle.fill").foregroundStyle(.red)
                    }
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 12).fill(optionFill(q, i)))
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color.secondary.opacity(0.25), lineWidth: 1))
        }
        .buttonStyle(.plain)
        .disabled(selection != nil)
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
