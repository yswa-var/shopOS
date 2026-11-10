package com.shopos.bills.data

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import com.google.gson.Gson
import com.shopos.bills.form.BillDraftSnapshot

@Entity(tableName = "bill_drafts")
data class BillDraftEntity(
    @PrimaryKey val userId: String,
    val json: String,
    val updatedAtMillis: Long,
)

@Dao
interface BillDraftDao {
    @Query("SELECT * FROM bill_drafts WHERE userId = :userId")
    suspend fun get(userId: String): BillDraftEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun save(entity: BillDraftEntity)

    @Query("DELETE FROM bill_drafts WHERE userId = :userId")
    suspend fun delete(userId: String)
}

@Database(entities = [BillDraftEntity::class], version = 1, exportSchema = true)
abstract class ShopOsDatabase : RoomDatabase() {
    abstract fun drafts(): BillDraftDao
}

interface BillDraftStore {
    suspend fun load(userId: String): BillDraftSnapshot?
    suspend fun save(userId: String, snapshot: BillDraftSnapshot)
    suspend fun delete(userId: String)
}

class RoomBillDraftStore(private val dao: BillDraftDao, private val gson: Gson = Gson()) : BillDraftStore {
    override suspend fun load(userId: String): BillDraftSnapshot? {
        val entity = dao.get(userId) ?: return null
        return gson.fromJson(entity.json, BillDraftSnapshot::class.java).also {
            require(it.schemaVersion == 1) { "Unsupported local draft version" }
        }
    }

    override suspend fun save(userId: String, snapshot: BillDraftSnapshot) {
        dao.save(BillDraftEntity(userId, gson.toJson(snapshot), System.currentTimeMillis()))
    }

    override suspend fun delete(userId: String) = dao.delete(userId)
}

object DraftDatabase {
    @Volatile private var instance: ShopOsDatabase? = null

    fun store(context: Context): BillDraftStore {
        val database = instance ?: synchronized(this) {
            instance ?: Room.databaseBuilder(context.applicationContext, ShopOsDatabase::class.java, "shopos-drafts.db")
                .build().also { instance = it }
        }
        return RoomBillDraftStore(database.drafts())
    }
}
