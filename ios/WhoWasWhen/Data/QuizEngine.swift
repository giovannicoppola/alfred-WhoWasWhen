import Foundation

/// One multiple-choice question, fully self-contained.
struct QuizQuestion: Identifiable, Hashable {
    /// The ruler or event the question (and its correct answer) is about,
    /// so the reveal can link to the full detail view.
    enum SubjectID: Hashable {
        case ruler(Int)
        case event(Int)
    }

    let id = UUID()
    var prompt: String
    /// Second prompt line — the event name for event questions ("When did
    /// this happen" / the event, per the requested two-line layout).
    var subject: String? = nil
    var options: [String]
    var correctIndex: Int
    /// Shown after answering, e.g. "Julius Caesar — Roman Consul (59 BC)".
    var explanation: String
    var subjectID: SubjectID? = nil
    /// Year options read better centered; names stay leading-aligned.
    var centerOptions: Bool = false
}

/// What a round draws its questions from.
enum QuizCategory: Hashable, Identifiable {
    case mixed
    case rulers
    case events
    case people
    case works
    case title(TitleInfo)

    var id: String {
        switch self {
        case .mixed: "mixed"
        case .rulers: "rulers"
        case .events: "events"
        case .people: "people"
        case .works: "works"
        case .title(let t): "title-\(t.titleID)"
        }
    }

    var label: String {
        switch self {
        case .mixed: "Mixed"
        case .rulers: "Rulers"
        case .events: "Events"
        case .people: "Notable people"
        case .works: "Works & authors"
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
            // Lifespan callings (Artist, Composer, …) can't use the ruler
            // "Who was X in «year»?" format — many hold the title at once — so
            // a single-calling round blends ~half "Who composed «work»?" with
            // ~half birth/death-year questions about the same calling.
            if Database.lifespanTitles.contains(t.title) {
                let works = (await app.quizWorks()).filter { $0.category == t.title }
                var qs = workQuestions(from: works, count: roundSize / 2)
                let people = holders.map { (category: t.title, person: $0) }.shuffled()
                qs += peopleQuestions(from: people, count: roundSize - qs.count,
                                      singleCalling: true)
                return qs.shuffled()
            }
            return rulerQuestions(for: t, holders: holders, count: roundSize)

        case .rulers:
            let titles = (await app.quizTitles()).shuffled()
            let questions = await rulerRound(titles: titles, count: roundSize, app: app)
            return questions.shuffled()

        case .people:
            let people = await notablePeople(app: app)
            return peopleQuestions(from: people, count: roundSize)

        case .works:
            let works = await app.quizWorks()
            return workQuestions(from: works, count: roundSize)

        case .mixed:
            let titles = (await app.quizTitles()).shuffled()
            guard !titles.isEmpty else { return [] }
            // Roughly a third event questions, a couple about notable
            // people, the rest ruler questions spread over random titles.
            let eventTarget = roundSize / 3
            let events = await app.randomQuizEvents(limit: eventTarget * 3)
            var questions = eventQuestions(from: events, count: eventTarget)
            let people = await notablePeople(app: app)
            questions += peopleQuestions(from: people, count: roundSize / 5)
            questions += workQuestions(from: await app.quizWorks(), count: roundSize / 5)
            questions += await rulerRound(titles: titles,
                                          count: roundSize - questions.count, app: app)
            return questions.shuffled()
        }
    }

    /// Every holder of a lifespan title, tagged with it — the Notable people
    /// question pool. Empty on databases that predate the notable people.
    @MainActor
    private static func notablePeople(app: AppModel) async -> [(category: String, person: HolderRow)] {
        var people: [(String, HolderRow)] = []
        for title in Database.lifespanTitles {
            for h in await app.holders(ofTitle: title) {
                people.append((title, h))
            }
        }
        return people.shuffled()
    }

    /// Ruler questions spread over random titles (the Mixed and Rulers rounds).
    @MainActor
    private static func rulerRound(titles: [TitleInfo], count: Int,
                                   app: AppModel) async -> [QuizQuestion] {
        guard !titles.isEmpty, count > 0 else { return [] }
        var questions: [QuizQuestion] = []
        var i = 0
        while questions.count < count && i < count * 3 {
            let t = titles[i % titles.count]
            let holders = await app.holders(ofTitle: t.title)
            questions += rulerQuestions(for: t, holders: holders, count: 1)
            i += 1
        }
        return questions
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
            explanation: "\(h.name) — \(title.title) (\(h.period))",
            subjectID: .ruler(h.rulerID))
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
            explanation: "\(h.name) — \(title.title) (\(h.period))",
            subjectID: .ruler(h.rulerID),
            centerOptions: true)
    }

    // MARK: - Notable-people questions

    /// "Who was Artist in 1503?" would have many right answers, so people
    /// questions ask what only one option can answer: when a person was
    /// born or died, or which calling they're known for.
    /// `singleCalling` rounds (a "By title" pick like Painters) skip the
    /// "What was this person?" variant — every answer would be the same.
    static func peopleQuestions(from people: [(category: String, person: HolderRow)],
                                count: Int, singleCalling: Bool = false) -> [QuizQuestion] {
        var out: [QuizQuestion] = []
        for (category, person) in people where out.count < count {
            let q = (!singleCalling && Int.random(in: 0..<3) == 0)
                ? whatWasQuestion(category: category, person: person)
                : lifeYearQuestion(category: category, person: person)
            if let q, !out.contains(where: { $0.subject == q.subject }) {
                out.append(q)
            }
        }
        return out
    }

    /// "When was this person born?" / "…die?" — same shape as the event
    /// year questions; a lifespan period's bounds are the birth/death years.
    private static func lifeYearQuestion(category: String, person: HolderRow) -> QuizQuestion? {
        let asksDeath = Bool.random()
        let correct = asksDeath ? person.endYear : person.startYear
        guard person.startYear < person.endYear,
              !person.name.contains(String(abs(correct))) else { return nil }
        let currentYear = Calendar.current.component(.year, from: .now)

        var years: Set<Int> = [correct]
        var attempts = 0
        while years.count < 4 && attempts < 40 {
            attempts += 1
            let magnitude = [2...8, 10...30, 40...90].randomElement()!
            let offset = Int.random(in: magnitude)
            let y = Bool.random() ? correct + offset : correct - offset
            if y <= currentYear { years.insert(y) }
        }
        guard years.count == 4 else { return nil }

        let sorted = years.sorted()
        return QuizQuestion(
            prompt: asksDeath ? "When did this person die?" : "When was this person born?",
            subject: person.name,
            options: sorted.map(formatYear),
            correctIndex: sorted.firstIndex(of: correct)!,
            explanation: "\(person.name) — \(category) (\(person.period))",
            subjectID: .ruler(person.rulerID),
            centerOptions: true)
    }

    /// "What was this person?" — the four options are lifespan callings,
    /// only one of which the person held.
    private static func whatWasQuestion(category: String, person: HolderRow) -> QuizQuestion? {
        let others = Database.lifespanTitles.filter { $0 != category }.shuffled()
        guard others.count >= 3 else { return nil }
        let options = (others.prefix(3) + [category]).shuffled()
        return QuizQuestion(
            prompt: "What was this person?",
            subject: person.name,
            options: Array(options),
            correctIndex: options.firstIndex(of: category)!,
            explanation: "\(person.name) — \(category) (\(person.period))",
            subjectID: .ruler(person.rulerID),
            centerOptions: true)
    }

    // MARK: - Works & authors questions

    /// The phrasing that reads right for a work's kind. Scientists' "works"
    /// are often discoveries or theories, not written texts ("Hawking
    /// radiation"), so they get "is known for"; visual art covers paintings
    /// and sculpture alike, so it stays with the neutral "created".
    private static func creationClause(for category: String, work: String) -> String {
        switch category {
        case "Composer": return "composed \(work)"
        case "Artist": return "created \(work)"
        case "Scientist": return "is known for \(work)"
        default: return "wrote \(work)"   // Writer, Philosopher
        }
    }

    /// "Who wrote «work»?" — the three wrong answers are other creators from
    /// the same category (so a painter isn't offered for a symphony), drawn
    /// from the nearest years to keep them era-plausible.
    static func workQuestions(from works: [WorkRow], count: Int) -> [QuizQuestion] {
        guard works.count >= 4 else { return [] }
        var out: [QuizQuestion] = []
        for w in works.shuffled() where out.count < count {
            // Creators who ALSO made a same-titled work (Schumann & Grieg both
            // wrote a "Piano Concerto in A minor") can't be wrong answers, or
            // the question would have two right ones. This set includes w's own
            // creator, so it doubles as the "not the answer" filter.
            let title = w.title.lowercased()
            let sameTitle = Set(works.filter { $0.title.lowercased() == title }
                .map(\.creatorRulerID))
            let sameKind = works.filter {
                $0.category == w.category && !sameTitle.contains($0.creatorRulerID)
            }
            let nearest = sameKind.sorted { abs($0.year - w.year) < abs($1.year - w.year) }
            var wrong: [String] = []
            for cand in nearest.prefix(20).shuffled() where wrong.count < 3 {
                if cand.creatorName != w.creatorName, !wrong.contains(cand.creatorName) {
                    wrong.append(cand.creatorName)
                }
            }
            guard wrong.count == 3 else { continue }
            // One work per creator per round keeps a name from being the
            // answer twice.
            if out.contains(where: { $0.subjectID == .ruler(w.creatorRulerID) }) { continue }

            let options = (wrong + [w.creatorName]).shuffled()
            out.append(QuizQuestion(
                prompt: "Who \(creationClause(for: w.category, work: w.title))?",
                options: options,
                correctIndex: options.firstIndex(of: w.creatorName)!,
                explanation: "\(w.title) — \(w.creatorName) (\(formatYear(w.year)))",
                subjectID: .ruler(w.creatorRulerID)))
        }
        return out
    }

    // MARK: - Event questions

    static func eventQuestions(from events: [QuizEventRow], count: Int) -> [QuizQuestion] {
        var out: [QuizQuestion] = []
        for e in events where out.count < count {
            // The prompt is now generic ("When did this begin?"), so the
            // subject is what makes an event question unique in a round.
            if let q = eventQuestion(e), !out.contains(where: { $0.subject == q.subject }) {
                out.append(q)
            }
        }
        return out
    }

    /// "When did this happen / begin / end" + the event on its own line —
    /// the wrong years are offset from the right one, never in the future,
    /// and shown in chronological order.
    private static func eventQuestion(_ e: QuizEventRow) -> QuizQuestion? {
        // Single-year events ask "happen"; ranged events ask start or end.
        let asksEnd = e.startYear != e.endYear && Bool.random()
        let correct = asksEnd ? e.endYear : e.startYear
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
        let verb = e.startYear == e.endYear ? "happen" : (asksEnd ? "end" : "begin")
        let answer = e.startYear == e.endYear
            ? formatYear(e.startYear)
            : "\(formatYear(e.startYear))-\(formatYear(e.endYear))"
        return QuizQuestion(
            prompt: "When did this \(verb)?",
            subject: e.name,
            options: sorted.map(formatYear),
            correctIndex: sorted.firstIndex(of: correct)!,
            explanation: "\(e.name) — \(answer)",
            subjectID: .event(e.eventID),
            centerOptions: true)
    }
}

/// Round statistics persisted in UserDefaults.
enum QuizStats {
    private static var defaults: UserDefaults { .standard }

    static func bestScore(for category: QuizCategory) -> Int {
        defaults.integer(forKey: "quiz.best.\(category.id)")
    }

    /// How many rounds of a given category have been finished — drives the
    /// "By title" list order (least-played first, to encourage exploration).
    static func playCount(for category: QuizCategory) -> Int {
        defaults.integer(forKey: "quiz.plays.\(category.id)")
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
        defaults.set(playCount(for: category) + 1, forKey: "quiz.plays.\(category.id)")
        if score > bestScore(for: category) {
            defaults.set(score, forKey: "quiz.best.\(category.id)")
            return true
        }
        return false
    }
}
