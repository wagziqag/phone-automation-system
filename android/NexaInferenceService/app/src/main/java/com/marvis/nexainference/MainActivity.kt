package com.marvis.nexainference

import android.content.Intent
import android.os.Build
import androidx.appcompat.app.AppCompatActivity
import android.os.Bundle
import android.widget.Button
import android.widget.TextView

/**
 * 简单启动/停止界面：用户手动拉起推理服务（也可由 BootReceiver 开机自启）。
 */
class MainActivity : AppCompatActivity() {

    private lateinit var statusText: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val startBtn = Button(this).apply { text = getString(R.string.start_server) }
        val stopBtn = Button(this).apply { text = getString(R.string.stop_server) }
        statusText = TextView(this).apply { text = "Nexa 本地推理服务（localhost:8080）" }

        val layout = android.widget.LinearLayout(this).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            setPadding(32, 32, 32, 32)
            addView(statusText)
            addView(startBtn)
            addView(stopBtn)
        }
        setContentView(layout)

        startBtn.setOnClickListener {
            val intent = Intent(this, InferenceService::class.java).apply {
                putExtra("port", 8080)
                putExtra("plugin", "npu")
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
            statusText.text = "服务已启动（npu 优先，非高通自动降级 cpu）"
        }

        stopBtn.setOnClickListener {
            stopService(Intent(this, InferenceService::class.java))
            statusText.text = "服务已停止"
        }
    }
}
