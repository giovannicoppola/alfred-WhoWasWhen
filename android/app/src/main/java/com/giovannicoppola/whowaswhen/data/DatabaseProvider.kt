package com.giovannicoppola.whowaswhen.data

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import java.io.File

/**
 * Resolves the on-device `whoWasWhen.db`.
 *
 * The database ships bundled in `assets/` (so the app works instantly and
 * offline). Android's framework SQLite can't open a database straight from the
 * compressed asset stream, so we copy it into internal storage on first run —
 * mirroring the iOS working-copy strategy.
 *
 * The iOS build registers a custom `fold()` SQL function for accent- and
 * case-insensitive search. The framework SQLite offers no public API to
 * register one, so instead we precompute folded shadow columns (`*_fold`) once,
 * at copy time, using the exact same [foldForSearch] the search box uses. Text
 * search then becomes a plain `col_fold LIKE ?`.
 */
object DatabaseProvider {
    const val DB_NAME = "whoWasWhen.db"

    /**
     * Bump when the bundled asset changes OR the fold migration changes, so the
     * working copy is re-seeded on the next launch.
     */
    private const val ASSET_VERSION = 1
    private const val PREFS = "wwwdb"
    private const val KEY_VERSION = "db_asset_version"

    /** Returns the absolute path to a ready-to-query working copy. */
    fun resolveDatabasePath(context: Context): String {
        val working = File(context.filesDir, DB_NAME)
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val installed = prefs.getInt(KEY_VERSION, -1)

        if (!working.exists() || installed != ASSET_VERSION) {
            copyAsset(context, working)
            buildFoldColumns(working)
            prefs.edit().putInt(KEY_VERSION, ASSET_VERSION).apply()
        }
        return working.absolutePath
    }

    private fun copyAsset(context: Context, dest: File) {
        dest.parentFile?.mkdirs()
        context.assets.open(DB_NAME).use { input ->
            dest.outputStream().use { output -> input.copyTo(output) }
        }
    }

    /**
     * Adds `*_fold` columns to the searchable text columns and populates them
     * with [foldForSearch]. Idempotent: skips columns that already exist.
     */
    private fun buildFoldColumns(file: File) {
        val db = SQLiteDatabase.openDatabase(
            file.absolutePath, null, SQLiteDatabase.OPEN_READWRITE
        )
        try {
            val plan = listOf(
                Triple("rulers", "rulerID", listOf("name", "personal_name", "epithet", "notes")),
                Triple("titles", "titleID", listOf("title")),
                Triple("byEvents", "eventID", listOf("eventName", "notes")),
            )
            db.beginTransaction()
            try {
                for ((table, keyCol, cols) in plan) {
                    val existing = columnNames(db, table)
                    for (col in cols) {
                        if (!existing.contains(col)) continue // tolerate older schema
                        val foldCol = "${col}_fold"
                        if (!existing.contains(foldCol)) {
                            db.execSQL("ALTER TABLE $table ADD COLUMN $foldCol TEXT")
                        }
                        populateFold(db, table, keyCol, col, foldCol)
                    }
                }
                db.setTransactionSuccessful()
            } finally {
                db.endTransaction()
            }
        } finally {
            db.close()
        }
    }

    private fun populateFold(
        db: SQLiteDatabase, table: String, keyCol: String, col: String, foldCol: String,
    ) {
        val cursor = db.rawQuery("SELECT $keyCol, $col FROM $table", null)
        cursor.use { c ->
            val update = db.compileStatement("UPDATE $table SET $foldCol = ? WHERE $keyCol = ?")
            while (c.moveToNext()) {
                val key = c.getLong(0)
                val raw = if (c.isNull(1)) "" else c.getString(1)
                update.bindString(1, foldForSearch(raw))
                update.bindLong(2, key)
                update.executeUpdateDelete()
            }
        }
    }

    private fun columnNames(db: SQLiteDatabase, table: String): Set<String> {
        val names = HashSet<String>()
        db.rawQuery("PRAGMA table_info($table)", null).use { c ->
            val nameIdx = c.getColumnIndex("name")
            while (c.moveToNext()) names.add(c.getString(nameIdx))
        }
        return names
    }
}
