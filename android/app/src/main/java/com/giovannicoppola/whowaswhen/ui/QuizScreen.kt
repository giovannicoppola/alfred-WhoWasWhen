package com.giovannicoppola.whowaswhen.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.spring
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Book
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.EmojiEvents
import androidx.compose.material.icons.filled.Palette
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.IosShare
import androidx.compose.material.icons.outlined.SportsEsports
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameNanos
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.giovannicoppola.whowaswhen.BuildConfig
import com.giovannicoppola.whowaswhen.QuizState
import com.giovannicoppola.whowaswhen.QuizState.Phase
import com.giovannicoppola.whowaswhen.WwwViewModel
import com.giovannicoppola.whowaswhen.data.Database
import com.giovannicoppola.whowaswhen.data.QuizCategory
import com.giovannicoppola.whowaswhen.data.QuizEngine
import com.giovannicoppola.whowaswhen.data.QuizQuestion
import com.giovannicoppola.whowaswhen.data.SubjectID
import com.giovannicoppola.whowaswhen.model.TitleInfo
import com.giovannicoppola.whowaswhen.model.formatNumber
import com.giovannicoppola.whowaswhen.model.titlePluralOrDefault
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.random.Random

/**
 * The Quiz tab: pick a category, answer a 10-question multiple-choice round
 * generated on the fly from the database. Mirrors iOS QuizView.
 */
@Composable
fun QuizScreen() {
    val actions = LocalAppActions.current
    val vm = actions.vm
    val st = vm.quiz
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        if (!st.titlesLoaded) {
            // The "By title" list mixes ruler titles with the lifespan callings
            // (Painters, Composers, …).
            st.titles = vm.quizTitles() + vm.peopleTitles()
            rebuildTitleOrder(vm, st)
            // Older databases predate the notable people / linked works; hide
            // those categories rather than offer an empty round.
            st.hasPeople = vm.holders(Database.lifespanTitles[0]).isNotEmpty()
            st.hasWorks = vm.quizWorks().isNotEmpty()
            st.titlesLoaded = true
        }
        // Automation hooks (debug builds): jump straight into a round or onto
        // a new-best score screen for screenshots.
        if (BuildConfig.DEBUG && st.phase == Phase.PICKING) {
            DebugHooks.takeQuiz()?.let { hook ->
                val cat = when (hook) {
                    "events" -> QuizCategory.Events
                    "rulers" -> QuizCategory.Rulers
                    "people" -> QuizCategory.People
                    "works" -> QuizCategory.Works
                    else -> QuizCategory.Mixed
                }
                start(vm, st, cat)
                if (DebugHooks.answer && st.questions.isNotEmpty()) {
                    select(actions, st, st.questions[0].correctIndex)
                }
                if (DebugHooks.score && st.phase == Phase.PLAYING) {
                    st.score = 9
                    st.newBest = true
                    st.phase = Phase.FINISHED
                }
            }
        }
    }

    IosScreen(
        background = if (st.phase == Phase.PICKING) Ios.colors.groupedBackground else Ios.colors.background,
        navBar = {
            IosNavBar(
                "Quiz",
                background = if (st.phase == Phase.PICKING) Ios.colors.groupedBackground else Ios.colors.background,
                leading = if (st.phase == Phase.PLAYING) {
                    { IosBarButton("End") { st.phase = Phase.PICKING } }
                } else null,
            )
        },
    ) {
        when (st.phase) {
            Phase.PICKING -> CategoryPicker(vm, st) { cat -> scope.launch { start(vm, st, cat) } }
            Phase.LOADING -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                IosProgressView("Preparing questions…")
            }
            Phase.PLAYING -> QuestionScreen(vm, st)
            Phase.FINISHED -> ScoreScreen(vm, st) { scope.launch { start(vm, st, st.category) } }
        }
    }
}

/**
 * "By title" order: categories never quizzed go first in a random order (so a
 * fresh list doesn't always lead with Antipopes), and ones already played
 * sink to the bottom, sorted A–Z. Rebuilt each time the picker appears.
 */
private fun rebuildTitleOrder(vm: WwwViewModel, st: QuizState) {
    val untried = st.titles.filter { vm.stats.playCount(QuizCategory.Title(it)) == 0 }
    val tried = st.titles.filter { vm.stats.playCount(QuizCategory.Title(it)) > 0 }
    st.orderedTitles = untried.shuffled() + tried.sortedBy { it.title }
}

private suspend fun start(vm: WwwViewModel, st: QuizState, cat: QuizCategory) {
    st.category = cat
    st.phase = Phase.LOADING
    val db = vm.database()
    val round = if (db == null) emptyList()
    else withContext(Dispatchers.IO) { QuizEngine.buildRound(cat, db) }
    if (round.size < 3) {
        st.phase = Phase.PICKING
        vm.showToast("Couldn't build a quiz for that category")
        return
    }
    st.questions = round
    st.index = 0
    st.score = 0
    st.selection = null
    st.newBest = false
    st.phase = Phase.PLAYING
}

private fun select(actions: AppActions, st: QuizState, i: Int) {
    if (st.selection != null) return
    st.selection = i
    if (i == st.questions[st.index].correctIndex) {
        st.score += 1
        actions.hapticSuccess()
    } else {
        actions.hapticError()
    }
}

private fun advance(vm: WwwViewModel, st: QuizState) {
    if (st.index + 1 < st.questions.size) {
        st.index += 1
        st.selection = null
    } else {
        st.newBest = vm.stats.recordRound(st.score, st.questions.size, st.category)
        st.phase = Phase.FINISHED
    }
}

// MARK: - Category picker

@Composable
private fun CategoryPicker(vm: WwwViewModel, st: QuizState, onPick: (QuizCategory) -> Unit) {
    // Rebuild each time the picker appears so untried titles re-shuffle and
    // just-played ones drop to the bottom.
    LaunchedEffect(Unit) { if (st.titlesLoaded) rebuildTitleOrder(vm, st) }

    val play = buildList {
        add(Triple<QuizCategory, String, ImageVector>(QuizCategory.Mixed, "Rulers and events from all of history", Icons.Filled.AutoAwesome))
        add(Triple(QuizCategory.Rulers, "Who ruled when, across every title", SfIcons.CrownFill))
        add(Triple(QuizCategory.Events, "When did it happen?", Icons.Filled.CalendarMonth))
        if (st.hasPeople) add(Triple(QuizCategory.People, "Artists, writers, scientists — when they lived", Icons.Filled.People))
        if (st.hasWorks) add(Triple(QuizCategory.Works, "Who wrote, painted, and composed what", Icons.Filled.Book))
    }

    LazyColumn(Modifier.fillMaxSize()) {
        item { GroupedHeader("Play", Modifier.padding(top = 0.dp)) }
        item {
            GroupedCard {
                play.forEachIndexed { i, (cat, subtitle, icon) ->
                    if (i > 0) IosDivider(60.dp)
                    CategoryRow(vm, cat, subtitle, icon, onPick)
                }
            }
        }
        item { GroupedHeader("By title") }
        itemsIndexed(st.orderedTitles, key = { _, t -> t.titleID }) { i, t ->
            TitleRow(vm, t, isFirst = i == 0, isLast = i == st.orderedTitles.lastIndex, onPick)
        }
        if (vm.stats.gamesPlayed > 0) {
            item {
                Spacer(Modifier.height(35.dp))
                GroupedCard {
                    Row(
                        Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(Icons.Outlined.SportsEsports, null, tint = Ios.colors.accent, modifier = Modifier.size(18.dp))
                        Spacer(Modifier.width(10.dp))
                        Text("${vm.stats.gamesPlayed} rounds played", style = Ios.type.footnote, color = Ios.colors.label)
                        Spacer(Modifier.weight(1f))
                        if (vm.stats.totalAnswered > 0) {
                            Text(
                                "${vm.stats.totalCorrect * 100 / vm.stats.totalAnswered}% correct",
                                style = Ios.type.footnote, color = Ios.colors.secondaryLabel,
                            )
                        }
                    }
                }
            }
        }
        item { Spacer(Modifier.height(28.dp)) }
    }
}

/** One "By title" row, drawn as a slice of a grouped card (first/last rounded). */
@Composable
private fun TitleRow(vm: WwwViewModel, t: TitleInfo, isFirst: Boolean, isLast: Boolean, onPick: (QuizCategory) -> Unit) {
    val r = 10.dp
    val shape = RoundedCornerShape(
        topStart = if (isFirst) r else 0.dp, topEnd = if (isFirst) r else 0.dp,
        bottomStart = if (isLast) r else 0.dp, bottomEnd = if (isLast) r else 0.dp,
    )
    Column(
        Modifier
            .padding(horizontal = 16.dp)
            .fillMaxWidth()
            .background(Ios.colors.groupedCell, shape)
    ) {
        if (!isFirst) IosDivider(60.dp)
        CategoryRow(
            vm, QuizCategory.Title(t),
            "${formatNumber(t.maxCount)} ${titlePluralOrDefault(t.titlePlural, t.title)}",
            if (Database.lifespanTitles.contains(t.title)) Icons.Filled.Palette else SfIcons.CrownFill,
            onPick,
        )
    }
}

@Composable
private fun CategoryRow(
    vm: WwwViewModel,
    cat: QuizCategory,
    subtitle: String,
    icon: ImageVector,
    onPick: (QuizCategory) -> Unit,
) {
    val c = Ios.colors
    val best = vm.stats.bestScore(cat)
    val source = remember { MutableInteractionSource() }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .rowHighlight(source)
            .clickable(interactionSource = source, indication = null) { onPick(cat) }
            .padding(horizontal = 20.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.width(28.dp), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = c.indigo, modifier = Modifier.size(20.dp))
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(cat.label, style = Ios.type.body.copy(fontWeight = FontWeight.Medium), color = c.label)
            Text(subtitle, style = Ios.type.caption, color = c.secondaryLabel)
        }
        if (best > 0) {
            Text(
                "Best $best/${QuizEngine.ROUND_SIZE}",
                style = Ios.type.caption2.copy(fontWeight = FontWeight.SemiBold),
                color = c.label,
                modifier = Modifier
                    .padding(start = 8.dp)
                    .background(c.yellow.copy(alpha = 0.25f), RoundedCornerShape(50))
                    .padding(horizontal = 6.dp, vertical = 2.dp),
            )
        }
        Spacer(Modifier.width(10.dp))
        Icon(SfIcons.ChevronRight, null, tint = c.tertiaryLabel, modifier = Modifier.size(13.dp))
    }
}

// MARK: - Question screen

@Composable
private fun QuestionScreen(vm: WwwViewModel, st: QuizState) {
    val actions = LocalAppActions.current
    val scope = rememberCoroutineScope()
    val c = Ios.colors
    val q = st.questions[st.index]

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        IosProgressBar(
            progress = if (st.questions.isEmpty()) 0f else st.index.toFloat() / st.questions.size,
            tint = c.indigo,
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Question ${st.index + 1} of ${st.questions.size}", style = Ios.type.subheadline, color = c.secondaryLabel)
            Spacer(Modifier.weight(1f))
            Icon(Icons.Filled.Star, null, tint = c.yellow, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
            Text(
                "${st.score}",
                style = Ios.type.subheadline.copy(fontWeight = FontWeight.SemiBold),
                color = c.yellow,
            )
        }
        // Event questions read as two lines: a generic "When did this
        // begin?" and then the event itself, undecorated.
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                q.prompt,
                style = if (q.subject == null) Ios.type.title3.copy(fontWeight = FontWeight.SemiBold) else Ios.type.headline,
                color = if (q.subject == null) c.label else c.secondaryLabel,
            )
            q.subject?.let {
                Text(it, style = Ios.type.title3.copy(fontWeight = FontWeight.SemiBold), color = c.label)
            }
        }

        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            q.options.forEachIndexed { i, option ->
                OptionButton(q, i, option, st.selection) { select(actions, st, i) }
            }
        }

        if (st.selection != null) {
            RevealRow(q) {
                scope.launch {
                    val r = when (val sid = q.subjectID) {
                        is SubjectID.Ruler -> vm.rulerById(sid.rulerID)
                        is SubjectID.Event -> vm.eventById(sid.eventID)
                        null -> null
                    }
                    if (r != null) vm.showDetail(r)
                }
            }
            Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                IosButton(
                    if (st.index + 1 < st.questions.size) "Next question" else "See score",
                    IosButtonStyle.PROMINENT,
                    onClick = { advance(vm, st) },
                )
            }
        }
    }
}

@Composable
private fun OptionButton(q: QuizQuestion, i: Int, option: String, selection: Int?, onSelect: () -> Unit) {
    val c = Ios.colors
    val answered = selection != null
    val fill = when {
        !answered -> c.secondaryBackground
        i == q.correctIndex -> c.green.copy(alpha = 0.22f)
        i == selection -> c.red.copy(alpha = 0.22f)
        else -> c.secondaryBackground
    }
    val status: @Composable () -> Unit = {
        if (answered) {
            if (i == q.correctIndex) Icon(Icons.Filled.CheckCircle, null, tint = c.green, modifier = Modifier.size(22.dp))
            else if (i == selection) Icon(Icons.Filled.Cancel, null, tint = c.red, modifier = Modifier.size(22.dp))
        }
    }
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(fill, RoundedCornerShape(12.dp))
            .hairlineBorder(c.secondaryLabel.copy(alpha = 0.25f), 12.dp)
            .iosClickable(enabled = !answered, onClick = onSelect),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                option,
                style = Ios.type.body,
                color = c.label,
                modifier = Modifier.weight(1f),
                textAlign = if (q.centerOptions) TextAlign.Center else TextAlign.Start,
            )
            if (!q.centerOptions) {
                Spacer(Modifier.width(8.dp))
                status()
            }
        }
        // Centered options (years) keep their symmetry: the verdict icon
        // floats at the trailing edge instead of sitting in the row.
        if (q.centerOptions) {
            Box(Modifier.align(Alignment.CenterEnd).padding(end = 14.dp)) { status() }
        }
    }
}

/**
 * The post-answer explanation, with a pill button to the ruler or event it
 * is about (the same detail sheet as a search result).
 */
@Composable
private fun RevealRow(q: QuizQuestion, onReadMore: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(q.explanation, style = Ios.type.footnote, color = Ios.colors.secondaryLabel)
        if (q.subjectID != null) {
            IosButton(
                "Read more", IosButtonStyle.BORDERED, onClick = onReadMore,
                tint = Ios.colors.indigo, capsule = true, small = true, icon = Icons.Outlined.Info,
            )
        }
    }
}

// MARK: - Score screen

@Composable
private fun ScoreScreen(vm: WwwViewModel, st: QuizState, onPlayAgain: () -> Unit) {
    val actions = LocalAppActions.current
    val c = Ios.colors
    val total = st.questions.size
    val ratio = st.score.toDouble() / maxOf(total, 1)
    val emoji = when {
        ratio >= 0.9 -> "👑"
        ratio >= 0.7 -> "🏛️"
        ratio >= 0.4 -> "📜"
        else -> "🏺"
    }
    // Premade text for the share sheet.
    val shareMessage = buildString {
        append("I just scored ${st.score}/$total on the ${st.category.label} round of the WhoWasWhen history quiz!")
        if (st.newBest) append(" New personal best 🏆")
        append(" Who ruled — and who painted, composed, and discovered — in any year of history? 👑 https://giovannicoppola.github.io/alfred-WhoWasWhen/")
    }
    val trophyScale = remember { Animatable(0.3f) }
    LaunchedEffect(st.newBest) {
        if (st.newBest) {
            delay(200)
            actions.hapticSuccess()
            trophyScale.animateTo(1f, spring(dampingRatio = 0.5f, stiffness = 195f))
        }
    }

    Box(Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            Spacer(Modifier.weight(1f))
            Text(emoji, fontSize = 64.sp)
            Text(
                "${st.score} / $total",
                style = Ios.type.body.copy(fontSize = 44.sp, fontWeight = FontWeight.Bold, lineHeight = 52.sp).monospacedDigit(),
                color = c.label,
            )
            if (st.newBest) {
                Row(
                    Modifier.scale(trophyScale.value),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Filled.EmojiEvents, null, tint = c.yellow, modifier = Modifier.size(22.dp))
                    Spacer(Modifier.width(8.dp))
                    Text("New best for ${st.category.label}!", style = Ios.type.headline, color = c.yellow)
                }
            } else {
                Text(
                    "Best for ${st.category.label}: ${vm.stats.bestScore(st.category)}/${QuizEngine.ROUND_SIZE}",
                    style = Ios.type.subheadline,
                    color = c.secondaryLabel,
                )
            }
            IosButton(
                "Share your score", IosButtonStyle.BORDERED,
                onClick = { actions.share(shareMessage, "Share your score") },
                tint = c.indigo, capsule = true, icon = Icons.Outlined.IosShare,
                modifier = Modifier.padding(top = 4.dp),
            )
            Spacer(Modifier.weight(1f))
            Column(
                Modifier.padding(start = 32.dp, end = 32.dp, bottom = 24.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                IosButton("Play again", IosButtonStyle.PROMINENT, onClick = onPlayAgain, fillWidth = true)
                IosButton("Categories", IosButtonStyle.BORDERED, onClick = { st.phase = Phase.PICKING }, fillWidth = true)
            }
        }
        if (st.newBest) Confetti()
    }
}

/**
 * A short, dependency-free confetti burst for new personal records: colored
 * flakes fall, drift, and spin across the screen for ~3 seconds.
 */
@Composable
private fun Confetti(count: Int = 48) {
    val c = Ios.colors
    val flakes = remember {
        val palette = listOf(c.yellow, c.indigo, c.teal, c.pink, c.orange, c.green)
        List(count) {
            Flake(
                x = Random.nextFloat(),
                delay = Random.nextFloat() * 0.7f,
                duration = 1.8f + Random.nextFloat() * 1.2f,
                drift = -70f + Random.nextFloat() * 140f,
                size = 6f + Random.nextFloat() * 5f,
                spin = -6f + Random.nextFloat() * 12f,
                color = palette.random(),
            )
        }
    }
    var t by remember { mutableFloatStateOf(0f) }
    LaunchedEffect(Unit) {
        // Screenshot hook (debug builds): hold the burst at a fixed moment.
        val freeze = if (BuildConfig.DEBUG) DebugHooks.confettiFreeze else null
        if (freeze != null) {
            t = freeze
            return@LaunchedEffect
        }
        val start = withFrameNanos { it }
        while (t < 3.8f) {
            withFrameNanos { now -> t = (now - start) / 1e9f }
        }
    }
    Canvas(Modifier.fillMaxSize()) {
        val pt = density
        for (f in flakes) {
            val life = (t - f.delay) / f.duration
            if (life <= 0f || life >= 1f) continue
            val x = f.x * size.width + f.drift * pt * life
            val y = life * life * (size.height + 60 * pt) - 30 * pt
            val alpha = if (life > 0.75f) (1 - life) / 0.25f else 1f
            val w = f.size * pt
            val h = f.size * 0.6f * pt
            rotate(Math.toDegrees((f.spin * life).toDouble()).toFloat(), pivot = Offset(x, y)) {
                drawRect(
                    f.color.copy(alpha = alpha),
                    topLeft = Offset(x - w / 2, y - h * 0.5f),
                    size = Size(w, h),
                )
            }
        }
    }
}

private data class Flake(
    val x: Float, val delay: Float, val duration: Float, val drift: Float,
    val size: Float, val spin: Float, val color: Color,
)
