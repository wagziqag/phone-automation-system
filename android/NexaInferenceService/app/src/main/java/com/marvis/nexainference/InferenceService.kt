package com.marvis.nexainference

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat

/**
 * 前台服务：在手机本地启动 Nexa 推理引擎 + localhost HTTP 服务。
 *
 * 启动方式：
 *   context.startForegroundService(Intent(context, InferenceService::class.java))
 * 可选 extras：
 *   "port"   -> Int  监听端口（默认 8080）
 *   "plugin" -> String "npu"(默认, Hexagon) | "cpu"
 */
class InferenceService : Service() {

    private var server: LocalHttpServer? = null
    private var engine: NexaEngine? = null

    companion object {
        const val PORT_DEFAULT = 8080
        const val CHANNEL_ID = "nexa_inference_channel"
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val port = intent?.getIntExtra("port", PORT_DEFAULT) ?: PORT_DEFAULT
        val plugin = intent?.getStringExtra("plugin") ?: "npu"

        startForeground(1, buildNotification())

        if (server == null) {
            engine = NexaEngine(plugin)
            server = LocalHttpServer(port, engine!!) { msg ->
                android.util.Log.i("NexaService", msg)
            }
            server?.start()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        server?.stop()
        server = null
        super.onDestroy()
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val chan = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.channel_name),
                NotificationManager.IMPORTANCE_LOW
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(chan)
        }
    }

    private fun buildNotification(): Notification {
        val pi = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.notify_title))
            .setContentText(getString(R.string.notify_text))
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(pi)
            .setOngoing(true)
            .build()
    }
}
