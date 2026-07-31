package com.marvis.nexainference

import android.app.Application
import ai.nexa.core.NexaSdk

/**
 * 应用入口：尽早初始化 Nexa SDK，使其可在任意组件内调用端侧推理。
 *
 * 注意：NexaSdk 的包名以官方 SDK 为准（本处按 ai.nexa:core 推断为 ai.nexa.core.*）。
 * 若编译报“unresolved reference”，请按 NEXA_SDK_NOTES.md 校正 import。
 */
class NexaApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        try {
            NexaSdk.getInstance().init(this)
        } catch (e: Throwable) {
            // 初始化失败不应直接崩溃，交由 InferenceService 在加载模型时报错
            e.printStackTrace()
        }
    }
}
