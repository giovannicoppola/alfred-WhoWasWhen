import Foundation

/// One multiple-choice question, fully self-contained.
struct QuizQuestion: Identifiable, Hashable {
    let id = UUID()
    var prompt: String
    var options: [String]
    var correctIndex: Int
    /// Shown after answering, e.g. "Julius Caesar — Roman Consul (59 BC)".
    var explanation: String
}

/// What a round draws its questions from.
enum QuizCategory: Hashable, Identifiable {
    case mixed
    case events
    case title(TitleInfo)

    var id: String {
        switch self {
        case .mixed: "mixed"
        case .events: "events"
        case .title(let t): "title-\(t.titleID)"
        }
    }

    var label: String {
        switch self {
        case .mixed: "Mixed"
        case .events: "Events"
        case .title(let t): titlePluralOrDefault(t.titlePlural, title: t.title)
        }
    }
}

/// Generates quiz rounds from the database — every question and every wrong
/// answer is real data, so the quiz works fully offline.
enum QuizEngine {
    static let roundSize = 10

    /// Fetches material and assembles a shuffled round for a category.
    @MainActor
    static func buildRound(category: QuizCategory, app: AppModel) async -> [QuizQuestion] {
        switch category {
        case .events:
            // Over-fetch: some events fail to yield clean distractor years.
            let events = await app.randomQuizEvents(limit: roundSize * 3)
            return eventQuestions(from: events, count: roundSize)

        case .title(let t):
            let holders = await app.holders(ofTitle: t.title)
            return rulerQuestions(for: t, holders: holders, count: roundSize)

        case .mixed:
            let titles = (await app.quizTitles()).shuffled()
            guard !titles.isEmpty else { return [] }
            // Roughly a third event questions, the rest ruler questions
            // spread over random titles.
            let eventTarget = roundSize / 3
            let events = await app.randomQuizEvents(limit: eventTarget * 3)
            var questions = eventQuestions(from: events, count: eventTarget)
            var i = 0
            while questions.count < roundSize && i < roundSize * 3 {
                let t = titles[i % titles.count]
                let holders = await app.holders(ofTitle: t.title)
                questions += rulerQuestions(for: t, holders: holders, count: 1)
                i += 1
            }
            return questions.shuffled()
        }
    }

    // MARK: - Ruler questions

    static func rulerQuestions(for title: TitleInfo, holders: [HolderRow],
                               count: Int) -> [QuizQuestion] {
        guard holders.count >= 6 else { return [] }
        var out: [QuizQuestion] = []
        var attempts = 0
        while out.count < count && attempts < count * 10 {
            attempts += 1
            let q = Bool.random()
                ? whoWasQuestion(title: title, holders: holders)
                : whenWasQuestion(title: title, holders: holders)
            // No two questions in a round should read the same.
            if let q, !out.contains(where: { $0.prompt == q.prompt }) {
                out.append(q)
            }
        }
        return out
    }

    /// "Who was «title» in «year»?" — wrong answers are holders of the same
    /// title who did *not* hold it that year (era-adjacent, so they're
    /// plausible). Excluding same-year holders also keeps co-consul years
    /// unambiguous.
    private static func whoWasQuestion(title: TitleInfo, holders: [HolderRow]) -> QuizQuestion? {
        guard let h = holders.randomElement(), h.startYear <= h.endYear else { return nil }
        let year = Int.random(in: h.startYear...h.endYear)

        let others = holders.filter {
            $0.name != h.name && ($0.endYear < year || $0.startYear > year)
        }
        let nearest = others.sorted {
            abs($0.progrTitle - h.progrTitle) < abs($1.progrTitle - h.progrTitle)
        }
        var wrongNames: [String] = []
        for cand in nearest.prefix(24).shuffled() where wrongNames.count < 3 {
            if !wrongNames.contains(cand.name) { wrongNames.append(cand.name) }
        }
        guard wrongNames.count == 3 else { return nil }

        let options = (wrongNames + [h.name]).shuffled()
        return QuizQuestion(
            prompt: "Who was \(title.title) in \(formatYear(year))?",
            options: options,
            correctIndex: options.firstIndex(of: h.name)!,
            explanation: "\(h.name) — \(title.title) (\(h.period))")
    }

    /// "When was «name» «title»?" — wrong answers are other holders' periods
    /// that don't overlap the right one (so exactly one option is defensible).
    private static func whenWasQuestion(title: TitleInfo, holders: [HolderRow]) -> QuizQuestion? {
        guard let h = holders.randomElement() else { return nil }

        let others = holders.filter {
            $0.period != h.period && ($0.endYear < h.startYear || $0.startYear > h.endYear)
        }
        let nearest = others.sorted {
            abs($0.progrTitle - h.progrTitle) < abs($1.progrTitle - h.progrTitle)
        }
        var wrongPeriods: [String] = []
        for cand in nearest.prefix(24).shuffled() where wrongPeriods.count < 3 {
            if !wrongPeriods.contains(cand.period) { wrongPeriods.append(cand.period) }
        }
        guard wrongPeriods.count == 3 else { return nil }

        let options = (wrongPeriods + [h.period]).shuffled()
        return QuizQuestion(
            prompt: "When was \(h.name) \(title.title)?",
            options: options,
            correctIndex: options.firstIndex(of: h.period)!,
            explanation: "\(h.name) — \(title.title) (\(h.period))")
    }

    // MARK: - Event questions

    static func eventQuestions(from events: [QuizEventRow], count: Int) -> [QuizQuestion] {
        var out: [QuizQuestion] = []
        for e in events where out.count < count {
            if let q = eventQuestion(e), !out.contains(where: { $0.prompt == q.prompt }) {
                out.append(q)
            }
        }
        return out
    }

    /// "When did this happen: «event»?" — the wrong years are offset from the
    /// right one, never in the future, and shown in chronological order.
    private static func eventQuestion(_ e: QuizEventRow) -> QuizQuestion? {
        let correct = e.startYear
        // Skip events that leak the answer in their name ("Panic of 1837").
        guard !e.name.contains(String(abs(correct))) else { return nil }
        let currentYear = Calendar.current.component(.year, from: .now)

        var years: Set<Int> = [correct]
        var attempts = 0
        while years.count < 4 && attempts < 40 {
            attempts += 1
            let magnitude = [3...9, 10...40, 50...150].randomElement()!
            let offset = Int.random(in: magnitude)
            let y = Bool.random() ? correct + offset : correct - offset
            if y <= currentYear { years.insert(y) }
        }
        guard years.count == 4 else { return nil }

        let sorted = years.sorted()
        let verb = e.startYear == e.endYear ? "happen" : "begin"
        let answer = e.startYear == e.endYear
            ? formatYear(e.startYear)
            : "\(formatYear(e.startYear))-\(formatYear(e.endYear))"
        return QuizQuestion(
            prompt: "When did this \(verb): \(e.name)?",
            options: sorted.map(formatYear),
            correctIndex: sorted.firstIndex(of: correct)!,
            explanation: "\(e.name) — \(answer)")
    }
}

/// Round statistics persisted in UserDefaults.
enum QuizStats {
    private static var defaults: UserDefaults { .standard }

    static func bestScore(for category: QuizCategory) -> Int {
        defaults.integer(forKey: "quiz.best.\(category.id)")
    }

    static var gamesPlayed: Int { defaults.integer(forKey: "quiz.gamesPlayed") }
    static var totalCorrect: Int { defaults.integer(forKey: "quiz.totalCorrect") }
    static var totalAnswered: Int { defaults.integer(forKey: "quiz.totalAnswered") }

    /// Records a finished round; returns true if it set a new category best.
    @discardableResult
    static func recordRound(score: Int, outOf answered: Int, category: QuizCategory) -> Bool {
        defaults.set(gamesPlayed + 1, forKey: "quiz.gamesPlayed")
        defaults.set(totalCorrect + score, forKey: "quiz.totalCorrect")
        defaults.set(totalAnswered + answered, forKey: "quiz.totalAnswered")
        if score > bestScore(for: category) {
            defaults.set(score, forKey: "quiz.best.\(category.id)")
            return true
        }
        return false
    }
}
