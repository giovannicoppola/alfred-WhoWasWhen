package com.giovannicoppola.whowaswhen.data

import android.content.Context

/** Round statistics persisted in SharedPreferences (the iOS UserDefaults). */
class QuizStats(context: Context) {
    private val prefs = context.getSharedPreferences("quiz", Context.MODE_PRIVATE)

    fun bestScore(category: QuizCategory): Int = prefs.getInt("quiz.best.${category.id}", 0)

    /** How many rounds of a category have been finished — drives list order. */
    fun playCount(category: QuizCategory): Int = prefs.getInt("quiz.plays.${category.id}", 0)

    val gamesPlayed: Int get() = prefs.getInt("quiz.gamesPlayed", 0)
    val totalCorrect: Int get() = prefs.getInt("quiz.totalCorrect", 0)
    val totalAnswered: Int get() = prefs.getInt("quiz.totalAnswered", 0)

    /** Records a finished round; returns true if it set a new category best. */
    fun recordRound(score: Int, outOf: Int, category: QuizCategory): Boolean {
        val editor = prefs.edit()
        editor.putInt("quiz.gamesPlayed", gamesPlayed + 1)
        editor.putInt("quiz.totalCorrect", totalCorrect + score)
        editor.putInt("quiz.totalAnswered", totalAnswered + outOf)
        editor.putInt("quiz.plays.${category.id}", playCount(category) + 1)
        var newBest = false
        if (score > bestScore(category)) {
            editor.putInt("quiz.best.${category.id}", score)
            newBest = true
        }
        editor.apply()
        return newBest
    }
}
